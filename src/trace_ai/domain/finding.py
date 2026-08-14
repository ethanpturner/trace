"""`Finding`: the object that means evidence supports a weakness, and never that documentation is thin.

`data-model.md` section 21 is authoritative for the fields. Section 23 states the distinction this
object exists on the other side of:

> A documentation gap means: Trace cannot determine whether a control exists or is effective.
> A finding means: Available evidence supports the conclusion that a meaningful security weakness
> exists.

Collapsing the two is the failure the project exists to avoid, and `design-principles.md` section 7
says a rule whose violation makes the system behave incorrectly does not belong in a prompt. So the
separation is a validator here rather than a sentence somewhere.

**The separation invariant consults DEC-013's table; it does not re-derive one.** `domain/outcomes.py`
holds that table, and `FINDING_VALIDATION_STATUSES` is *derived* from it — the set of validation
statuses some cell reaches a provisional finding from. A `Finding` may carry no other. Four of the
table's thirty cells produce a finding, and none of them from silence: `unverified` resolves to a
gap or a question under every validation status, and `not_evaluated` produces nothing at all.

**A finding whose evidence later turns out unsupported is reclassified, not edited.** The path is
`agent-design.md` section 16's conversion with lineage preserved, not mutating `validation_status`
into a value the table says could not have produced this object.

**`severity` is `unassigned` at creation and the approval gate is what constrains it** (DEC-030).
The model accepts `unassigned` deliberately: the reviewer assigns severity at checkpoint 2, and a
schema demanding it at construction would make Finding Consolidation guess. The hard rule —
section 21's own — is that an *approved* finding may not carry `unassigned`, and that belongs to
the gate rather than here.

**A low-confidence finding carries a justification** (DEC-050, applying DEC-013). DEC-013 is
explicit that the justification does not substitute for evidence: it "qualifies a finding that
already meets the rule but whose confidence is low". So `evidence_ids` is required regardless, and
`low_confidence_justification` is required in addition when `confidence` is `low`. Section 21's
minimum-rules wording reads as an either-or and DEC-013 is the authority that it is not.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    RiskTreatment,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.identifiers import (
    AssessmentId,
    AssetId,
    ComponentId,
    ControlMappingId,
    EvidenceReferenceId,
    FindingId,
    RequirementId,
    ThreatId,
)
from trace_ai.domain.outcomes import FINDING_VALIDATION_STATUSES

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["DuplicateChainError", "Finding", "canonical_finding_id"]


class DuplicateChainError(ValueError):
    """`duplicate_of_id` points somewhere that does not resolve, or points in a circle."""


class Finding(DomainModel):
    """A potentially actionable security weakness supported by analysis (section 21)."""

    id: FindingId
    assessment_id: AssessmentId

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)

    threat_ids: list[ThreatId] = Field(min_length=1)
    """Section 21's first minimum rule: at least one related threat. A weakness with no scenario
    behind it is a requirement restated as a complaint."""

    requirement_ids: list[RequirementId] = Field(min_length=1)
    """At least one applicable requirement or stated security expectation."""

    control_mapping_ids: list[ControlMappingId]
    """Required by section 21's field table, and carried empty rather than omitted where a finding
    has no mapping behind it. Required-and-empty and absent are different claims: the first says
    nothing linked this finding to a requirement evaluation, the second says nobody looked."""

    affected_component_ids: list[ComponentId]
    affected_asset_ids: list[AssetId]
    """Both keys are required by section 21 and one of the two lists is non-empty. The minimum
    rule is *asset or component*, so neither can carry `min_length` on its own."""

    evidence_ids: list[EvidenceReferenceId] = Field(min_length=1)
    """Required, always. An `EvidenceReference` quotes real source text and cannot be constructed
    to express an absence (section 8), so requiring one here is what makes concluding a weakness
    from silence structurally impossible rather than merely discouraged."""

    validation_status: ValidationStatus
    severity: Severity
    likelihood: str | None = None
    impact: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)

    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    confidence: ConfidenceLevel
    low_confidence_justification: str | None = None
    """Required when `confidence` is `low` (DEC-050). What evidence would raise confidence, and
    why the conclusion is worth surfacing before that evidence exists."""

    status: ObjectStatus
    generated_by: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime

    risk_treatment: RiskTreatment = RiskTreatment.UNDECIDED
    """The reviewer's chosen response, assigned at checkpoint 2 and never proposed by a node
    (DEC-060), the neighbouring judgment to severity (DEC-030). Findings are created `undecided`,
    which unlike an unassigned severity may survive approval — the gate is only that `accept`
    carries a `treatment_rationale`."""

    treatment_rationale: str | None = None
    """Required when `risk_treatment` is `accept` — the residual-risk statement, what remains
    exposed and why that is tolerable — and optional otherwise. Enforced at the approval gate, not
    here, exactly as severity's mandatory-on-approval rule is (DEC-060)."""

    treatment_review_by: date | None = None
    """An optional date to revisit an accepted risk; DEC-061 gives it semantics."""

    content_fingerprint: str | None = None
    """DEC-066's cross-run identity: `sha256:` over the sorted `requirement_ids` and the sorted,
    normalized affected-component names — structural fields only, no prose, so it survives
    rewording. Derived, never authored: the application sets it when the finding is persisted and
    recomputes it when an identity field changes (`services/findings/fingerprints.py`, reading
    `services/evaluation/matching.py`'s one implementation). It exists alongside the allocated
    identifier and never instead of it — DEC-018 identifiers are per-assessment, so this is the
    handle for "same finding, still open" across runs."""

    duplicate_of_id: FindingId | None = None
    reviewer_notes: str | None = None

    converted_from_id: str | None = None
    """The object this was converted from, if it was (DEC-051).

    Cross-type by design, so it is a plain identifier rather than a typed alias: a finding may
    have been a documentation gap and a gap may have been a finding. `supersedes_id` is the
    same-type mechanism DEC-023 gives for regeneration and does not reach across the boundary."""

    @model_validator(mode="after")
    def _affects_an_asset_or_a_component(self) -> Self:
        """Section 21: at least one affected asset or component.

        Either satisfies it, which is why neither list carries `min_length`. A finding affecting
        nothing names no part of the system a reader could go and look at.
        """
        if not self.affected_component_ids and not self.affected_asset_ids:
            raise ValueError(
                "a finding names at least one affected component or asset (data-model.md "
                "section 21, Minimum validation rules). A weakness that affects nothing "
                "identifiable is not yet a finding."
            )
        return self

    @model_validator(mode="after")
    def _validation_status_could_have_produced_a_finding(self) -> Self:
        """DEC-013's table decides what a finding is reachable from, and this asks it.

        The set is derived in `domain/outcomes.py` rather than restated, so this validator has no
        opinion of its own. `unverified` is the case that matters: it resolves to a documentation
        gap or a question under every validation status and to a finding under none, which is the
        DEC-009 separation expressed as a schema rule.
        """
        if self.validation_status not in FINDING_VALIDATION_STATUSES:
            permitted = sorted(status.value for status in FINDING_VALIDATION_STATUSES)
            raise ValueError(
                f"validation_status {self.validation_status.value!r} is one DEC-013's outcome "
                f"table never produces a finding from; it permits {permitted}. A conclusion the "
                f"evidence does not carry is a question or a documentation gap, and one whose "
                f"evidence turned out unsupported is reclassified with its lineage rather than "
                f"relabelled here (agent-design.md section 16)."
            )
        return self

    @model_validator(mode="after")
    def _low_confidence_is_justified(self) -> Self:
        """DEC-013's justification, required where DEC-013 requires it (DEC-050).

        It qualifies rather than substitutes: `evidence_ids` is non-empty whatever the confidence.
        Section 21's minimum rules read "evidence or an explicit low-confidence justification",
        and DEC-013 is the authority that the word is *and* wherever confidence is low.
        """
        if self.confidence is ConfidenceLevel.LOW and not self.low_confidence_justification:
            raise ValueError(
                "a finding with confidence 'low' states what evidence would raise it and why the "
                "conclusion is worth surfacing before that evidence exists (DEC-013, DEC-050). "
                "Low confidence with no justification is a conclusion nobody can weigh."
            )
        if self.confidence is not ConfidenceLevel.LOW and self.low_confidence_justification:
            raise ValueError(
                "low_confidence_justification is set on a finding whose confidence is "
                f"{self.confidence.value!r}. The field explains low confidence; on anything else "
                f"it is an explanation of something that is not the case."
            )
        return self

    @model_validator(mode="after")
    def _duplicate_points_elsewhere(self) -> Self:
        """A finding cannot be a duplicate of itself.

        The trivial case only. A cycle across two or more findings needs the whole set and is
        `canonical_finding_id`'s.
        """
        if self.duplicate_of_id is not None and self.duplicate_of_id == self.id:
            raise ValueError(
                f"{self.id} is marked a duplicate of itself. A canonical finding carries no "
                f"duplicate_of_id at all."
            )
        return self


def canonical_finding_id(finding: Finding, findings: Iterable[Finding]) -> str:
    """Follow `duplicate_of_id` to the finding that is not a duplicate of anything.

    Raises rather than returning a partial answer when the chain leaves the assessment or closes
    on itself. Both are states a reader could not resolve and neither is detectable from one
    object: `Finding` refuses the self-reference, and everything longer needs the set.

    `data-model.md` section 32 requires lineage to stay traceable, and a duplicate chain is
    lineage — an unresolvable one means the report cannot say which finding is the real one.
    """
    by_id = {other.id: other for other in findings}
    seen: list[str] = [finding.id]
    current = finding

    while current.duplicate_of_id is not None:
        following = by_id.get(current.duplicate_of_id)
        if following is None:
            raise DuplicateChainError(
                f"{current.id} is a duplicate of {current.duplicate_of_id!r}, which is not a "
                f"finding in this assessment. A duplicate pointing at nothing is a finding the "
                f"report cannot resolve to a canonical one."
            )
        if following.id in seen:
            raise DuplicateChainError(
                f"the duplicate chain {[*seen, following.id]} closes on itself. No finding in it "
                f"is canonical, so none of them can be reported."
            )
        seen.append(following.id)
        current = following

    return current.id
