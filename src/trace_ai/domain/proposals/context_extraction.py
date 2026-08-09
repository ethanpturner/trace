"""`ContextExtractionProposal`: what the extractor is asked to return, and nothing authoritative.

`agent-design.md` section 22 states the write model plainly — agents return proposed structured
objects and do not write authoritative records — and DEC-006 says the same thing from the data side.
This module is that boundary made concrete: one schema the model returns, containing proposals, and
structurally incapable of carrying anything the application owns.

**Proposed objects carry local keys, not identifiers.** DEC-018 allocates an identifier at insert
from a store-held counter, so an agent that minted `cmp-001` would be minting a number the store may
already have used. A proposed data flow therefore names its endpoints by the *key* of a component
proposed in the same response, and conversion resolves keys to allocated identifiers. A key that
looks like an application identifier is refused outright, because the failure it prevents —
an agent quietly numbering objects — is invisible until two assessments collide.

**The prohibitions are structural.** Section 7 forbids the agent to generate findings, assign
severity, or approve anything. None of those has a field here, and `extra="forbid"` on
`DomainModel` turns an invented one into a validation failure rather than a field silently dropped.
That is the same mechanism that makes an agent-proposed object with a made-up field fail rather than
pass downstream stripped of it.

**Evidence discipline is carried in, not added later.** A `documented` or `inferred` claim must cite
evidence; an `assumed` or `unknown` claim must not be required to (DEC-009). And every cited
identifier must be one the input package supplied — `agent-design.md` section 14 lists nonexistent
evidence references among the failure conditions, and a proposal that invents one is a proposal
whose citations cannot be checked.

**Injection attempts are observations, not claims** (DEC-021). Section 25 says the workflow may
create a context claim or a security event when injection-like content is detected without defining
either; DEC-021 settled it as one `SourceObservation` with a `kind`, and this schema carries it.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Self

from pydantic import AfterValidator, Field, JsonValue, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.context_claim import ClaimStatus
from trace_ai.domain.data_flow import FlowDirection
from trace_ai.domain.enums import ConfidenceLevel
from trace_ai.domain.identifiers import EvidenceReferenceId
from trace_ai.domain.question import QuestionPriority
from trace_ai.domain.source_observation import ObservationKind
from trace_ai.domain.vocabulary import UNKNOWN, VocabularyTerm

__all__ = [
    "ContextExtractionProposal",
    "LocalKey",
    "ProposalError",
    "ProposedActor",
    "ProposedAsset",
    "ProposedComponent",
    "ProposedContextClaim",
    "ProposedDataFlow",
    "ProposedObservation",
    "ProposedQuestion",
    "ProposedSystemContext",
    "ProposedTrustBoundary",
]

# A key names an object inside one response. Lowercase words, hyphens or underscores between them:
# `webhook-receiver`, `customer_source_code`.
_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")

# What a key must not look like. DEC-018's two forms, matched loosely on purpose: the point is to
# refuse anything a reader could mistake for an allocated identifier, not to parse one.
_LOOKS_LIKE_AN_IDENTIFIER = re.compile(r"^[a-z]{2,4}-(?:[A-Z0-9]+-)?\d{2,}$")


class ProposalError(ValueError):
    """A proposal that cannot be turned into objects, with the reason named."""


def _valid_key(value: str) -> str:
    if not _KEY.match(value):
        raise ValueError(
            f"{value!r} is not a local key. Use lowercase words joined by hyphens or underscores, "
            f"such as 'webhook-receiver'."
        )
    if _LOOKS_LIKE_AN_IDENTIFIER.match(value):
        raise ValueError(
            f"{value!r} looks like an application identifier. Proposed objects carry local keys; "
            f"identifiers are allocated by the store at insert (DEC-018), and an agent-chosen one "
            f"could collide with a record that already exists."
        )
    return value


LocalKey = Annotated[str, AfterValidator(_valid_key)]
"""A name for one proposed object, unique within the response and meaningless outside it."""


class ProposedSystemContext(DomainModel):
    """The system-level fields of a `SystemContext`, without its identifier lists.

    The lists are the application's: they name objects it allocated identifiers for, and an agent
    cannot know those. Nothing here carries `approved_at`, `approved_by`, or `version` — approval
    is the reviewer's and versioning is the application's.
    """

    system_name: str = Field(min_length=1)
    system_purpose: str | None = None
    business_criticality: str | None = None
    environment: list[str] = Field(default_factory=list)
    deployment_model: str | None = None
    data_classifications: list[str] = Field(default_factory=list)


class ProposedComponent(DomainModel):
    """A component the agent proposes (`data-model.md` section 11, minus what the application owns)."""

    key: LocalKey
    name: str = Field(min_length=1)
    component_type: VocabularyTerm
    description: str | None = None
    technology: list[str] = Field(default_factory=list)
    ownership: str | None = None
    deployment_zone: str | None = None
    internet_accessible: bool | None = None
    """`None` where the documentation does not say — which is not `False` (DEC-009)."""

    externally_managed: bool | None = None
    data_classifications: list[str] = Field(default_factory=list)
    authentication_mechanisms: list[str] = Field(default_factory=list)
    authorization_mechanisms: list[str] = Field(default_factory=list)
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)


class ProposedActor(DomainModel):
    """An actor the agent proposes (section 13)."""

    key: LocalKey
    name: str = Field(min_length=1)
    actor_type: VocabularyTerm
    trust_level: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    authentication_method: str | None = None
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)


class ProposedAsset(DomainModel):
    """An asset the agent proposes (section 12).

    The three impact fields are prose about what loss would cost. They are **not severity**, which
    section 7 forbids the agent to assign and DEC-030 gives to the reviewer.
    """

    key: LocalKey
    name: str = Field(min_length=1)
    asset_type: VocabularyTerm
    description: str | None = None
    confidentiality_impact: str | None = None
    integrity_impact: str | None = None
    availability_impact: str | None = None
    data_classification: str | None = None
    owner: str | None = None
    component_keys: list[LocalKey] = Field(default_factory=list)
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)


class ProposedDataFlow(DomainModel):
    """A data flow the agent proposes (section 14).

    Endpoints and crossings are local keys, resolved at conversion. `authentication` and
    `encryption_in_transit` default to `unknown` rather than to absence, because silence read as
    `False` is an asserted weakness nobody evidenced.
    """

    key: LocalKey
    name: str = Field(min_length=1)
    source_component_key: LocalKey
    destination_component_key: LocalKey
    direction: FlowDirection
    protocol: str | None = None
    data_types: list[str] = Field(default_factory=list)
    authentication: VocabularyTerm = UNKNOWN
    encryption_in_transit: VocabularyTerm = UNKNOWN
    crosses_trust_boundary_keys: list[LocalKey] = Field(default_factory=list)
    internet_exposed: bool | None = None
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    @model_validator(mode="after")
    def _endpoints_differ(self) -> Self:
        if self.source_component_key == self.destination_component_key:
            raise ValueError(
                f"source and destination are both {self.source_component_key!r}; a data flow moves "
                f"data between two components"
            )
        return self


class ProposedTrustBoundary(DomainModel):
    """A trust boundary the agent proposes (section 15)."""

    key: LocalKey
    name: str = Field(min_length=1)
    boundary_type: VocabularyTerm
    description: str | None = None
    inside_component_keys: list[LocalKey] = Field(default_factory=list)
    outside_component_keys: list[LocalKey] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)


class ProposedContextClaim(DomainModel):
    """A claim the agent proposes (section 10), carrying its own epistemic status.

    The evidence rule is the one `ContextClaim` enforces, applied one step earlier: a `documented`
    or `inferred` claim cites evidence, and an `assumed` or `unknown` claim is not required to. The
    duplication is deliberate — catching it here means the failure is a schema failure the retry
    policy can feed back, rather than a conversion error after the call is already paid for.
    """

    key: LocalKey
    subject_type: VocabularyTerm
    subject_key: LocalKey | None = None
    """The proposed object this claim is about, when it is about one."""

    predicate: str = Field(min_length=1)
    value: JsonValue
    status: ClaimStatus
    confidence: ConfidenceLevel
    rationale: str | None = None
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    @model_validator(mode="after")
    def _evidence_matches_the_claimed_status(self) -> Self:
        if self.status in {ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED} and not self.evidence_ids:
            raise ValueError(
                f"a {self.status} claim must cite evidence. A claim the documentation does not "
                f"support is {ClaimStatus.ASSUMED} or {ClaimStatus.UNKNOWN} (DEC-009)."
            )
        if (
            self.status in {ClaimStatus.INFERRED, ClaimStatus.ASSUMED}
            and not (self.rationale or "").strip()
        ):
            raise ValueError(f"a {self.status} claim must carry a rationale (DEC-022)")
        return self


class ProposedQuestion(DomainModel):
    """A clarifying question (section 22). DEC-009's first-named outlet."""

    key: LocalKey
    question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    related_object_key: LocalKey | None = None
    priority: QuestionPriority
    blocking: bool


