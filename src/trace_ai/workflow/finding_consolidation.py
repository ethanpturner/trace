"""The Finding Consolidation node: where "quality over volume" stops being an instruction.

`agent-design.md` section 16 classifies this as primarily deterministic — a model may assist
semantic comparison, but deterministic rules control object creation and status transitions. This
implementation uses no model at all, because every rule it applies is already written down:
DEC-013's outcome table decides what each mapping produces, section 16's reclassification rules
decide between a question and a gap, and section 21's minimum criteria decide whether a finding is
constructible.

**There is no quota, floor, ceiling, or target count anywhere in this module.** That is an
acceptance criterion rather than a preference, and it is checkable by reading: nothing here counts
outputs and compares the count to anything. `design-principles.md` section 9 and
`evaluation-plan.md` section 20 both say the goal is the smallest set of defensible conclusions,
and a floor would contradict it in the one place it would do the most damage.

**A zero-finding assessment is a success.** Not a warning, not an empty result, not a reason to
retry. `agent-design.md` section 26 makes insufficient evidence a non-retryable condition for the
general case, and this node is where the general case usually lands.

**The DEC-009 separation is enforced by construction, twice over.** A mapping resolving to
`unverified` reaches `Outcome.GAP_OR_QUESTION` under every validation status, so no route from
silence to a finding exists in the routing. And even if one did, `Finding` refuses a validation
status DEC-013's table produces no finding from. Neither check is this module's own opinion.

**A contradiction is asked about, never resolved.** `forgeflow-scenario.md` section 16.1 states the
requirement in those words: Trace must not silently choose the safer statement. An assessment
carrying contradictions produces a question ahead of every other routing rule, because picking
either statement would be a conclusion nobody drew.

**Titles are derived, not written.** The same input produces byte-identical titles across runs,
because a title that drifted would make two runs incomparable for evaluation and would make the
same finding look new every time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.base import now
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity, ValidationStatus
from trace_ai.domain.evidence_assessment import EvidenceAssessment, Recommendation, SubjectType
from trace_ai.domain.finding import Finding
from trace_ai.domain.outcomes import Outcome, outcome_for
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.services.findings.fingerprints import (
    component_name_index,
    fingerprinted_finding,
    fingerprinted_gap,
    gap_identity_indexes,
)
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.threat import Threat
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "NODE_NAME",
    "NODE_VERSION",
    "ConsolidationOutcome",
    "RejectedCandidate",
    "consolidate",
    "finding_title",
    "persist_consolidation",
]

NODE_NAME: Final = "finding-consolidation"
NODE_VERSION: Final = "0.1"

# What `generated_by` records on everything this node creates.
GENERATED_BY: Final = f"{NODE_NAME}-v1"

_WHITESPACE: Final = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class RejectedCandidate:
    """A mapping that produced no output, and why.

    Section 18 says rejected candidates may remain available in debug and evaluation views, and
    `design-principles.md` section 9 is why they are kept at all: a reviewer asking "why is this
    not a finding" needs an answer that is not silence.

    Held on the outcome rather than persisted as an object of its own. Issue #103 owns retention,
    and inventing a model here would decide that issue's design from the wrong end.
    """

    mapping_id: str
    requirement_id: str
    threat_id: str
    outcome: Outcome
    reason: str


@dataclass(frozen=True, slots=True)
class ConsolidationOutcome:
    """What one consolidation pass produced.

    Five collections and no count of any of them is compared to anything. `rejected` is not a
    failure list: most of it is `Outcome.NO_OUTPUT`, which is what a satisfied or inapplicable
    requirement produces and is the ordinary case.
    """

    findings: tuple[Finding, ...] = ()
    questions: tuple[Question, ...] = ()
    documentation_gaps: tuple[DocumentationGap, ...] = ()
    rejected: tuple[RejectedCandidate, ...] = ()
    downgraded_mappings: tuple[ControlMapping, ...] = ()
    """Mappings this pass lowered to `unverified` under DEC-013's conditions 2 and 3 — the half
    DEC-046 assigned here because `EvidenceAssessment` does not exist when Mapping Validation
    runs. Each carries the appended `downgrade_reason` entry (DEC-055) and is persisted under
    its existing identifier."""

    @property
    def object_ids(self) -> list[str]:
        return [
            *(finding.id for finding in self.findings),
            *(question.id for question in self.questions),
            *(gap.id for gap in self.documentation_gaps),
        ]


def finding_title(threat: Threat, mapping: ControlMapping) -> str:
    """A title derived from the threat and the requirement, stable across runs.

    Derived rather than authored so that two runs over identical input produce identical titles.
    An authored title would drift, and a drifting title makes the same finding look new to every
    comparison — which is what `evaluation-plan.md` needs matching on requirement and affected
    component to work around.

    Whitespace is collapsed and the result is stripped, so a reflowed threat title does not change
    the finding's.
    """
    collapsed = _WHITESPACE.sub(" ", threat.title).strip()
    return f"{collapsed} ({mapping.requirement_id})"


def _assessment_for(
    mapping: ControlMapping, assessments: Sequence[EvidenceAssessment]
) -> EvidenceAssessment | None:
    """The evidence assessment over this mapping, if evidence validation produced one."""
    for assessed in assessments:
        if (
            assessed.subject_type is SubjectType.CONTROL_MAPPING
            and assessed.subject_id == mapping.id
        ):
            return assessed
    return None


def _question_or_gap(assessed: EvidenceAssessment | None) -> Outcome | Recommendation:
    """Section 16's split, decided deterministically.

    Section 16 uses a question where the answer could materially change the assessment and is
    obtainable, and a gap where the primary issue is inability to verify. Neither is decidable
    from a mapping alone, so the rule reads what the evidence step already concluded:

    - A contradiction is asked about. Two documents disagreeing is not the same situation as
      silence, and collapsing it into a gap would lose that the documentation is inconsistent.
    - The agent's `recommendation` is consulted where it made one (DEC-047). It is advisory and
      this is the one place it is acted on, which is what makes it comparable to the outcome.
    - `missing_evidence` naming something specific means the answer is obtainable, which is
      section 16's own test for a question.
    - Otherwise a gap, because it asserts the least: that this could not be determined.
    """
    if assessed is None:
        return Recommendation.DOCUMENTATION_GAP

    if assessed.contradictions or assessed.validation_status is ValidationStatus.CONTRADICTED:
        return Recommendation.DOWNGRADE_TO_QUESTION

    if assessed.recommendation in {
        Recommendation.DOWNGRADE_TO_QUESTION,
        Recommendation.DOCUMENTATION_GAP,
    }:
        return assessed.recommendation

    if assessed.missing_evidence:
        return Recommendation.DOWNGRADE_TO_QUESTION

    return Recommendation.DOCUMENTATION_GAP


def _as_clause(entry: str) -> str:
    """A missing-evidence entry as a mid-sentence clause (#430).

    Agents write entries as sentences — leading capital, trailing period — and interpolating one
    into "Can you confirm ...?" produced "Can you confirm The webhook validation mechanism.?" in
    a section the reviewer reads line by line. The trailing period is stripped and the leading
    capital lowered, unless the first word is an acronym (second letter also upper), which
    lowering would mangle.
    """
    text = entry.strip().rstrip(".")
    if len(text) >= 2 and text[0].isupper() and text[1].islower():
        return text[0].lower() + text[1:]
    return text


def _downgraded(mapping: ControlMapping, assessed: EvidenceAssessment | None) -> ControlMapping:
    """The mapping lowered to `unverified`, with the record appended (DEC-046, DEC-055).

    `downgrade_reason` is appended to and never overwritten: two nodes can each lower a
    conclusion for different reasons, and overwriting would leave the record claiming the second
    reason was the only one. `downgraded_from` is first-writer — it records what the agent
    proposed, and a second downgrade does not change what was proposed.
    """
    status = assessed.validation_status.value if assessed is not None else "not_evaluated"
    entry = (
        f"{NODE_NAME}: the evidence assessment is {status!r}, not supported or "
        f"partially_supported, so the conclusion does not meet DEC-013's evidence conditions"
    )
    return ControlMapping.model_validate(
        {
            **mapping.model_dump(),
            "satisfaction_status": SatisfactionStatus.UNVERIFIED,
            "downgraded_from": mapping.downgraded_from or mapping.satisfaction_status,
            "downgrade_reason": (
                f"{mapping.downgrade_reason}; {entry}" if mapping.downgrade_reason else entry
            ),
        }
    )


def _reason(outcome: Outcome, mapping: ControlMapping) -> str:
    """Why a mapping produced nothing, in terms a reviewer can act on."""
    if mapping.applicability_status is ApplicabilityStatus.NOT_APPLICABLE:
        return f"{mapping.requirement_id} does not apply: {mapping.applicability_reason}"
    if outcome is Outcome.NO_OUTPUT:
        return (
            f"{mapping.requirement_id} is {mapping.satisfaction_status.value} and the evidence "
            f"carries it, or the mapping was never evaluated. Neither is a weakness."
        )
    return (
        f"{mapping.requirement_id} asserted more than its evidence carries and was lowered to "
        f"unverified (DEC-013). What the documentation does establish is recorded elsewhere."
    )


def consolidate(
    *,
    threats: Sequence[Threat],
    mappings: Sequence[ControlMapping],
    assessments: Sequence[EvidenceAssessment] = (),
    allocate: object = None,
    assessment_id: str,
    next_id: dict[str, int] | None = None,
) -> ConsolidationOutcome:
    """Route every mapping through DEC-013's table and build what it produces.

    `next_id` is a per-prefix counter the caller supplies when it wants deterministic identifiers
    without a store — the tests use it. In the workflow the identifiers come from the repository's
    allocator (DEC-018), which `persist_consolidation` uses.

    Nothing here counts an output and compares it to anything.
    """
    counters = next_id if next_id is not None else {}

    def mint(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}-{counters[prefix]:03d}"

    by_threat = {threat.id: threat for threat in threats}
    stamped = now()

    findings: list[Finding] = []
    questions: list[Question] = []
    gaps: list[DocumentationGap] = []
    rejected: list[RejectedCandidate] = []
    downgraded: list[ControlMapping] = []

    for mapping in mappings:
        threat = by_threat.get(mapping.threat_id)
        if threat is None:
            # A mapping whose threat is not in the set was not validated against this run's
            # threats. It is reported rather than routed, because routing it would build an
            # object citing a threat nobody supplied.
            rejected.append(
                RejectedCandidate(
                    mapping_id=mapping.id,
                    requirement_id=mapping.requirement_id,
                    threat_id=mapping.threat_id,
                    outcome=Outcome.NO_OUTPUT,
                    reason=f"threat {mapping.threat_id} is not in this run's validated set",
                )
            )
            continue

        assessed = _assessment_for(mapping, assessments)
        validation = (
            assessed.validation_status if assessed is not None else ValidationStatus.NOT_EVALUATED
        )
        outcome = outcome_for(mapping.satisfaction_status, validation)

        if outcome is Outcome.PROVISIONAL_FINDING:
            findings.append(
                _build_finding(
                    mapping=mapping,
                    threat=threat,
                    assessed=assessed,
                    finding_id=mint("fnd"),
                    assessment_id=assessment_id,
                    stamped=stamped,
                )
            )
            continue

        if outcome is Outcome.GAP_OR_QUESTION:
            if _question_or_gap(assessed) is Recommendation.DOWNGRADE_TO_QUESTION:
                questions.append(
                    _build_question(
                        mapping=mapping,
                        threat=threat,
                        assessed=assessed,
                        question_id=mint("qst"),
                        assessment_id=assessment_id,
                    )
                )
            else:
                gaps.append(
                    _build_gap(
                        mapping=mapping,
                        threat=threat,
                        assessed=assessed,
                        gap_id=mint("gap"),
                        assessment_id=assessment_id,
                    )
                )
            continue

        if outcome in {Outcome.DOWNGRADE_ONLY, Outcome.QUESTION_AFTER_DOWNGRADE}:
            # DEC-046's second half, performed where it said it would be: conditions 2 and 3
            # read the EvidenceAssessment, which exists by this phase, and the mapping is
            # lowered with the record appended (DEC-055).
            lowered = _downgraded(mapping, assessed)
            downgraded.append(lowered)
            if outcome is Outcome.QUESTION_AFTER_DOWNGRADE:
                # The table names the question: the conclusion asserted more than its evidence
                # carries, and the resulting uncertainty is asked about rather than dropped.
                questions.append(
                    _build_question(
                        mapping=lowered,
                        threat=threat,
                        assessed=assessed,
                        question_id=mint("qst"),
                        assessment_id=assessment_id,
                    )
                )
                continue

        rejected.append(
            RejectedCandidate(
                mapping_id=mapping.id,
                requirement_id=mapping.requirement_id,
                threat_id=mapping.threat_id,
                outcome=outcome,
                reason=_reason(outcome, mapping),
            )
        )

    return ConsolidationOutcome(
        findings=tuple(findings),
        questions=tuple(questions),
        documentation_gaps=tuple(gaps),
        rejected=tuple(rejected),
        downgraded_mappings=tuple(downgraded),
    )


def _build_finding(
    *,
    mapping: ControlMapping,
    threat: Threat,
    assessed: EvidenceAssessment | None,
    finding_id: str,
    assessment_id: str,
    stamped: object,
) -> Finding:
    """One provisional finding, created `unassigned` (DEC-030).

    Confidence is the mapping's rather than the assessment's: the mapping is the conclusion, and
    the assessment says whether the evidence carries it. Where the mapping is low-confidence the
    justification is required, and it is derived from what the evidence step said rather than
    invented — which is why `assessed.rationale` is used and a mapping with no assessment cannot
    reach here at all.
    """
    confidence = mapping.confidence
    justification = (
        assessed.rationale if confidence is ConfidenceLevel.LOW and assessed is not None else None
    )

    return Finding.model_validate(
        {
            "id": finding_id,
            "assessment_id": assessment_id,
            "title": finding_title(threat, mapping),
            "summary": (
                f"{mapping.requirement_id} is {mapping.satisfaction_status.value} for {threat.id}."
            ),
            "description": mapping.applicability_reason,
            "threat_ids": [threat.id],
            "requirement_ids": [mapping.requirement_id],
            "control_mapping_ids": [mapping.id],
            "affected_component_ids": list(threat.affected_component_ids),
            "affected_asset_ids": list(threat.affected_asset_ids),
            "evidence_ids": list(mapping.evidence_ids),
            "validation_status": assessed.validation_status
            if assessed is not None
            else ValidationStatus.NOT_EVALUATED,
            "severity": Severity.UNASSIGNED,
            "impact": threat.impact,
            "recommendation": (
                f"Establish whether {mapping.requirement_id} is met for {threat.id}, and record "
                f"the control that meets it."
            ),
            "assumptions": list(mapping.assumptions),
            "confidence": confidence,
            "low_confidence_justification": justification,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": GENERATED_BY,
            "created_at": stamped,
            "updated_at": stamped,
        }
    )


def _build_question(
    *,
    mapping: ControlMapping,
    threat: Threat,
    assessed: EvidenceAssessment | None,
    question_id: str,
    assessment_id: str,
) -> Question:
    """A question, phrased for a person, about what the documentation did not settle."""
    wanted = (
        "; ".join(_as_clause(entry) for entry in assessed.missing_evidence)
        if assessed is not None and assessed.missing_evidence
        else f"whether {mapping.requirement_id} is met"
    )
    contradicted = assessed is not None and (
        assessed.contradictions or assessed.validation_status is ValidationStatus.CONTRADICTED
    )

    return Question.model_validate(
        {
            "id": question_id,
            "assessment_id": assessment_id,
            "question": (
                f"Which statement is authoritative for {mapping.requirement_id}?"
                if contradicted
                else f"Can you confirm {wanted}?"
            ),
            "rationale": (
                f"The documents do not settle it, and the answer changes whether "
                f"{mapping.requirement_id} is met for {threat.id}."
            ),
            "related_object_type": "threat",
            "related_object_id": threat.id,
            "priority": QuestionPriority.HIGH if contradicted else QuestionPriority.MEDIUM,
            "blocking": False,
            "status": QuestionStatus.OPEN,
            "generated_by": GENERATED_BY,
        }
    )


def _build_gap(
    *,
    mapping: ControlMapping,
    threat: Threat,
    assessed: EvidenceAssessment | None,
    gap_id: str,
    assessment_id: str,
) -> DocumentationGap:
    """A documentation gap: what could not be determined, and why it matters.

    `severity` is `medium` and not derived from anything. DEC-045 forbids `unassigned` and no step
    before this one rates a gap, so a fixed honest middle is what is left; DEC-045's tradeoffs
    already record that nothing enforces a considered value over a default one.
    """
    return DocumentationGap.model_validate(
        {
            "id": gap_id,
            "assessment_id": assessment_id,
            "title": finding_title(threat, mapping),
            "description": (
                f"The supplied documents do not establish whether {mapping.requirement_id} is "
                f"met for {threat.id}."
            ),
            "importance": (
                f"{threat.impact} The requirement applies and its satisfaction cannot be "
                f"determined from what was supplied."
            ),
            "related_object_ids": [threat.id, mapping.id],
            "requested_evidence": list(assessed.missing_evidence) if assessed else [],
            "severity": Severity.MEDIUM,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": GENERATED_BY,
            "evidence_ids": list(mapping.evidence_ids),
        }
    )


def persist_consolidation(
    handle: AssessmentHandle, outcome: ConsolidationOutcome
) -> ConsolidationOutcome:
    """Re-mint the outcome's identifiers from the store and write it (DEC-018).

    `consolidate` builds objects with provisional identifiers so it can be tested and reasoned
    about without a store. This is where they become the store's, from the per-assessment counter,
    in one transaction with the insert that consumes them.

    The DEC-066 fingerprint is set here rather than in `consolidate`, because it hashes component
    *names* and the names live in the store: `consolidate` holds identifiers only. Persist is
    where DEC-066 says the value is computed, from the matcher's one implementation.
    """
    repository = handle.objects
    findings: list[Finding] = []
    questions: list[Question] = []
    gaps: list[DocumentationGap] = []

    component_names = component_name_index(handle)
    requirement_by_mapping, component_names_by_mapping = gap_identity_indexes(handle)

    with repository.transaction():
        for mapping in outcome.downgraded_mappings:
            # Under its existing identifier: a downgrade changes content, never identity, and
            # every reference into the mapping must keep resolving (DEC-046, DEC-055).
            repository.save(mapping)

        for finding in outcome.findings:
            stored = fingerprinted_finding(
                Finding.model_validate({**finding.model_dump(), "id": repository.allocate("fnd")}),
                component_names,
            )
            repository.save(stored)
            findings.append(stored)

        for question in outcome.questions:
            stored_question = Question.model_validate(
                {**question.model_dump(), "id": repository.allocate("qst")}
            )
            repository.save(stored_question)
            questions.append(stored_question)

        for gap in outcome.documentation_gaps:
            stored_gap = fingerprinted_gap(
                DocumentationGap.model_validate(
                    {**gap.model_dump(), "id": repository.allocate("gap")}
                ),
                requirement_by_mapping=requirement_by_mapping,
                component_names_by_mapping=component_names_by_mapping,
            )
            repository.save(stored_gap)
            gaps.append(stored_gap)

    return ConsolidationOutcome(
        findings=tuple(findings),
        questions=tuple(questions),
        documentation_gaps=tuple(gaps),
        rejected=outcome.rejected,
        downgraded_mappings=outcome.downgraded_mappings,
    )


PHASE: Final = Phase.FINDING_CONSOLIDATION
