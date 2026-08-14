"""Turning a validated proposal into domain objects the application owns.

This is the moment `agent-design.md` section 22's write model becomes concrete: the agent proposed,
and here the application takes ownership. Three things change at the boundary and each is the
application's alone.

**Identifiers are allocated, not accepted** (DEC-018). Every proposed object gets one from the
store's per-`(assessment_id, prefix)` counter, and local keys are resolved to those identifiers. A
key that does not resolve stops the conversion by name rather than producing an object pointing at
nothing.

**Status is set here, not proposed.** Everything arrives `candidate`: the objects exist and nobody
has approved them. An agent that could propose `approved` would be approving its own work, which is
the thing two structural checkpoints exist to prevent.

**Order is fixed** — components, actors, assets, trust boundaries, data flows, claims, questions,
observations — so identifiers are assigned in the same order on a re-run over the same proposal.
DEC-018 makes generated identifiers order-dependent and says that is harmless; it is harmless
because nothing outside the assessment stores one, and it is easier to read when it is at least
stable within a run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.question import Question, QuestionStatus
from trace_ai.domain.source_observation import SourceObservation
from trace_ai.domain.trust_boundary import TrustBoundary

if TYPE_CHECKING:
    from datetime import datetime

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.identifiers import IdentifierAllocator
    from trace_ai.domain.proposals.context_extraction import ContextExtractionProposal

__all__ = ["ConvertedContext", "convert_proposal"]


@dataclass(frozen=True, slots=True)
class ConvertedContext:
    """The objects a proposal became, and the key-to-identifier map that produced them."""

    components: tuple[Component, ...] = ()
    actors: tuple[Actor, ...] = ()
    assets: tuple[Asset, ...] = ()
    trust_boundaries: tuple[TrustBoundary, ...] = ()
    data_flows: tuple[DataFlow, ...] = ()
    claims: tuple[ContextClaim, ...] = ()
    questions: tuple[Question, ...] = ()
    observations: tuple[SourceObservation, ...] = ()
    identifiers: dict[str, str] = field(default_factory=dict)
    """Local key to allocated identifier. Kept so a validation message about a converted object can
    name the key the agent used, which is the only name the agent would recognize."""

    def all_objects(self) -> list[DomainModel]:
        """Every converted object, in allocation order."""
        return [
            *self.components,
            *self.actors,
            *self.assets,
            *self.trust_boundaries,
            *self.data_flows,
            *self.claims,
            *self.questions,
            *self.observations,
        ]


def convert_proposal(
    proposal: ContextExtractionProposal,
    *,
    allocator: IdentifierAllocator,
    assessment_id: str,
    created_at: datetime,
    generated_by: str,
    source_origin: SourceOrigin = SourceOrigin.UPLOADED_DOCUMENT,
) -> ConvertedContext:
    """Allocate identifiers and build domain objects from a validated proposal.

    `proposal.validate_references()` is called first: an unresolved key has to stop the conversion
    before any identifier is allocated, because a counter is monotonic and a half-converted proposal
    would leave gaps that read as deleted objects.

    `source_origin` is `uploaded_document` for the extraction agent's proposals and
    `structured_input` for a deterministic parser's (DEC-070): the distinction that matters —
    mechanical versus model-extracted — is exactly the one section 4.4 already draws.
    """
    proposal.validate_references()

    identifiers: dict[str, str] = {}

    def allocate(key: str, prefix: str) -> str:
        identifier = allocator.allocate(prefix)
        identifiers[key] = identifier
        return identifier

    def resolve(key: str, *, described_as: str) -> str:
        identifier = identifiers.get(key)
        if identifier is None:
            raise ProposalError(
                f"{described_as} references local key {key!r}, which no proposed object defines"
            )
        return identifier

    components = tuple(
        Component.model_validate(
            proposed.model_dump(exclude={"key"})
            | {
                "id": allocate(proposed.key, "cmp"),
                "assessment_id": assessment_id,
                "source_origin": source_origin,
                "status": ObjectStatus.CANDIDATE,
            }
        )
        for proposed in proposal.components
    )

    actors = tuple(
        Actor.model_validate(
            proposed.model_dump(exclude={"key"})
            | {
                "id": allocate(proposed.key, "act"),
                "assessment_id": assessment_id,
                "source_origin": source_origin,
            }
        )
        for proposed in proposal.actors
    )

    assets = tuple(
        Asset.model_validate(
            proposed.model_dump(exclude={"key", "component_keys", "stored_in_component_keys"})
            | {
                "id": allocate(proposed.key, "ast"),
                "assessment_id": assessment_id,
                "source_origin": source_origin,
                "status": ObjectStatus.CANDIDATE,
                "component_ids": [
                    resolve(key, described_as=f"asset {proposed.key!r}")
                    for key in proposed.component_keys
                ],
                "stored_in_component_ids": [
                    resolve(key, described_as=f"asset {proposed.key!r}")
                    for key in proposed.stored_in_component_keys
                ],
            }
        )
        for proposed in proposal.assets
    )

    boundaries = tuple(
        TrustBoundary.model_validate(
            proposed.model_dump(exclude={"key", "inside_component_keys", "outside_component_keys"})
            | {
                "id": allocate(proposed.key, "tb"),
                "assessment_id": assessment_id,
                "source_origin": source_origin,
                "status": ObjectStatus.CANDIDATE,
                "inside_component_ids": [
                    resolve(key, described_as=f"trust boundary {proposed.key!r}")
                    for key in proposed.inside_component_keys
                ],
                "outside_component_ids": [
                    resolve(key, described_as=f"trust boundary {proposed.key!r}")
                    for key in proposed.outside_component_keys
                ],
            }
        )
        for proposed in proposal.trust_boundaries
    )

    flows = tuple(
        DataFlow.model_validate(
            proposed.model_dump(
                exclude={
                    "key",
                    "source_component_key",
                    "destination_component_key",
                    "crosses_trust_boundary_keys",
                }
            )
            | {
                "id": allocate(proposed.key, "df"),
                "assessment_id": assessment_id,
                "source_origin": source_origin,
                "status": ObjectStatus.CANDIDATE,
                "source_component_id": resolve(
                    proposed.source_component_key, described_as=f"data flow {proposed.key!r}"
                ),
                "destination_component_id": resolve(
                    proposed.destination_component_key, described_as=f"data flow {proposed.key!r}"
                ),
                "crosses_trust_boundary_ids": [
                    resolve(key, described_as=f"data flow {proposed.key!r}")
                    for key in proposed.crosses_trust_boundary_keys
                ],
            }
        )
        for proposed in proposal.data_flows
    )

    claims = tuple(
        ContextClaim.model_validate(
            proposed.model_dump(exclude={"key", "subject_key"})
            | {
                "id": allocate(proposed.key, "ctx"),
                "assessment_id": assessment_id,
                "subject_id": (
                    None
                    if proposed.subject_key is None
                    else resolve(proposed.subject_key, described_as=f"claim {proposed.key!r}")
                ),
                "source_origin": source_origin,
                "generated_by": generated_by,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        for proposed in proposal.claims
    )

    questions = tuple(
        Question.model_validate(
            proposed.model_dump(exclude={"key", "related_object_key"})
            | {
                "id": allocate(proposed.key, "qst"),
                "assessment_id": assessment_id,
                "related_object_id": (
                    None
                    if proposed.related_object_key is None
                    else resolve(
                        proposed.related_object_key, described_as=f"question {proposed.key!r}"
                    )
                ),
                "related_object_type": None,
                "status": QuestionStatus.OPEN,
                "generated_by": generated_by,
            }
        )
        for proposed in proposal.questions
    )

    observations = tuple(
        SourceObservation.model_validate(
            proposed.model_dump(exclude={"key", "subject_claim_keys"})
            | {
                "id": allocate(proposed.key, "obs"),
                "assessment_id": assessment_id,
                "status": ObjectStatus.CANDIDATE,
                "subject_claim_ids": [
                    resolve(key, described_as=f"observation {proposed.key!r}")
                    for key in proposed.subject_claim_keys
                ],
                "generated_by": generated_by,
                "created_at": created_at,
            }
        )
        for proposed in proposal.observations
    )

    return ConvertedContext(
        components=components,
        actors=actors,
        assets=assets,
        trust_boundaries=boundaries,
        data_flows=flows,
        claims=claims,
        questions=questions,
        observations=observations,
        identifiers=identifiers,
    )
