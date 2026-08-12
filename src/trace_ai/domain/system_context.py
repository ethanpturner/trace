"""`SystemContext`: the approved architecture baseline everything downstream reasons from.

`data-model.md` section 9 is authoritative for the fields. `current-architecture.md` section 5.6
says threat analysis reasons from this object rather than reinterpreting the source documents each
time, which is what makes it a baseline rather than a summary.

**It has no `id` and no `status`, and that is deliberate.** Every other object in sections 10 to 15
has both. A `SystemContext` is keyed by **`(assessment_id, version)`**: an assessment has a sequence
of revisions, `version` numbers them from 1, and DEC-034 states the same key from the identifier
side — the scheme governs objects an assessment produces and this one is addressed by its position
in a sequence instead. DEC-020 persists it as a JSON payload keyed by those two columns.

**It holds identifier lists, not objects.** The objects live in their own rows; this records which
of them the reviewer approved. That is why `validate_against` exists: a list of identifiers can
dangle, and nothing about the shape of the list would show it.

**Approval is data, not control flow.** `approved_at` and `approved_by` are the two fields that make
the DEC-005 checkpoint observable in the record rather than only in the code path that reached it.
`is_approved` reads them and nothing else — there is no configuration flag it consults, because
DEC-012 gives `AssessmentConfiguration` no setting that governs a checkpoint.

**A successor revision cannot inherit an approval.** `next_version` increments `version` and clears
both approval fields, because a revision the reviewer has not seen is not a revision the reviewer
approved. It builds the new object with `model_validate` rather than `model_copy`, per DEC-023: the
copy API validates nothing, and this is the path a reviewer's edits travel.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from pydantic import Field

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import DomainModel
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.identifiers import (
    ActorId,
    AssessmentId,
    AssetId,
    ComponentId,
    ContextClaimId,
    DataFlowId,
    TrustBoundaryId,
)
from trace_ai.domain.trust_boundary import TrustBoundary

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["FIRST_VERSION", "AccessModel", "SystemContext"]


class AccessModel(StrEnum):
    """The system's stated authorization posture (section 9, DEC-068).

    A **closed** enum, because the values are named rather than illustrated — the
    `DataFlow.direction` rule, not the `component_type` one. `unknown` exists because an
    authorization posture nobody stated must never be readable as an answer: the never-`False`,
    never-`None` rule applied to the single highest-leverage authorization fact.
    """

    DENY_BY_DEFAULT = "deny_by_default"
    ALLOW_BY_DEFAULT = "allow_by_default"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# The version an extracted context starts at. Revisions count up from here; there is no version 0,
# because a context that has not been extracted does not exist rather than existing emptily.
FIRST_VERSION: Final = 1

# Which list holds which object type. Written once so the integrity check, the error messages, and
# any future consumer read the same mapping rather than three copies of it.
_LISTS: Final[tuple[tuple[str, type[DomainModel]], ...]] = (
    ("context_claim_ids", ContextClaim),
    ("component_ids", Component),
    ("asset_ids", Asset),
    ("actor_ids", Actor),
    ("data_flow_ids", DataFlow),
    ("trust_boundary_ids", TrustBoundary),
)


class SystemContext(DomainModel):
    """The structured architecture baseline for one assessment revision (section 9)."""

    assessment_id: AssessmentId

    system_name: str = Field(min_length=1)
    system_purpose: str | None = None
    business_criticality: str | None = None
    environment: list[str] = Field(default_factory=list)
    deployment_model: str | None = None
    data_classifications: list[str] = Field(default_factory=list)

    access_model: AccessModel = AccessModel.UNKNOWN
    """The stated authorization posture (DEC-068). Required with `unknown` as the default: a
    posture nobody stated renders as `unknown`, never as an answer."""

    context_claim_ids: list[ContextClaimId]
    component_ids: list[ComponentId]
    asset_ids: list[AssetId]
    actor_ids: list[ActorId]
    """Actors are first-class and referenced here (DEC-037), so an extracted actor is part of what
    the reviewer approves rather than an object nothing points at."""

    data_flow_ids: list[DataFlowId]
    trust_boundary_ids: list[TrustBoundaryId]
    """The six lists are required and may be empty. Section 9 marks every one of them
    `Required: Yes`, and the conformance guard reads required as "the constructor must be given a
    value" -- so a context with no data flows says `[]` rather than leaving the field off. A list
    that is absent and a list that is empty are different claims about an extraction, and only one
    of them is something a reviewer can approve."""

    approved_at: datetime | None = None
    approved_by: str | None = None
    version: int = Field(ge=FIRST_VERSION)
    """Revision number within the assessment, from 1. Half of this object's key."""

    @property
    def is_approved(self) -> bool:
        """True when a reviewer approved this revision, by the record rather than by inference.

        Both fields or neither: a timestamp with no reviewer says an approval happened and not who
        made it, which is precisely what DEC-005's checkpoint exists to record.
        """
        return self.approved_at is not None and self.approved_by is not None

    def next_version(self) -> Self:
        """The successor revision: same content, one version up, unapproved.

        Revision creation has one implementation so that clearing the approval cannot be forgotten
        at a call site. A revision carrying the previous revision's approval would claim a reviewer
        saw content they never saw.
        """
        return type(self).model_validate(
            {
                **self.model_dump(),
                "version": self.version + 1,
                "approved_at": None,
                "approved_by": None,
            }
        )

    def validate_against(self, objects: Iterable[DomainModel]) -> list[str]:
        """Every problem with this context's references, not just the first.

        The Context Validation node calls this. It returns problems rather than raising, because a
        reviewer fixing a context wants the whole list: raising on the first dangling identifier
        turns one review pass into as many passes as there are mistakes.

        Three kinds of problem are reported:

        - an identifier in one of the lists that no supplied object matches
        - an object belonging to a different assessment, which is the assessment-data boundary in
          `current-architecture.md` section 12 failing quietly
        - a data flow reaching a component or crossing a boundary this context does not list, which
          is a flow whose endpoints the reviewer never approved
        """
        by_type: dict[type[DomainModel], dict[str, DomainModel]] = {
            model: {} for _, model in _LISTS
        }
        problems: list[str] = []

        for obj in objects:
            for model in by_type:
                if isinstance(obj, model):
                    identifier = getattr(obj, "id", None)
                    if isinstance(identifier, str):
                        by_type[model][identifier] = obj
                    break

        for list_name, model in _LISTS:
            available = by_type[model]
            for identifier in getattr(self, list_name):
                found = available.get(identifier)
                if found is None:
                    problems.append(
                        f"{list_name}: {identifier} does not resolve to a {model.__name__}"
                    )
                elif (owner := getattr(found, "assessment_id", self.assessment_id)) != (
                    self.assessment_id
                ):
                    problems.append(
                        f"{list_name}: {identifier} belongs to assessment "
                        f"{owner}, not {self.assessment_id}"
                    )

        problems.extend(self._flow_problems(by_type[DataFlow]))
        return problems

    def _flow_problems(self, flows: dict[str, DomainModel]) -> list[str]:
        """Endpoints and crossings of the flows this context lists must be listed here too."""
        components = set(self.component_ids)
        boundaries = set(self.trust_boundary_ids)
        problems: list[str] = []

        for identifier in self.data_flow_ids:
            flow = flows.get(identifier)
            if not isinstance(flow, DataFlow):
                continue  # already reported as dangling

            for end, value in (
                ("source_component_id", flow.source_component_id),
                ("destination_component_id", flow.destination_component_id),
            ):
                if value not in components:
                    problems.append(
                        f"data flow {identifier}: {end} {value} is not in component_ids"
                    )

            for crossed in flow.crosses_trust_boundary_ids:
                if crossed not in boundaries:
                    problems.append(
                        f"data flow {identifier}: crosses trust boundary {crossed}, "
                        f"which is not in trust_boundary_ids"
                    )

        return problems
