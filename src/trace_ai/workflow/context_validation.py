"""The Context Validation node: report and route, never reinterpret or correct.

`agent-design.md` section 8 lists ten responsibilities and then states the constraint that shapes
all of them: **the node does not reinterpret architecture or invent corrections.** Everything here
either reports a problem or computes a reason for a human to look. Nothing is fixed, merged,
downgraded, or filled in.

That constraint is not fastidiousness. A validator that corrected its input would be making
architectural judgments with no evidence and no reviewer, which is the failure the two checkpoints
exist to prevent — and the corrections would be invisible, because a corrected object validates.

**This is where DEC-009 stops being advice.** The prompt asks the agent to leave silences alone; a
prompt instruction is advisory. Here, a `documented` claim with no evidence is an *error with a
retry instruction*, and it is never silently re-labelled `assumed` to make it pass. Re-labelling
would be the single most damaging correction available: it would turn a claim the agent asserted
into one nobody asserted, and the record would show a clean validation.

**Errors are returned, not raised.** A reviewer fixing a context wants the whole list, and the
extraction node needs to route on a classification rather than parse a message — so every error
carries an `ErrorClass` from the workflow taxonomy and says which rule it violated.

**Several of these checks are unreachable through the normal path, and that is the point.** The
domain objects already refuse an uncited `documented` claim and a self-referencing data flow, so
those rules can only fire for an object that bypassed the schema. A validator exists for exactly
that case; the tests construct such an object deliberately rather than pretending the path is
common.

**Duplicates are exact only.** `agent-design.md` section 11 permits semantic comparison for threats
and requires the merge decision to stay explicit and traceable; `data-model.md` section 39's open
question 8 is unresolved. Two components with the same normalized name are *reported*, never merged:
merging is a correction, and this node does not make them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.domain.vocabulary import UNKNOWN, normalize_term
from trace_ai.workflow.errors import ErrorClass

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.system_context import SystemContext

__all__ = [
    "SECTION_7_TRIGGERS",
    "ContextValidationOutcome",
    "PrivilegeExtreme",
    "ReviewTrigger",
    "ValidationError",
    "ZoneMismatch",
    "validate_context",
]

# Values that mean "not documented" while pretending to be an answer. `data-model.md` section 14
# requires unknown transport encryption to be `unknown`, never `false`: silence read as `false` is
# an asserted weakness nobody evidenced, and it is the DEC-009 failure at field level.
_FALSE_LIKE: Final[frozenset[str]] = frozenset(
    {"false", "no", "none", "not_documented", "n_a", "na", "absent", "disabled"}
)

# The claim statuses that must cite evidence, and the ones that must not be penalised for not
# citing any. Named as two sets rather than one and its complement, because the second is the
# DEC-009 path and deserves to be visible.
_REQUIRES_EVIDENCE: Final = frozenset({ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED})
_NEEDS_NO_EVIDENCE: Final = frozenset({ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN})

# `agent-design.md` section 7's human-review triggers, in the document's order.
SECTION_7_TRIGGERS: Final[tuple[str, ...]] = (
    "contradictory_high_impact_claims",
    "core_system_purpose_unclear",
    "major_trust_boundaries_uncertain",
    "authentication_or_authorization_ambiguous",
    "significant_component_inferred_rather_than_documented",
    "material_change_from_prior_approved_version",
)


@dataclass(frozen=True, slots=True)
class ValidationError:
    """One problem, named precisely enough to fix without reading the validator.

    `rule` names what was violated, in the corpus's terms, so a reader can find the sentence that
    requires it. `error_class` is what the extraction node routes on — a retry is worth attempting
    for a schema failure and is not for an analysis condition (`agent-design.md` section 26).
    """

    object_id: str
    field: str
    rule: str
    message: str
    error_class: ErrorClass = ErrorClass.SCHEMA_VALIDATION_FAILURE

    @property
    def retryable(self) -> bool:
        from trace_ai.workflow.errors import RETRYABLE

        return self.error_class in RETRYABLE

    def retry_instruction(self) -> str:
        """What to tell the next attempt, in terms the agent can act on."""
        return f"{self.object_id}.{self.field}: {self.message}"


@dataclass(frozen=True, slots=True)
class ReviewTrigger:
    """One of section 7's reasons a human has to look, with what caused it."""

    name: str
    object_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class ZoneMismatch:
    """A flow between components in different zones that crosses no declared boundary (DEC-068).

    Boundary crossings are the highest-signal threat locations, and this is the survey's zone
    insight adopted as a check rather than as a third representation of containment. Warn-only by
    construction: it lives outside `errors`, so it can neither block nor be retried against, and
    nothing is corrected — report-and-route holds.
    """

    flow_id: str
    source_component_id: str
    destination_component_id: str
    source_zone: str
    destination_zone: str

    @property
    def detail(self) -> str:
        return (
            f"{self.flow_id} moves data from {self.source_component_id} "
            f"(zone {self.source_zone!r}) to {self.destination_component_id} "
            f"(zone {self.destination_zone!r}) and crosses no declared trust boundary. Either a "
            f"boundary is undeclared or a zone label is wrong; a reviewer decides which."
        )


