"""The report consistency validator: section 19's prohibitions, made deterministic.

`agent-design.md` section 19 prohibits the Report Generation agent from inventing findings,
changing severity, dropping limitations, presenting assumptions or questions as confirmed, and
altering quoted evidence — and `design-principles.md` section 7 puts a rule like that outside the
prompt. This module is the enforcement: it runs between generation and rendering over the
`ReportSections`, and again over the rendered document, uses no model, and never repairs prose —
a violation blocks, preserves the offending output, and routes to retry or review by its error
class (section 26).

**What the checks do and do not catch.** Every check here is conservative and lexical, by
design:

- *Invented findings* are caught as identifier-shaped tokens the approved input did not carry,
  and as approved finding titles misquoted with a different identifier. A weakness asserted in
  fresh words, naming nothing, is **not** caught here — that is semantic judgment, out of scope
  by the issue and the reviewer's to catch at the checkpoint before this ever runs.
- *Severity drift* is caught sentence-by-sentence: a sentence naming exactly one approved finding
  and a severity word that is not that finding's severity fails. A severity implied without the
  vocabulary is not caught.
- *Gaps and questions presented as weaknesses* are caught the same way: a sentence naming a gap
  or open question together with confirmed-weakness vocabulary fails. This is the DEC-009
  boundary surviving into the output, and the last place it can be enforced.
- *Altered quotes* are caught as quotation-marked spans that match no stored `quoted_text`
  verbatim, and — over the rendered document — as any cited reference whose stored text does not
  appear byte for byte.

**The unsupported-statement count is a metric, not just a verdict.** `metrics()` emits
`unsupported_claim_count` under the exact name `data-model.md` section 28 lists, which is the
form the evaluation component consumes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.enums import Severity
from trace_ai.services.report.prompt_input import (
    IDENTIFIER_SHAPE,
    assemble_report_prompt_input,
)
from trace_ai.workflow.errors import ErrorClass

if TYPE_CHECKING:
    from trace_ai.domain.proposals.report_sections import ReportSections
    from trace_ai.services.report.input_assembly import ReportInput

__all__ = [
    "ReportValidationOutcome",
    "ReportViolation",
    "validate_rendered_report",
    "validate_report_sections",
]

_SEVERITY_WORDS: Final = "|".join(
    sorted({member.value for member in Severity} - {Severity.UNASSIGNED.value})
)

# A severity *statement*, not a bare adjective: "high severity", "severity: high", "severity is
# high". Bare vocabulary words carry too many ordinary meanings — "low confidence", "medium-sized"
# — and a validator that flagged them would train the agent to avoid plain words rather than to
# report severity faithfully.
_SEVERITY_STATED: Final = re.compile(
    rf"\b(?P<before>{_SEVERITY_WORDS})[-\s]severity\b"
    rf"|\bseverity(?:\s+is|\s+of|:)?\s+(?P<after>{_SEVERITY_WORDS})\b",
    re.IGNORECASE,
)

# The vocabulary that asserts a confirmed weakness. Conservative and lowercase; matched against
# casefolded sentences.
_WEAKNESS_WORDS: Final = ("vulnerab", "exploitable", "confirmed weakness", "is insecure")

_SENTENCES: Final = re.compile(r"[.!?]\s+|\n")
_QUOTED_SPAN: Final = re.compile(r"[\"“]([^\"“”]{20,})[\"”]")
_MINIMUM_QUOTE_FRAGMENT: Final = 30


@dataclass(frozen=True, slots=True)
class ReportViolation:
    """One prohibited operation, detected. The prose is never repaired."""

    check: str
    message: str
    error_class: ErrorClass = ErrorClass.SCHEMA_VALIDATION_FAILURE


@dataclass(frozen=True, slots=True)
class ReportValidationOutcome:
    """The violations, and the count the evaluation component consumes."""

    violations: tuple[ReportViolation, ...] = ()
    unsupported_statement_count: int = 0

    @property
    def valid(self) -> bool:
        return not self.violations

    def metrics(self) -> dict[str, int]:
        """Section 28's metric, under its listed name."""
        return {"unsupported_claim_count": self.unsupported_statement_count}

    def feedback(self) -> str:
        """What a retry is told (section 26: feedback or it is a repetition)."""
        return "\n".join(f"- {violation.message}" for violation in self.violations)


def _prose_fields(sections: ReportSections) -> list[tuple[str, str]]:
    return [
        ("executive_summary", sections.executive_summary),
        ("system_overview", sections.system_overview),
        ("risk_summary", sections.risk_summary),
        *((f"limitations[{e.limitation_id}]", e.text) for e in sections.limitations),
    ]


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCES.split(text) if sentence.strip()]


