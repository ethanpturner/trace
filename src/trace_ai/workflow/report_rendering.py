"""The Report Rendering node: the template applied to approved objects, with no model anywhere.

`agent-design.md` section 20's final line classifies this node as deterministic and model-free,
and the separation from the generation agent is the mechanism behind `design-principles.md`
section 17: structured analysis stays authoritative, and prose is a representation of it. This
module imports no model client, receives none, and depends on no module that constructs one.

**The template is followed, not reimplemented.** `templates/report-v1.md` is a structural
specification (DEC-035): this renderer reads it, substitutes the three marker forms — `agent.*`
with the validated `ReportSections` prose, `render.*` with blocks composed from approved objects,
`empty.*` with the template's own authored wording when a block has no rows — and emits the
result. Headings, numbering, anchors, ownership comments, and empty wording therefore come from
the artifact a person edits, and an edit there changes the report without touching this code.

**Quoted evidence is reproduced byte for byte.** `EvidenceReference.quoted_text` is verbatim from
the original document (DEC-015) and the appendix quotes it unaltered inside a fence; the location
line carries the source document and DEC-015's addressing.

**Two renders of identical approved state are identical apart from the timestamp.** Everything
rendered comes from the assembled input, which is ordered by identifier throughout; the one clock
read is the generated-at line, and it is a parameter so callers and tests can pin it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.enums import Severity

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.finding import Finding
    from trace_ai.domain.proposals.report_sections import ReportSections
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.report.input_assembly import ReportInput

__all__ = [
    "NODE_NAME",
    "NODE_VERSION",
    "RenderedReport",
    "render_report",
    "report_filename",
    "write_report",
]

NODE_NAME: Final = "report-rendering"
NODE_VERSION: Final = "0.1"

TEMPLATE_PATH: Final = PROJECT_ROOT / "templates" / "report-v1.md"

_MARKER: Final = re.compile(r"\{\{ (agent|render|empty)\.([a-z_]+) \}\}")

# Severity order for section 13: most severe first, then identifier. `unassigned` cannot occur —
# the approval gate refuses it — and sorts last if it ever did rather than crashing the render.
_SEVERITY_ORDER: Final = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFORMATIONAL: 4,
    Severity.UNASSIGNED: 5,
}


@dataclass(frozen=True, slots=True)
class RenderedReport:
    """One rendered report: the document and the name DEC-035 gives it."""

    markdown: str
    filename: str


def report_filename(workflow_run_id: str) -> str:
    """`report-<workflow_run_id>.md` (DEC-035): named per run, because the artifact store
    refuses to overwrite different content under a fixed name."""
    return f"report-{workflow_run_id}.md"


def _template_parts() -> tuple[str, dict[str, str]]:
    """The template body and its authored empty-section wording, parsed from the artifact.

    The body is everything before the trailing `---` separator, with the leading specification
    comment removed. The wording blocks after the separator are keyed by their `empty.*` name and
    emitted verbatim (DEC-035: none may be reworded at runtime).
    """
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    body, _, tail = text.rpartition("\n---\n")

    # Strip the leading spec comment: the template explains itself to editors, not to readers.
    if body.startswith("<!--"):
        body = body.split("-->", 1)[1].lstrip("\n")

    wording: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in tail.splitlines():
        heading = re.match(r"<!-- empty\.([a-z_]+) -->", line.strip())
        if heading:
            if current is not None:
                wording[current] = "\n".join(lines).strip()
            current = heading.group(1)
            lines = []
            continue
        if current is not None and not line.strip().startswith("<!--"):
            lines.append(line)
    if current is not None:
        wording[current] = "\n".join(lines).strip()

    return body, wording


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    cells = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows),
    ]
    return "\n".join(cells)


def _cell(value: str) -> str:
    """A value made safe for a table row: pipes escaped, newlines flattened."""
    return value.replace("|", "\\|").replace("\n", " ")


def _anchor(object_id: str) -> str:
    return f'<a id="{object_id.lower()}"></a>'


def _citation(reference: EvidenceReference, documents: dict[str, str]) -> str:
    """One evidence citation: source document, DEC-015 location, and the quoted text verbatim."""
    parts = [documents.get(reference.source_document_id, reference.source_document_id)]
    if reference.section_title:
        parts.append(reference.section_title)
    if reference.start_line is not None:
        end = reference.end_line if reference.end_line is not None else reference.start_line
        parts.append(f"lines {reference.start_line}-{end}")
    where = ", ".join(parts)
    return f"[{reference.id} — {where}]\n\n```\n{reference.quoted_text}\n```"


def _findings_block(
    findings: tuple[Finding, ...],
    references: dict[str, EvidenceReference],
    documents: dict[str, str],
) -> str:
    rendered: list[str] = []
    for finding in findings:
        lines = [
            _anchor(finding.id),
            f"### {finding.id}: {finding.title}",
            "",
            finding.summary,
            "",
            finding.description,
            "",
            f"- Severity: {finding.severity.value}",
            f"- Confidence: {finding.confidence.value}",
            f"- Validation status: {finding.validation_status.value}",
            f"- Affected components: {', '.join(finding.affected_component_ids) or 'none'}",
            f"- Affected assets: {', '.join(finding.affected_asset_ids) or 'none'}",
            f"- Impact: {finding.impact}",
            f"- Recommendation: {finding.recommendation}",
        ]
        if finding.assumptions:
            lines.append(f"- Assumptions: {'; '.join(finding.assumptions)}")
        if finding.limitations:
            lines.append(f"- Limitations: {'; '.join(finding.limitations)}")
        lines.append("")
        lines.append("Evidence:")
        lines.append("")
        for evidence_id in finding.evidence_ids:
            reference = references.get(evidence_id)
            if reference is None:
                lines.append(
                    f"[{evidence_id} — does not resolve to a stored passage; the finding "
                    f"cannot be verified from this report]"
                )
                continue
            lines.append(_citation(reference, documents))
            lines.append("")
        rendered.append("\n".join(lines).rstrip())
    return "\n\n".join(rendered)


def render_report(
    assembled: ReportInput,
    sections: ReportSections,
    *,
    generated_at: datetime | None = None,
) -> str:
    """Apply `templates/report-v1.md` to the approved input and the agent's four passages."""
    body, empty_wording = _template_parts()
    stamp = generated_at if generated_at is not None else now()
    assessment = assembled.assessment

    documents = {document.id: document.filename for document in assembled.source_documents}
    references = {reference.id: reference for reference in assembled.evidence_references}
    versions = assembled.versions

    by_action = sorted(
        assembled.approved_findings,
        key=lambda finding: (_SEVERITY_ORDER[finding.severity], finding.id),
    )

    render_blocks: dict[str, str] = {
        "assessment_name": assessment.name,
        "report_header": (
            f"Assessment {assessment.id} · generated {stamp.isoformat()} · "
            f"template {assembled.template}"
            + ("" if assembled.authoritative else " · NON-AUTHORITATIVE RUN (DEC-012)")
        ),
        "scope": "\n".join(
            [
                f"- Assessment: {assessment.id} — {assessment.name}",
                *([f"- Description: {assessment.description}"] if assessment.description else []),
                f"- Model profile: {assessment.configuration.model_profile}",
                f"- Threat methodology: {assessment.configuration.threat_methodology}",
                f"- Evidence threshold: {assessment.configuration.evidence_threshold.value}",
            ]
        ),
        "source_documents": _table(
            ["Document", "Identifier", "Ingestion status"],
            [
                [document.filename, document.id, document.ingestion_status.value]
                for document in assembled.source_documents
            ],
        ),
        "components": _table(
            ["Component", "Identifier", "Type", "Internet accessible"],
            [
                [
                    component.name,
                    component.id,
                    str(component.component_type),
                    str(component.internet_accessible),
                ]
                for component in assembled.components
            ],
        ),
        "actors": _table(
            ["Actor", "Identifier", "Type"],
            [[actor.name, actor.id, str(actor.actor_type)] for actor in assembled.actors],
        ),
        "data_flows": _table(
            ["Data flow", "Identifier", "From", "To", "Encryption in transit"],
            [
                [
                    flow.name,
                    flow.id,
                    flow.source_component_id,
                    flow.destination_component_id,
                    str(flow.encryption_in_transit),
                ]
                for flow in assembled.data_flows
            ],
        ),
        "assets": _table(
            ["Asset", "Identifier", "Type"],
            [[asset.name, asset.id, str(asset.asset_type)] for asset in assembled.assets],
        ),
        "trust_boundaries": _table(
            ["Trust boundary", "Identifier", "Type"],
            [
                [boundary.name, boundary.id, str(boundary.boundary_type)]
                for boundary in assembled.trust_boundaries
            ],
        ),
        "threats": "\n\n".join(
            f"{_anchor(threat.id)}\n### {threat.id}: {threat.title}\n\n"
            f"{threat.description}\n\nImpact: {threat.impact}"
            for threat in assembled.threats
        ),
        "findings": _findings_block(assembled.approved_findings, references, documents),
        "documentation_gaps": "\n\n".join(
            f"{_anchor(gap.id)}\n### {gap.id}: {gap.title}\n\n"
            f"It could not be determined from the documentation provided: {gap.description}\n\n"
            f"Why it matters: {gap.importance}"
            + (
                f"\n\nRequested evidence: {'; '.join(gap.requested_evidence)}"
                if gap.requested_evidence
                else ""
            )
            for gap in assembled.approved_documentation_gaps
        ),
        "assumptions": _table(
            ["Claim", "Status", "Statement", "Rationale"],
            [
                [
                    claim.id,
                    claim.status.value,
                    f"{claim.subject_id or claim.subject_type}: {claim.predicate}",
                    claim.rationale or "",
                ]
                for claim in assembled.assumption_claims
            ],
        ),
        "open_questions": "\n".join(
            f"- {question.id} "
            f"({'blocking' if question.blocking else question.priority.value}): "
            f"{question.question}"
            for question in assembled.open_questions
        ),
        "controls": "\n\n".join(
            f"{_anchor(control.id)}\n### {control.id}: {control.name}\n\n{control.description}"
            for control in assembled.confirmed_controls
        ),
        "recommended_actions": "\n".join(
            f"- [{finding.severity.value}] {finding.id}: {finding.recommendation}"
            + (
                f" Acceptance criteria: {'; '.join(finding.acceptance_criteria)}"
                if finding.acceptance_criteria
                else ""
            )
            for finding in by_action
        ),
        "methodology": (
            "This assessment was produced by Trace, a context-aware security architecture "
            "analysis pipeline: documents are ingested and indexed as evidence, an approved "
            "system context is extracted and reviewed at a human checkpoint, threats are "
            "analysed against it, requirements are mapped and their evidence validated, and "
            "findings are consolidated and approved at a second human checkpoint before this "
            "report is rendered. Model-assisted steps propose; deterministic validation and "
            "human review decide. Absence of documentation is never treated as proof of a "
            "vulnerability."
        ),
        "versions": "\n".join(
            [
                f"- Architecture version: {versions.architecture_version}",
                f"- Workflow version: {versions.workflow_version}",
                "- Prompt versions: "
                + (
                    ", ".join(f"{name} {value}" for name, value in versions.prompt_versions)
                    or "none"
                ),
                f"- Requirements catalog version: {versions.requirements_catalog_version}",
                f"- Model: {versions.model}",
                f"- Model configuration: {versions.model_configuration}",
            ]
        ),
        "evidence": "\n\n".join(
            f"{_anchor(reference.id)}\n{_citation(reference, documents)}"
            for reference in assembled.evidence_references
        ),
    }

    agent_blocks: dict[str, str] = {
        "executive_summary": sections.executive_summary,
        "system_overview": sections.system_overview,
        "risk_summary": sections.risk_summary,
        "limitations": "\n\n".join(
            f"- {entry.limitation_id}: {entry.text}" for entry in sections.limitations
        )
        or "No limitations were required by the run's state.",
    }

    def substitute(match: re.Match[str]) -> str:
        kind, name = match.group(1), match.group(2)
        if kind == "agent":
            return agent_blocks[name]
        if kind == "render":
            return render_blocks[name]
        return empty_wording[name] if not render_blocks.get(name) else ""

    rendered = _MARKER.sub(substitute, body)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.rstrip() + "\n"


def write_report(
    handle: AssessmentHandle,
    assembled: ReportInput,
    sections: ReportSections,
    *,
    workflow_run_id: str,
    generated_at: datetime | None = None,
) -> tuple[RenderedReport, Path]:
    """Render and store under the assessment's own `outputs/` area (DEC-035, section 5.16).

    The path comes from the `ArtifactStore`, which is bound to one assessment and refuses a path
    outside it — output cannot mix assessments because the API offers no way to.
    """
    report = RenderedReport(
        markdown=render_report(assembled, sections, generated_at=generated_at),
        filename=report_filename(workflow_run_id),
    )
    path = handle.artifacts.store_output(report.filename, report.markdown.encode("utf-8"))
    return report, path
