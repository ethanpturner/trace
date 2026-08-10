"""`ControlMapping`: the object that stops a requirement becoming a finding by itself.

`data-model.md` section 19 calls this "one of the most important objects in Trace because it
prevents the application from jumping directly from a requirement to a finding", and every rule
here exists to keep that true.

**A mapping always says why the requirement applies.** `applicability_reason` is required and
non-empty. `agent-design.md` section 12 makes "requirements are applied without an applicability
rationale" a failure condition, and section 13 has the validation node enforce rationales; a schema
that allowed an empty one would leave the whole thing to instruction.

**`satisfied` cites evidence and `unverified` does not** (DEC-044, applying DEC-009 and DEC-013).
Those two rules are the same rule from opposite ends. A `satisfied` mapping with no evidence is
section 12's "unverified controls are marked implemented" failure; an `unverified` mapping with no
evidence is the *expected* outcome of assessing ordinary architecture documentation, and section 19
says so directly — a high proportion of `unverified` is not a defect and must not be treated as one.

**`unmet` requires evidence too, and cannot be reached by silence.** Section 19 states it and
explains the mechanism: an `EvidenceReference` quotes real source text, so there is no way to cite
an absence. The schema enforces the structural half; the Mapping Validation node downgrades an
unsupported `unmet` to `unverified` and records the downgrade.

**A suppressed conclusion is recorded on the mapping that suppressed it** (DEC-025). When a
`common_false_positives` entry applies, the conclusion not drawn and the entry that stopped it are
both written down. A suppression nobody can see is indistinguishable from an analysis that never
considered the question.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.identifiers import (
    AssessmentId,
    ControlId,
    ControlMappingId,
    EvidenceReferenceId,
    RequirementId,
    ThreatId,
)

__all__ = [
    "EVIDENCED_SATISFACTION_STATUSES",
    "ApplicabilityStatus",
    "ControlMapping",
    "SatisfactionStatus",
]


class ApplicabilityStatus(StrEnum):
    """Whether the requirement applies to this threat (section 19's applicability values)."""

    APPLICABLE = "applicable"
    CONDITIONALLY_APPLICABLE = "conditionally_applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class SatisfactionStatus(StrEnum):
    """Whether the requirement is met (section 19's satisfaction values)."""

    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    UNVERIFIED = "unverified"
    """The documentation does not establish either way. The expected result for most requirements
    against most documentation, and never by itself a finding (DEC-009, DEC-013)."""

    UNMET = "unmet"
    """Evidence describes the control as absent or inadequate, or contradicts a claim that it
    exists. Silence cannot reach here, because silence cannot be quoted."""

    NOT_APPLICABLE = "not_applicable"


# The statuses that assert something a reader could check, and therefore need a passage behind
# them. `unverified` is deliberately absent: requiring evidence of it would leave nowhere to record
# the ordinary case, which is exactly the DEC-009 collapse this project exists to avoid.
EVIDENCED_SATISFACTION_STATUSES: Final[frozenset[SatisfactionStatus]] = frozenset(
    {
        SatisfactionStatus.SATISFIED,
        SatisfactionStatus.PARTIALLY_SATISFIED,
        SatisfactionStatus.UNMET,
    }
)


class ControlMapping(DomainModel):
    """The relationship among a threat, a requirement, and the controls that bear on it."""

    id: ControlMappingId
    assessment_id: AssessmentId

    threat_id: ThreatId
    """Required. A requirement is only ever evaluated through a threat, which means a requirement
    that applies to the system but that no generated threat reaches is never evaluated and appears
    in no output. That is a coverage limit of this schema (DEC-024), not a defect of any node."""

    requirement_id: RequirementId
    control_ids: list[ControlId] = Field(default_factory=list)

    applicability_status: ApplicabilityStatus
    applicability_reason: str = Field(min_length=1)
    """Why the requirement does or does not apply, referring to the requirement's
    `applicable_conditions` and `non_applicable_conditions`. Required and non-empty: a verdict
    without a rationale is section 12's named failure condition."""

    suppressed_conclusion: str | None = None
    """A conclusion not drawn because a `common_false_positives` entry applied (DEC-025)."""

    suppressed_by: str | None = None
    """The `common_false_positives` entry that stopped it (DEC-025)."""

    downgraded_from: SatisfactionStatus | None = None
    """The satisfaction status the mapping proposed before validation lowered it (DEC-046).

    Set by the Mapping Validation node and by nothing else. A suppression (above) is the *agent*
    declining a conclusion; a downgrade is the *application* refusing one the agent drew. They
    are recorded separately because a metric that could not tell them apart could not tell an
    over-aggressive catalog entry from an under-evidenced model."""

    downgrade_reason: str | None = None
    """Why the downgrade happened, naming the DEC-013 condition that failed (DEC-046)."""

    satisfaction_status: SatisfactionStatus
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel

    generated_by: str = Field(min_length=1)
    reviewer_status: ObjectStatus

    @model_validator(mode="after")
    def _asserted_satisfaction_cites_evidence(self) -> Self:
        """`satisfied`, `partially_satisfied`, and `unmet` cite a passage; `unverified` does not.

        Both halves matter and they are one rule. Section 12 makes an unevidenced `satisfied` the
        "unverified controls are marked implemented" failure; section 19 makes an unevidenced
        `unverified` the ordinary and correct outcome. A schema that required evidence everywhere
        would force every honest silence into a status that asserts something.
        """
        if self.satisfaction_status in EVIDENCED_SATISFACTION_STATUSES and not self.evidence_ids:
            raise ValueError(
                f"a mapping with satisfaction_status {self.satisfaction_status.value!r} must "
                f"cite at least one evidence reference. Absence of evidence resolves to "
                f"'unverified' (DEC-009); 'unmet' needs a passage describing the absence or "
                f"inadequacy, and silence cannot be quoted (data-model.md section 19)."
            )
        return self

    @model_validator(mode="after")
    def _suppression_is_recorded_in_both_halves(self) -> Self:
        """A suppressed conclusion names what suppressed it, and vice versa (DEC-025).

        Half a suppression record is worse than none: a conclusion marked as not drawn, with no
        entry saying why, reads as an unexplained omission rather than as a deliberate one.
        """
        if bool(self.suppressed_conclusion) != bool(self.suppressed_by):
            raise ValueError(
                "suppressed_conclusion and suppressed_by are recorded together (DEC-025). One "
                "without the other is a suppression nobody can check."
            )
        return self

    @model_validator(mode="after")
    def _downgrade_is_recorded_in_both_halves(self) -> Self:
        """A downgraded mapping says what it was and why (DEC-046).

        The same shape as the suppression pair, for the same reason: a status marked as lowered,
        with nothing saying from what or why, reads as an unexplained value rather than a
        deliberate one. `data-model.md` section 19 requires the downgrade to be recorded, and half
        a record does not satisfy it.
        """
        if bool(self.downgraded_from) != bool(self.downgrade_reason):
            raise ValueError(
                "downgraded_from and downgrade_reason are recorded together (DEC-046). A "
                "downgrade nobody can trace is as invisible to evaluation as a silent one."
            )
        if self.downgraded_from is not None and self.downgraded_from == self.satisfaction_status:
            raise ValueError(
                f"downgraded_from is {self.downgraded_from.value!r} and so is "
                f"satisfaction_status. A downgrade that changed nothing is a record of an event "
                f"that did not happen."
            )
        return self