def validate_report_sections(
    assembled: ReportInput, sections: ReportSections
) -> ReportValidationOutcome:
    """Check the agent's four passages against the approved input. Deterministic; no model."""
    package = assemble_report_prompt_input(assembled)
    approved_ids = {finding.id for finding in assembled.approved_findings}
    severity_by_id = {finding.id: finding.severity.value for finding in assembled.approved_findings}
    gap_ids = {gap.id for gap in assembled.approved_documentation_gaps}
    question_ids = {question.id for question in assembled.open_questions}
    quoted_texts = [reference.quoted_text for reference in assembled.evidence_references]

    violations: list[ReportViolation] = []
    unsupported = 0

    for field_name, text in _prose_fields(sections):
        for token in IDENTIFIER_SHAPE.findall(text):
            if token not in package.referenceable:
                unsupported += 1
                violations.append(
                    ReportViolation(
                        check="unknown_identifier",
                        message=(
                            f"{field_name} mentions {token!r}, which the approved input does "
                            f"not carry. A statement about an object the input did not supply "
                            f"is an invented conclusion (agent-design.md section 19)."
                        ),
                        error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                    )
                )

        for sentence in _sentences(text):
            lowered = sentence.casefold()
            named = [fid for fid in approved_ids if fid in sentence]
            if len(named) == 1:
                stated = [
                    (match.group("before") or match.group("after")).casefold()
                    for match in _SEVERITY_STATED.finditer(sentence)
                ]
                actual = severity_by_id[named[0]]
                if stated and actual not in stated:
                    violations.append(
                        ReportViolation(
                            check="severity_drift",
                            message=(
                                f"{field_name} states severity {stated} for {named[0]}, whose "
                                f"reviewer-assigned severity is {actual!r}. Severity is never "
                                f"the agent's to change (DEC-030)."
                            ),
                        )
                    )

            for gap_id in gap_ids:
                if gap_id in sentence and any(word in lowered for word in _WEAKNESS_WORDS):
                    violations.append(
                        ReportViolation(
                            check="dec_009_gap_as_weakness",
                            message=(
                                f"{field_name} presents {gap_id} with confirmed-weakness "
                                f"language. A documentation gap means it could not be "
                                f"determined whether a control exists; presenting it as a "
                                f"weakness is the DEC-009 collapse in the output."
                            ),
                        )
                    )
            for question_id in question_ids:
                if question_id in sentence and any(word in lowered for word in _WEAKNESS_WORDS):
                    violations.append(
                        ReportViolation(
                            check="question_as_vulnerability",
                            message=(
                                f"{field_name} presents open question {question_id} as a "
                                f"vulnerability. A question is unanswered, not confirmed "
                                f"(agent-design.md section 19)."
                            ),
                        )
                    )

        for span in _QUOTED_SPAN.findall(text):
            if any(span in quoted for quoted in quoted_texts):
                continue
            if any(
                span[:_MINIMUM_QUOTE_FRAGMENT] in quoted or quoted[:_MINIMUM_QUOTE_FRAGMENT] in span
                for quoted in quoted_texts
                if len(quoted) >= _MINIMUM_QUOTE_FRAGMENT
            ):
                violations.append(
                    ReportViolation(
                        check="altered_quote",
                        message=(
                            f"{field_name} quotes evidence in altered form: {span[:60]!r}... "
                            f"does not match any stored quoted_text verbatim. Quoted evidence "
                            f"is never altered (agent-design.md section 19, DEC-015)."
                        ),
                    )
                )

    try:
        sections.check_required(
            [limitation.limitation_id for limitation in assembled.required_limitations]
        )
    except ValueError as mismatch:
        violations.append(ReportViolation(check="limitation_set", message=str(mismatch)))

    return ReportValidationOutcome(
        violations=tuple(violations), unsupported_statement_count=unsupported
    )


def validate_rendered_report(assembled: ReportInput, markdown: str) -> ReportValidationOutcome:
    """Check the rendered document against the approved objects. Deterministic; no model."""
    approved_ids = {finding.id for finding in assembled.approved_findings}
    violations: list[ReportViolation] = []

    headings = re.findall(r"^### (fnd-\S+):", markdown, flags=re.MULTILINE)
    if len(headings) != len(approved_ids):
        violations.append(
            ReportViolation(
                check="finding_count",
                message=(
                    f"the document renders {len(headings)} finding entries and the approved "
                    f"set has {len(approved_ids)}. Every approved finding appears exactly "
                    f"once, and nothing else appears at all."
                ),
            )
        )

    for token in set(re.findall(r"\bfnd-[A-Za-z0-9-]*\d\b", markdown)):
        if token not in approved_ids:
            violations.append(
                ReportViolation(
                    check="unapproved_finding_identifier",
                    message=(
                        f"the document mentions {token!r}, which is not an approved finding. "
                        f"Rejected, deferred, and provisional candidates appear nowhere in "
                        f"the report (agent-design.md section 18)."
                    ),
                )
            )

    for finding in assembled.approved_findings:
        anchor = f'<a id="{finding.id}"></a>'
        if anchor not in markdown:
            continue  # already counted by finding_count
        entry = markdown.split(anchor, 1)[1].split("<a id=", 1)[0]
        stated = re.search(r"- Severity: (\S+)", entry)
        if stated and stated.group(1) != finding.severity.value:
            violations.append(
                ReportViolation(
                    check="severity_drift",
                    message=(
                        f"the document states severity {stated.group(1)!r} for {finding.id}, "
                        f"whose reviewer-assigned severity is {finding.severity.value!r}."
                    ),
                )
            )
        for label, entries in (
            ("limitation", finding.limitations),
            ("assumption", finding.assumptions),
        ):
            for recorded in entries:
                if recorded not in markdown:
                    violations.append(
                        ReportViolation(
                            check="omitted_limitation",
                            message=(
                                f"the {label} recorded on {finding.id} — {recorded!r} — does "
                                f"not appear in the document. The agent and the renderer may "
                                f"not remove material limitations (section 19)."
                            ),
                        )
                    )

    for reference in assembled.evidence_references:
        if reference.quoted_text not in markdown:
            violations.append(
                ReportViolation(
                    check="altered_quote",
                    message=(
                        f"{reference.id}'s stored quoted_text does not appear byte for byte "
                        f"in the document. Quoted evidence is reproduced unaltered "
                        f"(DEC-015)."
                    ),
                )
            )

    return ReportValidationOutcome(violations=tuple(violations))
