"""What the Report Generation agent sees: the approved analysis, rendered, and nothing raw.

`agent-design.md` section 19 gives this agent only approved or explicitly reportable objects, and
this module renders the assembled `ReportInput` (#104) into the prompt's `Input data` section.
Two properties are the design:

**No raw source excerpt is included.** The evidence appendix is the renderer's, quoted evidence is
never the agent's to restate (section 19's prohibited operations), and a package with no source
excerpts is a package the prompt-injection boundary never has to open a fence for. The approved
objects' free-text fields are schema-validated and reviewer-vetted application data; the prompt
still instructs that any instruction-shaped text inside them is data.

**The identifiers the agent may mention are enumerated.** Section 19 makes "an identifier is
cited that the input did not carry" a failure condition, and `referenceable_ids` is the set the
node checks the response against. An identifier is checkable only because the package knows
exactly what it contained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from trace_ai.services.report.input_assembly import ReportInput

__all__ = ["ReportPromptInput", "assemble_report_prompt_input"]

# Identifier-shaped tokens in prose: a generated identifier (`fnd-003`) or an authored
# requirement identifier (`req-AUTH-001`). Used by the node to find what the response mentions.
IDENTIFIER_SHAPE: Final = re.compile(r"\b[a-z]{2,4}-(?:[A-Z][A-Z0-9]*-)?\d+\b")


@dataclass(frozen=True, slots=True)
class ReportPromptInput:
    """The rendered input and the identifier set it carried."""

    rendered: str
    referenceable: frozenset[str]
    input_object_ids: tuple[str, ...]

    def substitutions(self) -> dict[str, str]:
        return {"input.report": self.rendered}


def _line(prefix: str, value: str | None) -> list[str]:
    return [f"{prefix}: {value}"] if value else []


def assemble_report_prompt_input(assembled: ReportInput) -> ReportPromptInput:
    """Render the approved state for the prompt, deterministically.

    Everything here restates objects the assembly already bounded — nothing is queried, so the
    agent and the renderer still read one assembly. Ordering follows the assembly's, which is by
    identifier throughout.
    """
    lines: list[str] = []
    referenceable: set[str] = set()

    assessment = assembled.assessment
    lines.append("### Assessment scope")
    lines.append(f"Assessment {assessment.id}: {assessment.name}")
    lines.extend(_line("Description", assessment.description))
    lines.append(
        f"Documents supplied: "
        f"{', '.join(document.filename for document in assembled.source_documents) or 'none'}"
    )
    referenceable.add(assessment.id)

    lines.append("")
    lines.append("### Approved system context")
    if assembled.system_context is None:
        lines.append("No approved system context revision exists.")
    else:
        for label, items in (
            ("Components", assembled.components),
            ("Actors", assembled.actors),
            ("Assets", assembled.assets),
            ("Data flows", assembled.data_flows),
            ("Trust boundaries", assembled.trust_boundaries),
        ):
            names = ", ".join(f"{getattr(item, 'name', item.id)} ({item.id})" for item in items)
            lines.append(f"{label}: {names or 'none'}")
            referenceable.update(item.id for item in items)

    lines.append("")
    lines.append("### Approved findings")
    if assembled.zero_approved_findings:
        lines.append(
            "No findings were approved. This is a stated result: no candidate weakness reached "
            "the assessment's bar. It is not a statement that the system is secure."
        )
    for finding in assembled.approved_findings:
        referenceable.add(finding.id)
        referenceable.update(finding.threat_ids)
        referenceable.update(finding.requirement_ids)
        lines.extend(
            [
                f"- {finding.id} [{finding.severity.value}] {finding.title}",
                f"  Summary: {finding.summary}",
                f"  Impact: {finding.impact}",
                f"  Recommendation: {finding.recommendation}",
            ]
        )
        if finding.assumptions:
            lines.append(f"  Assumptions: {'; '.join(finding.assumptions)}")
        if finding.limitations:
            lines.append(f"  Limitations: {'; '.join(finding.limitations)}")
        if finding.reviewer_notes:
            lines.append(f"  Reviewer notes: {finding.reviewer_notes}")

    lines.append("")
    lines.append("### Approved documentation gaps")
    for gap in assembled.approved_documentation_gaps:
        referenceable.add(gap.id)
        lines.append(f"- {gap.id} [{gap.severity.value}] {gap.title}: {gap.description}")
        lines.append(f"  Why it matters: {gap.importance}")
    if not assembled.approved_documentation_gaps:
        lines.append("None.")

    lines.append("")
    lines.append("### Open questions")
    for question in assembled.open_questions:
        referenceable.add(question.id)
        marker = "blocking" if question.blocking else question.priority.value
        lines.append(f"- {question.id} ({marker}): {question.question}")
    if not assembled.open_questions:
        lines.append("None.")

    lines.append("")
    lines.append("### Confirmed controls")
    for control in assembled.confirmed_controls:
        referenceable.add(control.id)
        lines.append(f"- {control.id} {control.name}: {control.description}")
    if not assembled.confirmed_controls:
        lines.append("None.")

    lines.append("")
    lines.append("### Required limitations")
    lines.append("Write exactly one limitation entry per identifier below, from its stated facts.")
    for limitation in assembled.required_limitations:
        lines.append(f"- {limitation.limitation_id}: {limitation.facts}")
        referenceable.add(limitation.limitation_id)
    if not assembled.required_limitations:
        lines.append("None: return an empty limitations list.")

    for threat in assembled.threats:
        referenceable.add(threat.id)

    return ReportPromptInput(
        rendered="\n".join(lines),
        referenceable=frozenset(referenceable),
        input_object_ids=tuple(
            sorted(
                {identifier for identifier in referenceable if not identifier.startswith("lim-")}
            )
        ),
    )
