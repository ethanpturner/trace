"""`Assessment` and `AssessmentConfiguration`: the root of everything else.

`data-model.md` sections 5 and 6 are authoritative for these fields. The Assessment is the parent
of every other object in the model -- sixteen of them carry an `assessment_id` -- and it is what
`current-architecture.md` section 12's assessment-data boundary is drawn around.

**This object carries no setting that governs the two human checkpoints, and must not acquire
one.** Earlier versions of section 6 declared `require_context_review` and `require_finding_review`
here; DEC-012 removed them. The checkpoints are nodes in the workflow graph rather than runtime
conditionals, so there is no value that advances the pipeline past an unapproved one -- and a field
here would be the switch that defeats DEC-005 whatever it defaulted to. `extra="forbid"` on
`DomainModel` means a reintroduced field fails validation rather than passing silently, and
`tests/unit/test_assessment.py` asserts both names are refused.

Two things that look like configuration and are not. Answering a checkpoint from a recorded
decision file is still a checkpoint -- the node executes, the gate holds, a `ReviewerDecision` is
written -- and that is the mode repeatable evaluation uses. Removing a checkpoint altogether is an
ablation belonging to the evaluation harness, and a run that applies it is recorded as
non-authoritative.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, field_validator, model_validator

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import AssessmentId, WorkflowRunId

__all__ = [
    "ARCHITECTURE_VERSION",
    "DATA_MODEL_VERSION",
    "DEFAULT_MAXIMUM_RETRIES_PER_NODE",
    "WORKFLOW_VERSION",
    "Assessment",
    "AssessmentConfiguration",
    "EvidenceThreshold",
    "default_configuration",
    "new_assessment",
]

# The corpus versions this build implements. Stamped onto every assessment so a stored one records
# what produced it -- DEC-020 refuses to load an assessment written by an incompatible data model,
# and this is the field that refusal reads.
ARCHITECTURE_VERSION: Final = "0.1"
DATA_MODEL_VERSION: Final = "0.1"
WORKFLOW_VERSION: Final = "0.1"

# agent-design.md section 26. Two retries, not zero and not unbounded.
DEFAULT_MAXIMUM_RETRIES_PER_NODE: Final = 2


class EvidenceThreshold(StrEnum):
    """The minimum evidence policy a finding must satisfy (DEC-013).

    Declared here rather than in `domain/enums.py` because section 6 defines the vocabulary on the
    field rather than in section 4's shared types, the same way `ContextClaim` carries its own
    status values.
    """

    DIRECT_OR_CONFIRMED = "direct-or-confirmed"
    PERMISSIVE = "permissive"


class AssessmentConfiguration(DomainModel):
    """Settings that affect an assessment run (section 6).

    Nothing here governs a checkpoint. See the module docstring; DEC-012 is the reason.

    **A field section 6 marks `Required: Yes` carries no Pydantic default**, including the four
    that have an obvious one. `data-model.md` is authoritative for required-ness, and the
    conformance guard reads it as "the constructor must be given a value" -- the only reading that
    is mechanically checkable, since a default makes a field optional however sensible the value
    is. The defaults still exist; they live in `default_configuration()`, where they are visible as
    choices rather than invisible in a signature.
    """

    model_profile: str
    """A named provider-model-settings bundle, not a bare model identifier (DEC-014).

    It does not select a provider or a model by itself: the adapter behind the model seam resolves
    the name to a provider, a model, and the settings that go with it. `primary-development` is
    section 6's example.
    """

    threat_methodology: str
    """The initial threat-analysis methodology, such as `stride-scenario-based`.

    STRIDE is a coverage aid rather than a mechanical threat generator, so this names an approach
    and not a checklist to enumerate.

    **Free text, with no registry** (DEC-041). One methodology exists, and a registry with one
    entry validates nothing while having to be edited before a second could be tried — which
    inverts the point of this being configuration. The cost is that `stride` and
    `stride-scenario-based` compare as different, which is free for a single-user MVP and stops
    being free at the first cross-assessment comparison.
    """

    maximum_model_calls: int | None = Field(default=None, gt=0)
    """An execution safety limit. `scripts/estimate_cost.py` predicts 28 calls for ForgeFlow."""

    maximum_cost: Decimal | None = Field(default=None, ge=0)
    """A cost limit, as `Decimal` and never `float`.

    Section 6 types it `decimal` and section 27 types `estimated_cost` the same way. A limit
    compared through binary floating point is wrong exactly at the boundary where it matters:
    `8.00` is not representable, so a run costing precisely the limit could halt or not depending
    on rounding nobody chose.
    """

    maximum_retries_per_node: int = Field(ge=0)
    retain_debug_artifacts: bool
    enable_external_tracing: bool
    evidence_threshold: EvidenceThreshold

    evidence_age_threshold_days: int | None = Field(default=None, gt=0)
    """Days after which a cited evidence capture is flagged as stale (DEC-118).

    Unset means no staleness flags anywhere: absence of a policy is not a policy, and a default
    number would be an opinion about every assessment nobody stated. The flag never suppresses,
    expires, or downgrades anything — it marks a citation a reader should re-verify, and it
    governs no checkpoint (DEC-012 is untouched; the checkpoints wait for decisions, not for
    fresh evidence).
    """


class Assessment(DomainModel):
    """One complete security architecture analysis (section 5)."""

    id: AssessmentId
    name: str
    description: str | None = None
    status: ObjectStatus
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    architecture_version: str
    data_model_version: str
    workflow_version: str
    requirements_catalog_version: str | None = None
    configuration: AssessmentConfiguration
    active_workflow_run_id: WorkflowRunId | None = None
    final_report_path: str | None = None
    final_report_run_id: WorkflowRunId | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("created_at", "updated_at")
    @classmethod
    def _must_be_timezone_aware(cls, value: datetime) -> datetime:
        """A naive timestamp serializes as though it were UTC without being marked as such.

        The first place that surfaces is a comparison between two assessments written by different
        code paths, which is the hardest place to notice it.
        """
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware; use trace_ai.domain.base.now()")
        return value

    @model_validator(mode="after")
    def _updated_at_is_not_before_created_at(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError(
                f"updated_at ({self.updated_at.isoformat()}) is earlier than created_at "
                f"({self.created_at.isoformat()})"
            )
        return self


def default_configuration(
    model_profile: str,
    threat_methodology: str,
    **overrides: object,
) -> AssessmentConfiguration:
    """A configuration carrying the defaults the corpus states, for the fields that have one.

    `maximum_retries_per_node` is 2, from `agent-design.md` section 26's retry policy.
    `evidence_threshold` is `direct-or-confirmed`, the stricter of DEC-013's two.
    `enable_external_tracing` is off, because `current-architecture.md` section 5.17 makes sending
    prompt content and source data to an external provider a decision rather than a default.
    `retain_debug_artifacts` is off, because those artifacts are copies of material under review.

    `model_profile` and `threat_methodology` have no default and are parameters: the first names a
    provider-model-settings bundle that depends on what is configured, and the second is an
    analytical choice.
    """
    return AssessmentConfiguration.model_validate(
        {
            "model_profile": model_profile,
            "threat_methodology": threat_methodology,
            "maximum_retries_per_node": DEFAULT_MAXIMUM_RETRIES_PER_NODE,
            "retain_debug_artifacts": False,
            "enable_external_tracing": False,
            "evidence_threshold": EvidenceThreshold.DIRECT_OR_CONFIRMED,
        }
        | overrides
    )


def new_assessment(
    assessment_id: str,
    name: str,
    configuration: AssessmentConfiguration,
    **fields: object,
) -> Assessment:
    """Build an assessment with its timestamps and version fields stamped.

    The identifier is a parameter rather than something this function mints. DEC-018 assigns a
    generated identifier at insert, from the persistence layer's counter, precisely so it is not
    assigned at construction -- so the caller allocates it inside the transaction that stores the
    object and passes it here. The issue that asked for this factory predates that decision.

    Everything else a caller would otherwise assemble by hand is stamped: `created_at` and
    `updated_at` from the one UTC clock, and the three version fields from this build's constants,
    so no assessment records a version somebody typed.
    """
    stamp = now()
    return Assessment.model_validate(
        {
            "id": assessment_id,
            "name": name,
            "status": ObjectStatus.DRAFT,
            "configuration": configuration,
            "created_at": stamp,
            "updated_at": stamp,
            "architecture_version": ARCHITECTURE_VERSION,
            "data_model_version": DATA_MODEL_VERSION,
            "workflow_version": WORKFLOW_VERSION,
        }
        | fields
    )
