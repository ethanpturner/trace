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
from trace_ai.services.findings.lineage import finding_lineage

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Any

    from trace_ai.domain.assessment import Assessment
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "VIEWS",
    "render_context",
    "render_evaluation",
    "render_findings",
    "render_index",
    "render_lineage",
    "render_overview",
    "render_page",
    "render_questions",
    "render_workflow",
]

UNTRUSTED_LABEL = "quoted untrusted source content"

# The seven Stage 5 views, in navigation order: label and the path segment each renders at.
VIEWS: tuple[tuple[str, str], ...] = (
    ("Overview", "overview"),
    ("Context", "context"),
    ("Workflow", "workflow"),
    ("Questions & decisions", "questions"),
    ("Findings", "findings"),
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
                a.final_report_path is not None,
            ]
            for a in assessments
        ]
        body = _table_raw(["Assessment", "Name", "Status", "Report"], rows)
    return render_page("Read-only view", None, "", body)


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
        + _table(["Type", "Count"], sorted(counts.items()))
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
            run.estimated_cost or 0,
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
    """The findings, each linking to its lineage walk."""
    findings = handle.objects.list(Finding)
    if not findings:
        body = '<p class="muted">No findings.</p>'
    else:
        rows = [
            [
                _link(f.id, f"/{assessment.id}/lineage/{f.id}", css="finding"),
                f.severity.value,
                f.status.value,
                f.title,
            ]
            for f in findings
        ]
        body = _table_raw(["Finding", "Severity", "Status", "Title"], rows)
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

    parts: list[str] = [
        f"<h2>{_e(finding.id)} — {_e(finding.title)}</h2>",
        '<p class="muted">Severity '
        f"{_e(finding.severity.value)}, {_e(finding.status.value)}. "
        "The chain below is what the store holds, walked from the finding to the document hash.</p>",
        '<div class="lineage">',
        _lineage_block(
            "Requirements & threats",
            [f"threat {t.id}: {t.title}" for t in lineage.threats]
            + [f"requirement {rid}" for rid in finding.requirement_ids],
        ),
        _lineage_block(
            "Control mappings",
            [
                f"{m.id}: {m.requirement_id} — {m.satisfaction_status.value}"
                for m in lineage.control_mappings
            ],
        ),
        _lineage_block(
            "Evidence assessments",
            [
                f"{a.id}: {a.subject_type.value} {a.subject_id} — {a.validation_status.value}"
                for a in lineage.evidence_assessments
            ],
        ),
        _lineage_block(
            "Critiques",
            [f"{c.id}: {c.critique_type.value} on {c.subject_id}" for c in lineage.critiques],
        ),
        _lineage_block(
            "Context claims",
            [
                f"{c.id}: {c.predicate} = {c.value} ({c.status.value})"
                for c in lineage.context_claims
            ],
        ),
    ]
    parts.append("<h3>Evidence, quoted from the source documents</h3>")
    hashes = {doc.id: doc.content_hash for doc in lineage.source_documents}
    names = {doc.id: doc.filename for doc in lineage.source_documents}
    for reference in lineage.evidence_references:
        where = _location(reference)
        parts.append(
            '<div class="excerpt">'
            f'<div class="label">[{UNTRUSTED_LABEL} — {_e(reference.id)}'
            f"{f', {_e(where)}' if where else ''}]</div>"
            f"<pre>{_e(reference.quoted_text)}</pre>"
            f'<div class="muted">{_e(names.get(reference.source_document_id, "?"))} · '
            f"<code>{_e(reference.content_hash)}</code></div></div>"
        )
    if lineage.source_documents:
        parts.append("<h3>Source documents</h3>")
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
    return scorecard_html


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


def _location(reference: Any) -> str:
    if reference.start_line is not None:
        end = reference.end_line if reference.end_line is not None else reference.start_line
        return f"lines {reference.start_line}-{end}"
    if reference.json_pointer:
        return str(reference.json_pointer)
    return ""