class ProposedObservation(DomainModel):
    """Something observed about the source material (section 10a, DEC-021).

    One object for contradictions and detected injection attempts, distinguished by `kind`. It
    carries no severity and never becomes a finding: an observation asserts something about a
    document, and a finding asserts a weakness in the reviewed system.
    """

    key: LocalKey
    kind: ObservationKind
    summary: str = Field(min_length=1)
    evidence_ids: list[EvidenceReferenceId] = Field(min_length=1)
    subject_claim_keys: list[LocalKey] = Field(default_factory=list)

    @model_validator(mode="after")
    def _evidence_meets_the_minimum_for_its_kind(self) -> Self:
        required = 2 if self.kind is ObservationKind.CONTRADICTION else 1
        if len(self.evidence_ids) < required:
            raise ValueError(
                f"a {self.kind} observation requires at least {required} evidence references; "
                f"one passage cannot establish that two disagree"
            )
        return self


class ContextExtractionProposal(DomainModel):
    """One context-extraction response: `agent-design.md` section 7's outputs, and nothing else.

    Everything the application owns is absent by construction — identifiers, statuses, approval
    fields, severity, findings — so the boundary section 22 states is a property of the schema
    rather than a rule someone remembers.
    """

    system: ProposedSystemContext
    claims: list[ProposedContextClaim] = Field(default_factory=list)
    components: list[ProposedComponent] = Field(default_factory=list)
    actors: list[ProposedActor] = Field(default_factory=list)
    assets: list[ProposedAsset] = Field(default_factory=list)
    data_flows: list[ProposedDataFlow] = Field(default_factory=list)
    trust_boundaries: list[ProposedTrustBoundary] = Field(default_factory=list)
    questions: list[ProposedQuestion] = Field(default_factory=list)
    observations: list[ProposedObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _keys_are_unique(self) -> Self:
        """One key, one object. Two objects sharing a key make every reference to it ambiguous."""
        seen: dict[str, str] = {}
        for group, items in self._keyed_groups().items():
            for item in items:
                key = item.key
                if key in seen:
                    raise ValueError(
                        f"local key {key!r} is used by both {seen[key]} and {group}; "
                        f"a key names one object"
                    )
                seen[key] = group
        return self

    def _keyed_groups(self) -> dict[str, list[Any]]:
        return {
            "claims": list(self.claims),
            "components": list(self.components),
            "actors": list(self.actors),
            "assets": list(self.assets),
            "data_flows": list(self.data_flows),
            "trust_boundaries": list(self.trust_boundaries),
            "questions": list(self.questions),
            "observations": list(self.observations),
        }

    def cited_evidence_ids(self) -> set[str]:
        """Every evidence identifier the proposal cites, across every object."""
        cited: set[str] = set()
        for items in self._keyed_groups().values():
            for item in items:
                cited.update(getattr(item, "evidence_ids", []))
        return cited

    def validate_against_evidence(self, available: set[str]) -> None:
        """Refuse a proposal citing evidence the input package did not supply.

        `agent-design.md` section 14 lists nonexistent evidence references among the failure
        conditions, and it is the failure that matters most here: a citation nobody can resolve
        looks exactly like one that checks out, right up until someone follows it.
        """
        invented = sorted(self.cited_evidence_ids() - available)
        if invented:
            raise ProposalError(
                f"the proposal cites evidence that was not supplied: {', '.join(invented)}. "
                f"An unresolvable citation reads as a supported claim (agent-design.md section 14)."
            )

    def keys(self) -> set[str]:
        """Every local key the proposal defines."""
        return {item.key for items in self._keyed_groups().values() for item in items}

    def validate_references(self) -> None:
        """Refuse a proposal whose local references do not resolve within it.

        Checked before conversion so the failure is a schema-shaped one the retry policy can feed
        back to the agent, rather than an exception halfway through allocating identifiers.
        """
        defined = self.keys()
        problems: list[str] = []

        for flow in self.data_flows:
            for label, key in (
                ("source_component_key", flow.source_component_key),
                ("destination_component_key", flow.destination_component_key),
            ):
                if key not in {component.key for component in self.components}:
                    problems.append(
                        f"data flow {flow.key!r}: {label} {key!r} is not a proposed component"
                    )
            for crossed in flow.crosses_trust_boundary_keys:
                if crossed not in {boundary.key for boundary in self.trust_boundaries}:
                    problems.append(
                        f"data flow {flow.key!r}: crosses {crossed!r}, which is not a proposed "
                        f"trust boundary"
                    )

        for asset in self.assets:
            for key in asset.component_keys:
                if key not in {component.key for component in self.components}:
                    problems.append(f"asset {asset.key!r}: {key!r} is not a proposed component")

        for boundary in self.trust_boundaries:
            for key in [*boundary.inside_component_keys, *boundary.outside_component_keys]:
                if key not in {component.key for component in self.components}:
                    problems.append(
                        f"trust boundary {boundary.key!r}: {key!r} is not a proposed component"
                    )

        for observation in self.observations:
            for key in observation.subject_claim_keys:
                if key not in {claim.key for claim in self.claims}:
                    problems.append(
                        f"observation {observation.key!r}: {key!r} is not a proposed claim"
                    )

        for claim in self.claims:
            if claim.subject_key is not None and claim.subject_key not in defined:
                problems.append(
                    f"claim {claim.key!r}: subject_key {claim.subject_key!r} is undefined"
                )

        for question in self.questions:
            if (
                question.related_object_key is not None
                and question.related_object_key not in defined
            ):
                problems.append(
                    f"question {question.key!r}: related_object_key "
                    f"{question.related_object_key!r} is undefined"
                )

        if problems:
            raise ProposalError("; ".join(problems))