@dataclass(frozen=True, slots=True)
class CrossClaimObservation:
    """Two stated claims about the same surface that disagree (DEC-070, #526).

    The parser family's residual: once structured parsers emit mechanically-derived claims
    beside agent-extracted ones, contradictions become both likely and checkable. Warn-only in
    the DEC-063 posture — outside `errors` by construction, so nothing blocks and nothing is
    retried against — and nothing is corrected: report-and-route holds, and a reviewer decides
    which statement is wrong. Every check requires both sides to *state* their value; silence
    is never a side of a conflict (DEC-009).
    """

    kind: str
    """`exposure_conflict`, `transport_conflict`, or `claim_conflict`."""

    object_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class PrivilegeExtreme:
    """An attack-surface extreme the context does not represent (DEC-068).

    The extremes are where analysis most often goes silent, and silence needs the DEC-009 outlet:
    the driver raises a `Question` for each entry, because absence here needs a human answer
    rather than an inferred one.
    """

    extreme: str
    """`anonymous_or_external` or `administrative_or_privileged`."""

    detail: str


@dataclass(frozen=True, slots=True)
class ContextValidationOutcome:
    """Section 8's outputs: what validated, what did not, what to retry, and why to look."""

    errors: tuple[ValidationError, ...] = ()
    triggers: tuple[ReviewTrigger, ...] = ()
    unfamiliar_terms: tuple[str, ...] = ()
    """Vocabulary terms outside the `KNOWN_*` lists. Reported, never rejected (DEC-036): the lists
    illustrate, and a benchmark that used only listed terms would prove nothing."""

    duplicate_groups: tuple[tuple[str, ...], ...] = ()
    """Objects sharing a normalized name. Reported for a reviewer to merge or keep; merging here
    would be a correction, and section 8 forbids the node making them."""

    zone_mismatches: tuple[ZoneMismatch, ...] = ()
    """DEC-068's cross-claim check, warn-only: outside `errors` by construction, so
    `blocking_errors` and `retry_instructions` cannot include one."""

    privilege_extremes: tuple[PrivilegeExtreme, ...] = ()
    """DEC-068's privilege-extremes check: attack-surface extremes no actor represents. The
    driver raises a `Question` per entry — the DEC-009 outlet for exactly that silence — and
    nothing here blocks."""

    cross_claim_observations: tuple[CrossClaimObservation, ...] = ()
    """DEC-070's cross-claim consistency checks (#526), warn-only like the zone check: two
    stated claims about the same surface that disagree, reported for the reviewer."""

    @property
    def ready_for_review(self) -> bool:
        """Whether the workflow may move the context to the checkpoint.

        The transition guard section 8 asks for. A context with an outstanding blocking error is
        not one a reviewer should be asked to approve — they would be approving objects the
        application already knows are wrong.
        """
        return not self.blocking_errors

    @property
    def blocking_errors(self) -> tuple[ValidationError, ...]:
        return tuple(
            error
            for error in self.errors
            if error.error_class is not ErrorClass.INSUFFICIENT_EVIDENCE
        )

    def retry_instructions(self) -> tuple[str, ...]:
        """Feedback for the next attempt, for the errors another attempt could fix."""
        return tuple(error.retry_instruction() for error in self.errors if error.retryable)


def _normalized_name(value: str) -> str:
    """A name reduced for comparison only. Never written back onto the object."""
    try:
        return normalize_term(value)
    except ValueError:
        return value.strip().casefold()


