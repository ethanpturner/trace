"""Moving one outcome object across the Finding / DocumentationGap / Question boundary.

`agent-design.md` section 16 gives the reclassification rules and `data-model.md` section 4.6 gives
the reviewer `convert_to_question` and `convert_to_documentation_gap`. Both describe the move;
neither says what survives it. `design-principles.md` section 16 does: a reviewer must be able to
explain why a finding changed or disappeared.

**Nothing is fabricated.** Every field the target requires and the source does not carry is a
keyword argument with no default, so omitting one is a `TypeError` before anything is built, and
supplying an empty one is refused by name. That rule is what separates a conversion from a
rewrite. `DocumentationGap.importance` and `Question.rationale` are the obvious cases; the
interesting one is severity, because a `Finding` *has* a severity and its gap cannot use it —
findings are created `unassigned` (DEC-030) and a gap may never carry `unassigned` (DEC-045), so
the caller states the gap's rating rather than inheriting a value that means "nobody decided".

**Converting to a `Finding` is not an escape hatch.** `documentation_gap_to_finding` builds the
object through `Finding.model_validate` like everything else, so the minimum criteria and DEC-013's
outcome table both apply. A gap that became a finding without new evidence would be the DEC-009
collapse arriving through a helper.

**The source is superseded, never deleted** (section 2.6). The caller gets both objects back and
persists both; the source moves to `superseded` and stays retrievable, because a finding that
vanished is one nobody can be shown the history of.

**Lineage is one field and one walk.** `converted_from_id` (DEC-051) is cross-type, so
`conversion_chain` follows it across all three kinds. `supersedes_id` is DEC-023's same-type
mechanism for regeneration and does not reach here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.domain.base import now
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity, ValidationStatus
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from trace_ai.domain.base import DomainModel

__all__ = [
    "ConversionChainError",
    "conversion_chain",
    "documentation_gap_to_finding",
    "finding_to_documentation_gap",
    "finding_to_question",
]


class ConversionChainError(ValueError):
    """A `converted_from_id` points at nothing, or the chain closes on itself."""


def _required(**values: str) -> None:
    """Refuse a required target field the caller left blank.

    A `TypeError` already covers omitting the argument. This covers the other half — passing `""`
    or whitespace to satisfy the signature, which is how a placeholder gets into a required field
    without anyone deciding to put one there.
    """
    blank = sorted(name for name, value in values.items() if not value or not value.strip())
    if blank:
        raise ValueError(
            f"these fields are required on the converted object and were supplied blank: "
            f"{blank}. A conversion carries what the source establishes and asks for the rest; "
            f"it does not invent a placeholder."
        )


def _superseded(obj: Finding | DocumentationGap) -> Finding | DocumentationGap:
    """The source object, marked superseded and otherwise unchanged (section 2.6).

    Built with `model_validate` rather than `model_copy`: domain objects are frozen and this is a
    change re-entering the schema (`CLAUDE.md`).
    """
    return type(obj).model_validate({**obj.model_dump(), "status": ObjectStatus.SUPERSEDED})


def finding_to_documentation_gap(
    finding: Finding,
    *,
    gap_id: str,
    importance: str,
    severity: Severity,
    requested_evidence: Sequence[str] = (),
    generated_by: str,
) -> tuple[DocumentationGap, Finding]:
    """A finding the evidence does not carry becomes the gap it always was.

    Returns the gap and the superseded finding, in that order. Both are persisted by the caller.

    `severity` is the caller's because a finding's is `unassigned` until checkpoint 2 (DEC-030)
    and a gap may never be `unassigned` (DEC-045). Inheriting it would move a value meaning
    "nobody has decided" into a field where nobody ever will.
    """
    _required(importance=importance, generated_by=generated_by)

    gap = DocumentationGap.model_validate(
        {
            "id": gap_id,
            "assessment_id": finding.assessment_id,
            "title": finding.title,
            "description": finding.description,
            "importance": importance,
            # The threats, requirements, and mappings the finding rested on. A gap that dropped
            # them would be a gap nobody could trace to the analysis that raised it (section 32).
            "related_object_ids": [
                *finding.threat_ids,
                *finding.requirement_ids,
                *finding.control_mapping_ids,
                *finding.affected_component_ids,
                *finding.affected_asset_ids,
            ],
            "requested_evidence": list(requested_evidence),
            "severity": severity,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": generated_by,
            "evidence_ids": list(finding.evidence_ids),
            "converted_from_id": finding.id,
        }
    )
    return gap, _superseded(finding)  # type: ignore[return-value]


def finding_to_question(
    finding: Finding,
    *,
    question_id: str,
    question: str,
    rationale: str,
    priority: QuestionPriority,
    blocking: bool,
    generated_by: str,
) -> tuple[Question, Finding]:
    """A finding whose answer is obtainable becomes the question that would settle it.

    `blocking` has no default here for the reason `Question` gives it none: whether the workflow
    pauses is a property of the question, and a default would let an unset argument decide it.
    """
    _required(question=question, rationale=rationale, generated_by=generated_by)

    asked = Question.model_validate(
        {
            "id": question_id,
            "assessment_id": finding.assessment_id,
            "question": question,
            "rationale": rationale,
            # One related object, and the threat is the honest one: a question exists because a
            # scenario could not be settled. `Question` carries a single reference by section 22's
            # shape, so the rest of the lineage travels on `converted_from_id`.
            "related_object_type": "threat",
            "related_object_id": finding.threat_ids[0],
            "priority": priority,
            "blocking": blocking,
            "status": QuestionStatus.OPEN,
            "generated_by": generated_by,
            "converted_from_id": finding.id,
        }
    )
    return asked, _superseded(finding)  # type: ignore[return-value]


def documentation_gap_to_finding(
    gap: DocumentationGap,
    *,
    finding_id: str,
    summary: str,
    threat_ids: Sequence[str],
    requirement_ids: Sequence[str],
    control_mapping_ids: Sequence[str],
    affected_component_ids: Sequence[str],
    affected_asset_ids: Sequence[str],
    evidence_ids: Sequence[str],
    validation_status: ValidationStatus,
    impact: str,
    recommendation: str,
    confidence: ConfidenceLevel,
    generated_by: str,
    low_confidence_justification: str | None = None,
) -> tuple[Finding, DocumentationGap]:
    """A gap that later evidence supports becomes a finding — if it earns it.

    Almost every argument is required because almost nothing a finding needs is on a gap, and that
    asymmetry is the point: a gap records that something could not be determined, so converting it
    forward means someone determined it. `Finding.model_validate` runs the minimum criteria and
    DEC-013's outcome table, so a conversion cannot reach a finding the pipeline could not have
    reached directly.

    `evidence_ids` is a parameter rather than inherited from the gap. A gap's evidence shows
    ambiguity or contradiction (section 23); a finding's has to support the weakness, and those
    are not the same passages.
    """
    _required(
        summary=summary, impact=impact, recommendation=recommendation, generated_by=generated_by
    )

    stamped = now()
    finding = Finding.model_validate(
        {
            "id": finding_id,
            "assessment_id": gap.assessment_id,
            "title": gap.title,
            "summary": summary,
            "description": gap.description,
            "threat_ids": list(threat_ids),
            "requirement_ids": list(requirement_ids),
            "control_mapping_ids": list(control_mapping_ids),
            "affected_component_ids": list(affected_component_ids),
            "affected_asset_ids": list(affected_asset_ids),
            "evidence_ids": list(evidence_ids),
            "validation_status": validation_status,
            # DEC-030: created unassigned whatever the gap rated itself. A gap's severity rates
            # the gap and a finding's rates a weakness, and they are not the same quantity
            # (DEC-045), so carrying it across would be the misreading that entry warns about.
            "severity": Severity.UNASSIGNED,
            "impact": impact,
            "recommendation": recommendation,
            "confidence": confidence,
            "low_confidence_justification": low_confidence_justification,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": generated_by,
            "created_at": stamped,
            "updated_at": stamped,
            "converted_from_id": gap.id,
        }
    )
    return finding, _superseded(gap)  # type: ignore[return-value]


def conversion_chain(obj: DomainModel, objects: Iterable[DomainModel]) -> list[str]:
    """The identifiers this object was converted from, newest first, ending at the original.

    Cross-type by construction, which is why it walks identifiers rather than typed references.
    Raises on a broken or circular chain: both are states section 32's lineage requirement makes
    unacceptable, and returning a partial walk would present an incomplete history as a complete
    one.
    """
    by_id = {str(getattr(other, "id", "")): other for other in objects}
    chain = [str(getattr(obj, "id", ""))]
    current = obj

    while (source := getattr(current, "converted_from_id", None)) is not None:
        following = by_id.get(source)
        if following is None:
            raise ConversionChainError(
                f"{chain[-1]} was converted from {source!r}, which is not in this assessment. "
                f"A conversion whose source is gone is a history nobody can read (section 32)."
            )
        if following.id in chain:  # type: ignore[attr-defined]
            raise ConversionChainError(
                f"the conversion chain {[*chain, source]} closes on itself. No object in it is "
                f"the original."
            )
        chain.append(source)
        current = following

    return chain
