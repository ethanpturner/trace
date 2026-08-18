"""Rendering persisted objects to HTML strings — pure, escaped, and content-safe.

Every function here takes a read-only `AssessmentHandle` (or the objects read from one) and returns
an HTML string. Nothing writes. Source-derived text is passed through `html.escape` before it
reaches the page, because the interface renders into a browser rather than the inert terminal the
command line writes to, and an excerpt of an untrusted document must not be able to inject markup.
Evidence excerpts carry the same untrusted label the command line uses, verbatim text and all: a
reviewer judging whether a document instructs its reader has to see the instruction.

The lineage view is the differentiator. It walks one finding to its hashed evidence through the
chain `services/findings/lineage.py` already assembles — threat, mapping, evidence assessment,
critique, context claim, evidence excerpt, document hash — and renders each link with the identifier
that ties it to the next. No assessment content is invented; the walk shows what the store holds.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.critique import Critique
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import EvidenceAssessment
from trace_ai.domain.execution import ExecutionRecord, WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import SourceDocument
from trace_ai.domain.threat import Threat
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.staleness import stale_evidence_ids
from trace_ai.services.findings.lineage import finding_lineage

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Any

    from trace_ai.domain.assessment import Assessment
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "VIEWS",
    "render_context",
    "render_diff",
    "render_evaluation",
    "render_findings",
    "render_index",
    "render_ledger",
    "render_lineage",
    "render_overview",
    "render_page",
    "render_questions",
    "render_threats",
    "render_workflow",
]

UNTRUSTED_LABEL = "quoted untrusted source content"

# The seven Stage 5 views, in navigation order: label and the path segment each renders at.
VIEWS: tuple[tuple[str, str], ...] = (
    ("Overview", "overview"),
    ("Context", "context"),
    ("Threats", "threats"),
    ("Workflow", "workflow"),
    ("Ledger", "ledger"),
    ("Questions & decisions", "questions"),
    ("Findings", "findings"),
    ("Lineage", "lineage"),
    ("Evaluation", "evaluation"),
)


def _e(value: object) -> str:
    """Escape any value for HTML. Source-derived text passes through here before the page."""
    return html.escape(str(value))


def _rows(pairs: Iterable[tuple[str, object]]) -> str:
    return "".join(f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>" for label, value in pairs)


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


# -- the page shell ----------------------------------------------------------------------------

_STYLE = """
:root { --fg:#1f2328; --muted:#57606a; --line:#d0d7de; --bg:#fff; --head:#f6f8fa;
        --accent:#0969da; --flag:#bc4c00; }
:root[data-theme="dark"], :root:not([data-theme="light"]) {
  --fg:#e6edf3; --muted:#9198a1; --line:#30363d; --bg:#0d1117; --head:#161b22;
  --accent:#4493f8; --flag:#db6d28; }
@media (prefers-color-scheme: light){ :root:not([data-theme="dark"]){
  --fg:#1f2328; --muted:#57606a; --line:#d0d7de; --bg:#fff; --head:#f6f8fa;
  --accent:#0969da; --flag:#bc4c00; } }
* { box-sizing: border-box; }
body { background:var(--bg); color:var(--fg); margin:0;
       font:15px/1.55 -apple-system, system-ui, sans-serif; }
header { border-bottom:1px solid var(--line); padding:1rem 1.5rem; }
header h1 { font-size:1.1rem; margin:0; }
nav { display:flex; flex-wrap:wrap; gap:0.25rem 1rem; padding:0.75rem 1.5rem;
      border-bottom:1px solid var(--line); }
nav a { color:var(--accent); text-decoration:none; }
main { padding:1.5rem; max-width:70rem; }
h2 { font-size:1.05rem; border-bottom:1px solid var(--line); padding-bottom:0.3rem; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; margin:0.5rem 0 1.5rem; }
th, td { text-align:left; padding:0.4rem 0.7rem; border-bottom:1px solid var(--line);
         vertical-align:top; }
thead th { background:var(--head); }
th[scope], tr > th:first-child { color:var(--muted); font-weight:600; white-space:nowrap; }
.muted { color:var(--muted); }
.flag { color:var(--flag); font-weight:600; }
.excerpt { border:1px solid var(--line); border-left:3px solid var(--flag); padding:0.6rem 0.8rem;
           margin:0.5rem 0; }
.excerpt .label { color:var(--flag); font-size:0.85rem; }
.excerpt pre { margin:0.3rem 0 0; white-space:pre-wrap; font:13px/1.5 ui-monospace, monospace; }
.lineage { border-left:2px solid var(--line); padding-left:1rem; margin-left:0.3rem; }
.lineage h3 { font-size:0.95rem; margin:1rem 0 0.3rem; }
code { font:13px/1.4 ui-monospace, monospace; }
a.finding { color:var(--accent); }
.ok { color:#1a7f37; font-weight:600; }
.drift { color:var(--flag); font-weight:600; }
"""


def render_page(title: str, assessment_id: str | None, active: str, body: str) -> str:
    """Wrap a view's body in the shared shell with the navigation the interface offers."""
    if assessment_id is None:
        nav = '<nav><a href="/">Assessments</a></nav>'
    else:
        links = ['<a href="/">Assessments</a>']
        for label, segment in VIEWS:
            mark = ' style="font-weight:700"' if segment == active else ""
            links.append(f'<a href="/{_e(assessment_id)}/{segment}"{mark}>{_e(label)}</a>')
        nav = "<nav>" + "".join(links) + "</nav>"
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"<header><h1>Trace — {_e(title)}</h1></header>\n{nav}\n<main>\n{body}\n</main>\n"
        "</body>\n</html>\n"
    )


# -- the views ---------------------------------------------------------------------------------


def render_index(assessments: Sequence[Assessment]) -> str:
    """The landing page: every assessment in the data root, identifiers and status only."""
    if not assessments:
        body = '<p class="muted">No assessments in this data root.</p>'
    else:
        rows = [
            [
                _link(a.id, f"/{a.id}/overview"),
                a.name,
                a.status.value,
                "rendered" if a.final_report_path else "—",
            ]
            for a in assessments
        ]
        body = _table_raw(["Assessment", "Name", "Status", "Report"], rows)
    if len(assessments) > 1:
        body += (
            "<h2>Compare two assessments</h2>"
            '<p class="muted">Pick two of the assessments above to diff their approved models '
            "at <code>/diff/&lt;before&gt;/&lt;after&gt;</code> (DEC-097).</p>"
        )
    return render_page("Read-only view", None, "", body)


def render_diff(before: str, after: str, diff: object) -> str:
    """One assessment diff, rendered read-only (#508). `diff` is an `AssessmentDiff`; a family
    with no movement is a count line, a moved family names its added, removed, and changed."""
    families = diff.families  # type: ignore[attr-defined]
    sections: list[str] = []
    for name, family in families.items():
        if not family.moved:
            sections.append(
                f'<p class="muted">{_e(name.replace("_", " "))}: {family.unchanged} unchanged.</p>'
            )
            continue
        rows: list[list[object]] = []
        for entry in family.added:
            rows.append(["added", entry.identity, "", entry.after_id or "—", ""])
        for entry in family.removed:
            rows.append(["removed", entry.identity, entry.before_id or "—", "", ""])
        for entry in family.changed:
            rows.append(
                [
                    "changed",
                    entry.identity,
                    entry.before_id or "—",
                    entry.after_id or "—",
                    ", ".join(entry.changed_fields),
                ]
            )
        sections.append(
            f"<h2>{_e(name.replace('_', ' '))} ({family.unchanged} unchanged)</h2>"
            + _table(["Change", "Identity", "Before", "After", "Fields"], rows)
        )
    heading = f"<p>Diff of <code>{_e(before)}</code> → <code>{_e(after)}</code>.</p>"
    if not diff.moved:  # type: ignore[attr-defined]
        heading += '<p class="muted">No differences in the approved models.</p>'
    return render_page("Assessment diff", None, "", heading + "".join(sections))


def render_overview(handle: AssessmentHandle, assessment: Assessment) -> str:
    """Assessment overview: the deliverable's identity, configuration, and counts."""
    config = assessment.configuration
    counts = handle.objects.counts_by_type()
    body = "<h2>Assessment</h2>" + _rows(
        [
            ("Identifier", assessment.id),
            ("Name", assessment.name),
            ("Status", assessment.status.value),
            ("Created", assessment.created_at.isoformat()),
            ("Workflow version", assessment.workflow_version),
            ("Requirements catalog", assessment.requirements_catalog_version or "-"),
            ("Model profile", config.model_profile),
            ("Threat methodology", config.threat_methodology),
            ("Final report", "rendered" if assessment.final_report_path else "not rendered"),
        ]
    )
    body = (
        f"<table>{body}</table>"
        + "<h2>Objects</h2>"
        + _table(
            ["Type", "Count"],
            [[_type_label(name), count] for name, count in sorted(counts.items())],
        )
    )
    return render_page("Overview", assessment.id, "overview", body)


def render_context(handle: AssessmentHandle, assessment: Assessment) -> str:
    """The extracted architecture context: the five object types and the claims."""
    sections: list[str] = []
    for label, model, kind_attr in (
        ("Components", Component, "component_type"),
        ("Actors", Actor, "actor_type"),
        ("Assets", Asset, "asset_type"),
        ("Data flows", DataFlow, "direction"),
        ("Trust boundaries", TrustBoundary, "boundary_type"),
    ):
        objects = handle.objects.list(model)
        if not objects:
            continue
        rows = [
            [getattr(obj, "id", "-"), getattr(obj, "name", "-"), getattr(obj, kind_attr, "-")]
            for obj in objects
        ]
        sections.append(
            f"<h2>{_e(label)} ({len(objects)})</h2>" + _table(["Identifier", "Name", "Kind"], rows)
        )

    claims = handle.objects.list(ContextClaim)
    if claims:
        rows = [
            [c.id, c.status.value, c.confidence.value, f"{c.predicate} = {c.value}"] for c in claims
        ]
        sections.append(
            f"<h2>Context claims ({len(claims)})</h2>"
            + _table(["Identifier", "Status", "Confidence", "Assertion"], rows)
        )
    return render_page("Context", assessment.id, "context", "".join(sections))


def render_workflow(handle: AssessmentHandle, assessment: Assessment) -> str:
    """Workflow progress: the runs and their execution records. Safe messages only, no content."""
    runs = handle.objects.list(WorkflowRun)
    records = handle.objects.list(ExecutionRecord)
    run_rows = [
        [
            run.id,
            run.status.value,
            "authoritative" if run.is_authoritative else "ablated: " + ", ".join(run.ablations),
            run.total_model_calls,
            f"{run.estimated_cost:.4f}" if run.estimated_cost else "—",
        ]
        for run in runs
    ]
    record_rows = [
        [rec.node_name, rec.execution_type.value, rec.status.value, rec.duration_ms or 0]
        for rec in records
    ]
    body = (
        f"<h2>Runs ({len(runs)})</h2>"
        + _table(["Run", "Status", "Authority", "Model calls", "Est. cost"], run_rows)
        + f"<h2>Executions ({len(records)})</h2>"
        + _table(["Node", "Type", "Status", "Duration (ms)"], record_rows)
    )
    return render_page("Workflow", assessment.id, "workflow", body)


def render_threats(handle: AssessmentHandle, assessment: Assessment) -> str:
    """The threats the analysis proposed, with the objects each is grounded in (#508).

    Previously reachable only through the report or the CLI; the read-only view now renders
    threats as a first-class page, DEC-078's read-only GET boundary unchanged.
    """
    threats = handle.objects.list(Threat)
    component_names = {c.id: c.name for c in handle.objects.list(Component)}
    asset_names = {a.id: a.name for a in handle.objects.list(Asset)}
    rows = [
        [
            threat.id,
            ", ".join(str(term) for term in threat.category) or "—",
            threat.status.value,
            threat.title,
            ", ".join(
                [
                    *(component_names.get(cid, cid) for cid in threat.affected_component_ids),
                    *(asset_names.get(aid, aid) for aid in threat.affected_asset_ids),
                ]
            )
            or "—",
        ]
        for threat in threats
    ]
    body = f"<h2>Threats ({len(threats)})</h2>" + _table(
        ["Identifier", "Category", "Status", "Title", "Grounded in"], rows
    )
    return render_page("Threats", assessment.id, "threats", body)


def render_ledger(handle: AssessmentHandle, assessment: Assessment) -> str:
    """Per-run, per-node spend from the execution records (#508, the view of DEC-092's ledger).

    Absent prints as a dash, never zero: an offline replay that captured no usage measured
    nothing, exactly as `trace ledger` shows it.
    """
    runs = handle.objects.list(WorkflowRun)
    records_by_run: dict[str, list[ExecutionRecord]] = {}
    for record in handle.objects.list(ExecutionRecord):
        if record.execution_type.value == "model":
            records_by_run.setdefault(record.workflow_run_id, []).append(record)

    def _sum(values: list[int | None]) -> object:
        reported = [v for v in values if v is not None]
        return sum(reported) if reported else "—"

    sections: list[str] = []
    for run in runs:
        nodes: dict[str, list[ExecutionRecord]] = {}
        for record in records_by_run.get(run.id, []):
            nodes.setdefault(record.node_name, []).append(record)
        rows = [
            [
                name,
                len(rows_),
                _sum([r.input_tokens for r in rows_]),
                _sum([r.cache_read_tokens for r in rows_]),
                _sum([r.output_tokens for r in rows_]),
            ]
            for name, rows_ in nodes.items()
        ]
        cost = f"{run.estimated_cost:.4f}" if run.estimated_cost is not None else "—"
        sections.append(
            f"<h2>{_e(run.id)} — {_e(run.status.value)} "
            f"({run.total_model_calls} calls, est. cost {_e(cost)})</h2>"
            + (
                _table(
                    ["Node", "Calls", "Input", "Cache read", "Output"],
                    rows,
                )
                if rows
                else '<p class="muted">No model-assisted executions recorded.</p>'
            )
        )
    body = "".join(sections) or '<p class="muted">No workflow run has started.</p>'
    return render_page("Ledger", assessment.id, "ledger", body)


def render_questions(handle: AssessmentHandle, assessment: Assessment) -> str:
    """Open questions and the reviewer decisions recorded against the assessment's objects."""
    questions = handle.objects.list(Question)
    decisions = handle.objects.list(ReviewerDecision)
    q_rows = [
        [q.id, "blocking" if q.blocking else q.priority.value, q.status.value, q.question]
        for q in questions
    ]
    d_rows = [
        [d.id, d.subject_type, d.subject_id, d.disposition.value, d.reviewer_id] for d in decisions
    ]
    body = (
        f"<h2>Open questions ({len(questions)})</h2>"
        + _table(["Identifier", "Priority", "Status", "Question"], q_rows)
        + f"<h2>Reviewer decisions ({len(decisions)})</h2>"
        + _table(["Identifier", "Subject type", "Subject", "Disposition", "Reviewer"], d_rows)
    )
    return render_page("Questions & decisions", assessment.id, "questions", body)


def render_findings(handle: AssessmentHandle, assessment: Assessment) -> str:
    """The findings, each linking to its lineage walk.

    With `evidence_age_threshold_days` configured, a stale-evidence column names how many of
    each finding's citations were captured past the threshold as of this request — a view is a
    point-in-time look, so the request's time is the honest anchor (DEC-118). Without the
    threshold the column is absent rather than zero: no policy is not a policy.
    """
    findings = handle.objects.list(Finding)
    threshold = assessment.configuration.evidence_age_threshold_days
    if not findings:
        body = '<p class="muted">No findings.</p>'
    else:
        references = {ref.id: ref for ref in handle.objects.list(EvidenceReference)}
        as_of = now()
        headers = ["Finding", "Severity", "Status", "Title", "Summary", "Evidence"]
        if threshold is not None:
            headers.append(f"Stale evidence (>{threshold}d)")
        rows = []
        for f in findings:
            row = [
                _link(f.id, f"/{assessment.id}/lineage/{f.id}", css="finding"),
                _e(f.severity.value),
                _e(f.status.value),
                _e(f.title),
                _e(f.summary),
                _e(len(f.evidence_ids)),
            ]
            if threshold is not None:
                stale = stale_evidence_ids(f, references, threshold_days=threshold, as_of=as_of)
                row.append(", ".join(stale) if stale else "none")
            rows.append(row)
        body = _table_raw(headers, rows)
    return render_page("Findings", assessment.id, "findings", body)


def render_lineage(handle: AssessmentHandle, assessment: Assessment, finding_id: str) -> str:
    """Why was this generated? One finding walked to its hashed evidence, link by link."""
    finding = handle.objects.find(Finding, finding_id)
    if finding is None:
        return render_page(
            "Lineage", assessment.id, "findings", '<p class="muted">No such finding.</p>'
        )
    lineage = finding_lineage(
        finding,
        threats=handle.objects.list(Threat),
        control_mappings=handle.objects.list(ControlMapping),
        evidence_assessments=handle.objects.list(EvidenceAssessment),
        critiques=handle.objects.list(Critique),
        context_claims=handle.objects.list(ContextClaim),
        evidence_references=handle.objects.list(EvidenceReference),
        source_documents=handle.objects.list(SourceDocument),
    )

    # The walk's hops, each a section with its own anchor so every hop is linkable and
    # screenshot-able (#533), and a contents line so the chain is navigated, not scrolled.
    hops: list[tuple[str, str, list[str]]] = [
        (
            "threats",
            "Threats",
            [
                f'<a id="{_e(t.id.lower())}"></a>{_link(t.id, f"/{assessment.id}/threats")}: '
                f"{_e(t.title)}"
                for t in lineage.threats
            ]
            + [f"requirement {_e(rid)}" for rid in finding.requirement_ids],
        ),
        (
            "mappings",
            "Control mappings",
            [
                f'<a id="{_e(m.id.lower())}"></a><code>{_e(m.id)}</code>: {_e(m.requirement_id)}'
                f" — {_e(m.satisfaction_status.value)}"
                for m in lineage.control_mappings
            ],
        ),
        (
            "assessments",
            "Evidence assessments",
            [
                f'<a id="{_e(a.id.lower())}"></a><code>{_e(a.id)}</code>: '
                f"{_e(a.subject_type.value)} {_e(a.subject_id)} — {_e(a.validation_status.value)}"
                for a in lineage.evidence_assessments
            ],
        ),
        (
            "critiques",
            "Critiques",
            [
                f'<a id="{_e(c.id.lower())}"></a><code>{_e(c.id)}</code>: '
                f"{_e(c.critique_type.value)} on {_e(c.subject_id)}"
                for c in lineage.critiques
            ],
        ),
        (
            "claims",
            "Context claims",
            [
                f'<a id="{_e(c.id.lower())}"></a><code>{_e(c.id)}</code>: {_e(c.predicate)} = '
                f"{_e(str(c.value))} ({_e(c.status.value)})"
                for c in lineage.context_claims
            ],
        ),
    ]
    contents = " · ".join(
        [f'<a href="#{slug}">{_e(label)}</a>' for slug, label, _ in hops]
        + ['<a href="#evidence">Evidence</a>', '<a href="#documents">Documents</a>']
    )
    parts: list[str] = [
        f"<h2>{_e(finding.id)} — {_e(finding.title)}</h2>",
        '<p class="muted">Severity '
        f"{_e(finding.severity.value)}, {_e(finding.status.value)}. "
        "The chain below is what the store holds, walked from the finding to the document hash; "
        "each excerpt is re-verified against its source as this page renders.</p>",
        f'<p class="muted">{contents}</p>',
        '<div class="lineage">',
    ]
    for slug, label, items in hops:
        parts.append(f'<a id="{slug}"></a>')
        parts.append(_lineage_block_html(label, items))

    parts.append('<a id="evidence"></a><h3>Evidence, quoted and re-verified</h3>')
    index = EvidenceIndex(handle)
    hashes = {doc.id: doc.content_hash for doc in lineage.source_documents}
    names = {doc.id: doc.filename for doc in lineage.source_documents}
    for reference in lineage.evidence_references:
        where = _location(reference)
        checked = index.verify(reference.id)
        verdict = (
            '<span class="ok">verifies</span>'
            if checked.ok
            else f'<span class="drift">{_e(checked.outcome.value)}</span>'
        )
        parts.append(
            f'<a id="{_e(reference.id.lower())}"></a><div class="excerpt">'
            f'<div class="label">[{UNTRUSTED_LABEL} — {_e(reference.id)}'
            f"{f', {_e(where)}' if where else ''}] · {verdict}</div>"
            f"<pre>{_e(reference.quoted_text)}</pre>"
            f'<div class="muted">{_e(names.get(reference.source_document_id, "?"))} · '
            f"<code>{_e(reference.content_hash)}</code></div></div>"
        )
    if lineage.source_documents:
        parts.append('<a id="documents"></a><h3>Source documents</h3>')
        parts.append(
            _table(
                ["Document", "Content hash"],
                [[names[d.id], hashes[d.id]] for d in lineage.source_documents],
            )
        )
    parts.append("</div>")
    return render_page("Lineage", assessment.id, "findings", "".join(parts))


def render_evaluation(scorecard_html: str | None) -> str:
    """The evaluation view: the scorecard, which is metrics and identifiers only (DEC-076).

    The boundary with this interface is recorded in DEC-076 — the scorecard shows measurements of
    the system, this interface shows an assessment's content; neither absorbs the other. The view
    embeds the committed scorecard rather than re-deriving it.
    """
    if scorecard_html is None:
        body = (
            '<p class="muted">No scorecard found. Generate it with '
            "<code>uv run python scripts/build_scorecard.py</code>.</p>"
        )
        return render_page("Evaluation", None, "evaluation", body)
    # The committed page is served byte-for-byte apart from one navigation line injected after
    # its <body>: without it the view was a dead end — the interface nav vanished and the
    # browser's back button was the only exit.
    back = '<p style="margin:0 0 1rem"><a href="/">&larr; assessments</a></p>'
    return scorecard_html.replace("<body>", f"<body>\n{back}", 1)


def render_lineage_index(handle: AssessmentHandle, assessment: Assessment) -> str:
    """The lineage entry page: pick the finding whose walk to read.

    The walk itself needs a finding identifier, and the differentiator view was unreachable from
    the navigation without this page — a presenter had to hand-type the deep link.
    """
    findings = handle.objects.list(Finding)
    if not findings:
        body = '<p class="muted">No findings to walk. The lineage view follows a finding back to its hashed evidence.</p>'
    else:
        rows = [
            [
                _link(f.id, f"/{assessment.id}/lineage/{f.id}", css="finding"),
                _e(f.severity.value),
                _e(f.title),
            ]
            for f in findings
        ]
        body = (
            "<p>Every finding links to its full walk: critique, evidence assessment, control "
            "mapping, threat, context claim, and the exact hashed excerpts underneath.</p>"
            + _table_raw(["Finding", "Severity", "Title"], rows)
        )
    return render_page("Lineage", assessment.id, "lineage", body)


def _type_label(class_name: str) -> str:
    """A stored class name as a reader-facing label: `ContextClaim` -> `Context claim`."""
    import re as _re

    spaced = _re.sub(r"(?<!^)(?=[A-Z])", " ", class_name)
    return spaced[0].upper() + spaced[1:].lower()


# -- helpers -----------------------------------------------------------------------------------


def _link(text: object, href: str, *, css: str | None = None) -> str:
    attr = f' class="{css}"' if css else ""
    return f'<a href="{_e(href)}"{attr}>{_e(text)}</a>'


def _table_raw(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """A table whose first cell is pre-rendered HTML (a link); other cells are escaped."""
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = [f"<td>{row[0]}</td>"] + [f"<td>{_e(cell)}</td>" for cell in row[1:]]
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'


def _lineage_block(heading: str, items: Sequence[str]) -> str:
    if not items:
        return f'<h3>{_e(heading)}</h3><p class="muted">none</p>'
    lines = "".join(f"<li>{_e(item)}</li>" for item in items)
    return f"<h3>{_e(heading)}</h3><ul>{lines}</ul>"


def _lineage_block_html(heading: str, items: Sequence[str]) -> str:
    """A hop section whose items are already rendered HTML (anchors and links included)."""
    if not items:
        return f'<h3>{_e(heading)}</h3><p class="muted">none</p>'
    lines = "".join(f"<li>{item}</li>" for item in items)
    return f"<h3>{_e(heading)}</h3><ul>{lines}</ul>"


def _location(reference: Any) -> str:
    if reference.start_line is not None:
        end = reference.end_line if reference.end_line is not None else reference.start_line
        return f"lines {reference.start_line}-{end}"
    if reference.json_pointer:
        return str(reference.json_pointer)
    return ""