def validate_context(
    context: SystemContext,
    objects: Sequence[DomainModel],
    *,
    available_evidence: set[str] | None = None,
    previous: SystemContext | None = None,
) -> ContextValidationOutcome:
    """Validate one extracted context. Returns problems; changes nothing.

    `objects` are the converted domain objects. They are read and never written: a test asserts
    they are unchanged after a run that produces errors, because the constraint that this node
    corrects nothing is worth more than the convenience of it fixing something obvious.
    """
    errors: list[ValidationError] = []
    by_id: dict[str, DomainModel] = {}

    # -- identifiers are unique within the assessment -------------------------------------
    for obj in objects:
        identifier = getattr(obj, "id", None)
        if not isinstance(identifier, str):
            continue
        if identifier in by_id:
            errors.append(
                ValidationError(
                    object_id=identifier,
                    field="id",
                    rule="identifiers are unique within an assessment (data-model.md section 2.1)",
                    message=f"{identifier} names both a {type(by_id[identifier]).__name__} and a "
                    f"{type(obj).__name__}",
                )
            )
        by_id[identifier] = obj

    # -- schemas still validate, and required fields are present ---------------------------
    for obj in objects:
        try:
            type(obj).model_validate(obj.model_dump())
        except Exception as failure:
            errors.append(
                ValidationError(
                    object_id=str(getattr(obj, "id", type(obj).__name__)),
                    field="*",
                    rule="objects validate against data-model.md (section 33)",
                    message=str(failure).splitlines()[0],
                )
            )

    # -- referenced objects exist -----------------------------------------------------------
    for problem in context.validate_against(objects):
        errors.append(
            ValidationError(
                object_id=problem.split(":")[0].strip(),
                field="reference",
                rule="referenced objects exist (agent-design.md section 8)",
                message=problem,
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        )

    # -- evidence requirements, and the DEC-009 path ----------------------------------------
    available = available_evidence
    for claim in (obj for obj in objects if isinstance(obj, ContextClaim)):
        if claim.status in _REQUIRES_EVIDENCE and not claim.evidence_ids:
            errors.append(
                ValidationError(
                    object_id=claim.id,
                    field="evidence_ids",
                    rule="documented and inferred claims cite evidence (agent-design.md section 7)",
                    message=(
                        f"status is {claim.status} and no evidence is cited. Do not re-label the "
                        f"claim to make it pass: a claim the documentation does not support is "
                        f"assumed or unknown (DEC-009), and that is the agent's call, not this "
                        f"node's."
                    ),
                )
            )
        if available is not None:
            for evidence_id in claim.evidence_ids:
                if evidence_id not in available:
                    errors.append(
                        ValidationError(
                            object_id=claim.id,
                            field="evidence_ids",
                            rule="evidence references exist (agent-design.md section 14)",
                            message=f"{evidence_id} was not supplied to the extractor",
                        )
                    )
        # `confidence` is enum-typed, so a member check here would be unreachable. DEC-022 is
        # what makes that the whole responsibility: there is no numeric score and no range, so
        # section 8's "confirm confidence is valid" is satisfied by the type and nothing else.

    # -- data flows: false-shaped unknowns ---------------------------------------------------
    for flow in (obj for obj in objects if isinstance(obj, DataFlow)):
        for name in ("encryption_in_transit", "authentication"):
            value = getattr(flow, name)
            if value in _FALSE_LIKE:
                errors.append(
                    ValidationError(
                        object_id=flow.id,
                        field=name,
                        rule="unknown transport security is `unknown`, not false "
                        "(data-model.md section 14)",
                        message=(
                            f"{name} is {value!r}. Absence of a statement is not a statement of "
                            f"absence; use {UNKNOWN!r} where the documentation does not say."
                        ),
                    )
                )
        if flow.source_component_id == flow.destination_component_id:  # pragma: no cover
            errors.append(
                ValidationError(
                    object_id=flow.id,
                    field="source_component_id",
                    rule="a data flow moves data between two components (section 14)",
                    message="source and destination are the same component",
                )
            )

    duplicates = _duplicate_groups(objects)
    for group in duplicates:
        errors.append(
            ValidationError(
                object_id=group[0],
                field="name",
                rule="exact duplicates are detected, not merged (agent-design.md section 8)",
                message=(
                    f"{', '.join(group)} share a normalized name. Reported for a reviewer to "
                    f"decide; merging would be a correction this node does not make."
                ),
            )
        )

    return ContextValidationOutcome(
        errors=tuple(errors),
        triggers=tuple(_triggers(context, objects, previous=previous)),
        unfamiliar_terms=tuple(_unfamiliar_terms(objects)),
        duplicate_groups=tuple(duplicates),
        zone_mismatches=tuple(_zone_mismatches(objects)),
        privilege_extremes=tuple(_privilege_extremes(objects)),
        cross_claim_observations=tuple(_cross_claim_observations(objects)),
    )


def _zone_mismatches(objects: Sequence[DomainModel]) -> list[ZoneMismatch]:
    """DEC-068's cross-claim check: differing zones with no declared crossing, reported.

    Both endpoints must *state* a zone — a flow into a component whose zone is undocumented is
    silence, and silence is not a mismatch. Zones are compared in DEC-056's normalized form so
    `DMZ` and `dmz` are one zone, and nothing is written back.
    """
    components = {obj.id: obj for obj in objects if isinstance(obj, Component)}
    mismatches: list[ZoneMismatch] = []
    for flow in (obj for obj in objects if isinstance(obj, DataFlow)):
        source = components.get(flow.source_component_id)
        destination = components.get(flow.destination_component_id)
        if source is None or destination is None:
            continue
        if not source.deployment_zone or not destination.deployment_zone:
            continue
        if _normalized_name(source.deployment_zone) == _normalized_name(
            destination.deployment_zone
        ):
            continue
        if flow.crosses_trust_boundary_ids:
            continue
        mismatches.append(
            ZoneMismatch(
                flow_id=flow.id,
                source_component_id=source.id,
                destination_component_id=destination.id,
                source_zone=source.deployment_zone,
                destination_zone=destination.deployment_zone,
            )
        )
    return mismatches


# Transport spellings for the transport-conflict check (#526). Documentation, not validation
# (DEC-036): the sets bound what the *check* recognizes, never what a flow may say — a protocol
# outside both sets is simply not checked. Encrypted spellings imply TLS on the wire; the
# "none" family is an explicit statement that the transport is unencrypted.
_ENCRYPTED_PROTOCOLS: Final[frozenset[str]] = frozenset(
    {"https", "tls", "ssh", "sftp", "wss", "grpcs", "ftps", "smtps", "ldaps"}
)
_UNENCRYPTED_STATEMENTS: Final[frozenset[str]] = frozenset(
    {"none", "no", "unencrypted", "cleartext", "plaintext"}
)

# Claim statuses that assert something. `assumed` and `unknown` are DEC-009's outlets and never
# a side of a conflict; `contradicted` and `rejected` are outcomes, already decided.
_ASSERTING_STATUSES: Final[frozenset[ClaimStatus]] = frozenset(
    {ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED, ClaimStatus.USER_CONFIRMED}
)


def _cross_claim_observations(objects: Sequence[DomainModel]) -> list[CrossClaimObservation]:
    """DEC-070's consistency checks (#526): stated disagreements, reported and never corrected.

    Three checks, each requiring both sides to state a value so silence never conflicts:

    - **exposure_conflict**: a flow states `internet_exposed` true while its destination
      component states `internet_accessible` false — two claims about one surface.
    - **transport_conflict**: a flow's protocol implies TLS while its `encryption_in_transit`
      states the unencrypted family. Only the spellings the sets above recognize are checked.
    - **claim_conflict**: two asserting claims share a subject and normalized predicate and
      state different values — the parser-versus-document case DEC-070 anticipated.
    """
    observations: list[CrossClaimObservation] = []
    components = {obj.id: obj for obj in objects if isinstance(obj, Component)}

    for flow in (obj for obj in objects if isinstance(obj, DataFlow)):
        destination = components.get(flow.destination_component_id)
        if (
            flow.internet_exposed is True
            and destination is not None
            and destination.internet_accessible is False
        ):
            observations.append(
                CrossClaimObservation(
                    kind="exposure_conflict",
                    object_ids=(flow.id, destination.id),
                    detail=(
                        f"{flow.id} states internet_exposed=true while its destination "
                        f"{destination.id} states internet_accessible=false. One of the two "
                        f"statements is wrong; a reviewer decides which."
                    ),
                )
            )
        if (
            flow.protocol
            and _normalized_name(flow.protocol) in _ENCRYPTED_PROTOCOLS
            and str(flow.encryption_in_transit) != str(UNKNOWN)
            and _normalized_name(str(flow.encryption_in_transit)) in _UNENCRYPTED_STATEMENTS
        ):
            observations.append(
                CrossClaimObservation(
                    kind="transport_conflict",
                    object_ids=(flow.id,),
                    detail=(
                        f"{flow.id} names protocol {flow.protocol!r}, which implies transport "
                        f"encryption, while stating encryption_in_transit="
                        f"{str(flow.encryption_in_transit)!r}. The two statements disagree."
                    ),
                )
            )

    asserting = [
        claim
        for claim in objects
        if isinstance(claim, ContextClaim) and claim.status in _ASSERTING_STATUSES
    ]
    by_fact: dict[tuple[str | None, str], list[ContextClaim]] = defaultdict(list)
    for claim in asserting:
        by_fact[(claim.subject_id, _normalized_name(claim.predicate))].append(claim)
    for (subject_id, _predicate), claims in sorted(
        by_fact.items(), key=lambda item: (item[0][0] or "", item[0][1])
    ):
        stated_values = {repr(claim.value) for claim in claims}
        if len(claims) < 2 or len(stated_values) < 2:
            continue
        identifiers = tuple(sorted(claim.id for claim in claims))
        subject = subject_id or "the system"
        observations.append(
            CrossClaimObservation(
                kind="claim_conflict",
                object_ids=identifiers,
                detail=(
                    f"{', '.join(identifiers)} assert {claims[0].predicate!r} about {subject} "
                    f"with different values. Two asserted statements about one fact disagree; "
                    f"a reviewer decides which stands."
                ),
            )
        )
    return observations


# What counts as each attack-surface extreme (DEC-068). An actor qualifies through its persona
# where one is stated, or through what its type already says: an `external_attacker` is external
# whatever its `access_level`, and an `administrator` is privileged. Deliberately narrow — a
# check that guessed would mark the extreme represented when nobody represented it.
_ANONYMOUS_OR_EXTERNAL_TYPES: Final[frozenset[str]] = frozenset(
    {"external_attacker", "third_party_service"}
)
_ADMIN_OR_PRIVILEGED_TYPES: Final[frozenset[str]] = frozenset({"administrator"})


def _privilege_extremes(objects: Sequence[DomainModel]) -> list[PrivilegeExtreme]:
    """DEC-068's privilege-extremes check: which extreme no actor represents.

    The extremes of the attack surface are where analysis most often goes silent. This does not
    block and corrects nothing; each entry becomes a `Question`, because whether an unrepresented
    extreme is genuinely out of scope is a judgment about the world.
    """
    actors = [obj for obj in objects if isinstance(obj, Actor)]
    anonymous_or_external = any(
        actor.access_level == "anonymous" or actor.actor_type in _ANONYMOUS_OR_EXTERNAL_TYPES
        for actor in actors
    )
    admin_or_privileged = any(
        actor.access_level == "privileged" or actor.actor_type in _ADMIN_OR_PRIVILEGED_TYPES
        for actor in actors
    )

    extremes: list[PrivilegeExtreme] = []
    if not anonymous_or_external:
        extremes.append(
            PrivilegeExtreme(
                extreme="anonymous_or_external",
                detail=(
                    "No actor in the context is anonymous or external. If the system is "
                    "reachable from outside, who reaches it? If it is not, what establishes "
                    "that?"
                ),
            )
        )
    if not admin_or_privileged:
        extremes.append(
            PrivilegeExtreme(
                extreme="administrative_or_privileged",
                detail=(
                    "No actor in the context is administrative or privileged. Who operates and "
                    "configures the system, and through what?"
                ),
            )
        )
    return extremes


def _duplicate_groups(objects: Sequence[DomainModel]) -> list[tuple[str, ...]]:
    """Identifiers of objects of one type sharing a normalized name. Exact matching only."""
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for obj in objects:
        if not isinstance(obj, Component | Asset | DataFlow | TrustBoundary):
            continue
        grouped[(type(obj).__name__, _normalized_name(obj.name))].append(obj.id)
    return [tuple(sorted(ids)) for ids in grouped.values() if len(ids) > 1]


def _unfamiliar_terms(objects: Sequence[DomainModel]) -> list[str]:
    """Vocabulary terms outside the documented examples. Reported, never rejected (DEC-036).

    The DEC-068 fields are covered on the same terms as the original four: a persona, entry
    point, or classification outside its `KNOWN_*` set is surfaced for a reader and refused for
    nothing. `None` and an empty list are absence, not terms.
    """
    from trace_ai.domain.actor import (
        KNOWN_ACCESS_LEVELS,
        KNOWN_ACTOR_TYPES,
        KNOWN_SKILL_LEVELS,
    )
    from trace_ai.domain.asset import KNOWN_ASSET_TYPES, KNOWN_DATA_CLASSIFICATIONS
    from trace_ai.domain.component import KNOWN_COMPONENT_TYPES, KNOWN_ENTRY_POINT_TYPES
    from trace_ai.domain.trust_boundary import KNOWN_BOUNDARY_TYPES

    checks: list[tuple[type, str, frozenset[str]]] = [
        (Component, "component_type", KNOWN_COMPONENT_TYPES),
        (Component, "entry_point_types", KNOWN_ENTRY_POINT_TYPES),
        (Actor, "actor_type", KNOWN_ACTOR_TYPES),
        (Actor, "skill_level", KNOWN_SKILL_LEVELS),
        (Actor, "access_level", KNOWN_ACCESS_LEVELS),
        (Asset, "asset_type", KNOWN_ASSET_TYPES),
        (Asset, "data_classification", KNOWN_DATA_CLASSIFICATIONS),
        (TrustBoundary, "boundary_type", KNOWN_BOUNDARY_TYPES),
    ]
    found: set[str] = set()
    for obj in objects:
        for model, attribute, known in checks:
            if not isinstance(obj, model):
                continue
            value = getattr(obj, attribute)
            values = value if isinstance(value, list) else [value]
            for term in values:
                if term is not None and term not in known:
                    found.add(f"{attribute}={term}")
    return sorted(found)


def _triggers(
    context: SystemContext,
    objects: Sequence[DomainModel],
    *,
    previous: SystemContext | None,
) -> list[ReviewTrigger]:
    """Section 7's six human-review triggers, computed from what was extracted.

    A trigger is not an error. It is a reason a person should look, and the reviewer decides what it
    means — which is why each carries the objects that caused it rather than a verdict about them.
    """
    triggers: list[ReviewTrigger] = []
    components = [obj for obj in objects if isinstance(obj, Component)]
    boundaries = [obj for obj in objects if isinstance(obj, TrustBoundary)]
    claims = [obj for obj in objects if isinstance(obj, ContextClaim)]
    observations = [obj for obj in objects if isinstance(obj, SourceObservation)]

    contradicted = [claim.id for claim in claims if claim.status is ClaimStatus.CONTRADICTED]
    contradicted += [
        observation.id
        for observation in observations
        if observation.kind is ObservationKind.CONTRADICTION
    ]
    if contradicted:
        triggers.append(
            ReviewTrigger(
                name="contradictory_high_impact_claims",
                object_ids=tuple(sorted(contradicted)),
                detail="the documents disagree and the resolution is a reviewer's decision",
            )
        )

    if not (context.system_purpose or "").strip():
        triggers.append(
            ReviewTrigger(
                name="core_system_purpose_unclear",
                object_ids=(),
                detail="no system purpose was extracted from the documentation",
            )
        )

    uncertain = [
        boundary.id
        for boundary in boundaries
        if not boundary.inside_component_ids and not boundary.outside_component_ids
    ]
    if not boundaries or uncertain:
        triggers.append(
            ReviewTrigger(
                name="major_trust_boundaries_uncertain",
                object_ids=tuple(sorted(uncertain)),
                detail=(
                    "no trust boundaries were extracted"
                    if not boundaries
                    else "a boundary has components on neither side"
                ),
            )
        )

    documented_auth = [
        component.id
        for component in components
        if component.authentication_mechanisms or component.authorization_mechanisms
    ]
    if components and not documented_auth:
        triggers.append(
            ReviewTrigger(
                name="authentication_or_authorization_ambiguous",
                object_ids=(),
                detail="no component records an authentication or authorization mechanism",
            )
        )

    uncited = [component.id for component in components if not component.evidence_ids]
    if uncited:
        triggers.append(
            ReviewTrigger(
                name="significant_component_inferred_rather_than_documented",
                object_ids=tuple(sorted(uncited)),
                detail="a component cites no evidence, so it rests on inference",
            )
        )

    if previous is not None:
        removed = set(previous.component_ids) - set(context.component_ids)
        added = set(context.component_ids) - set(previous.component_ids)
        if removed or added:
            triggers.append(
                ReviewTrigger(
                    name="material_change_from_prior_approved_version",
                    object_ids=tuple(sorted(removed | added)),
                    detail=(
                        f"{len(added)} component(s) added and {len(removed)} removed since the "
                        f"approved revision"
                    ),
                )
            )

    return triggers
