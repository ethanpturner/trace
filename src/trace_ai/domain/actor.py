"""`Actor`: a user, system identity, administrator, threat actor, or external party.

`data-model.md` section 13 is authoritative for the fields, and this object is the one the corpus
was least sure about. Section 40 omitted it from the implementation priority, open question 4 asked
whether actors are first-class objects at all, and `SystemContext` had no field pointing at one --
while `agent-design.md` section 7 listed Actor among the extractor's outputs and the roadmap listed
it in two stages. DEC-037 settles it: Actor is first-class, `SystemContext` gains `actor_ids`, and
section 40 gains the entry it was missing.

**Actor carries no `status`.** Section 13's table has no such column, and every other object in the
context baseline has one. That is not an oversight to correct here: adding a field the document does
not sanction is exactly what `tests/unit/test_data_model_conformance.py` fails on, and changing it
would be a data-model change rather than an implementation detail.

**`trust_level` here is not `SourceDocument.TrustLevel`.** That enum classifies how a *document*
should be treated; this field is free text classifying how much privilege an actor holds. The two
share a name and nothing else, which is why this one is a plain string and stays that way.
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.identifiers import ActorId, AssessmentId, EvidenceReferenceId
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["KNOWN_ACCESS_LEVELS", "KNOWN_ACTOR_TYPES", "KNOWN_SKILL_LEVELS", "Actor"]

# Section 13's examples. Documentation, not a validation rule (DEC-036).
KNOWN_ACTOR_TYPES: Final[frozenset[str]] = frozenset(
    {
        "end_user",
        "developer",
        "administrator",
        "service_identity",
        "third_party_service",
        "external_attacker",
        "malicious_insider",
        "compromised_dependency",
    }
)

# Section 13's persona examples (DEC-068). Starting sets, documentation only: both fields are
# open vocabularies for DEC-036's reasons.
KNOWN_SKILL_LEVELS: Final[frozenset[str]] = frozenset({"opportunist", "skilled", "organized_group"})
KNOWN_ACCESS_LEVELS: Final[frozenset[str]] = frozenset(
    {"anonymous", "authenticated", "privileged", "physical"}
)


class Actor(DomainModel):
    """A party that interacts with the reviewed system (section 13)."""

    id: ActorId
    assessment_id: AssessmentId

    name: str = Field(min_length=1)
    actor_type: VocabularyTerm
    """Open vocabulary; see `KNOWN_ACTOR_TYPES`."""

    trust_level: str | None = None
    """How much privilege this actor holds. Free text, and unrelated to `SourceDocument`'s enum."""

    skill_level: VocabularyTerm | None = None
    """Persona field (DEC-068): how capable this actor is presumed to be. Open vocabulary,
    normalized; see `KNOWN_SKILL_LEVELS`. Its purpose is auditability — a threat's free-text
    preliminary likelihood becomes checkable against who it presumes. `None` means nobody
    characterised the actor, which is not `opportunist`."""

    access_level: VocabularyTerm | None = None
    """Persona field (DEC-068): what access this actor starts with. Open vocabulary, normalized;
    see `KNOWN_ACCESS_LEVELS`. `None` means the documentation does not say."""

    capabilities: list[str] = Field(default_factory=list)
    authentication_method: str | None = None
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    source_origin: SourceOrigin
    """Where this object came from (section 4.4). `uploaded_document` for something the extractor
    read out of a document, `reviewer_edit` for something a person added at the checkpoint. Required
    rather than defaulted, because a default would make the extractor's provenance the answer given
    when nobody supplied one (DEC-039)."""
