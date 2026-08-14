"""The Mapping Validation node: the place `unverified` is stopped from becoming `unmet`.

`agent-design.md` section 13 lists ten responsibilities for a deterministic node between the
mapping agent and evidence validation. One of them is load-bearing for the whole project —
"Prevent unverified from silently becoming unmet" — and `data-model.md` section 19 says the same
thing from the data side: an unverified requirement does not automatically create a finding.

**This node is the one validator that changes its input, and only in one direction.** The context
and threat validators report and route and never correct, because a validator making security
judgments with no evidence and no reviewer produces corrections nobody can see. DEC-013 sanctions
exactly one change here — lowering an unsupported `unmet` to `unverified` — and DEC-046 makes it
legible by recording what it was and why. Nothing else is edited: a duplicate is surfaced, not
deduplicated; a conflict is flagged, not resolved.

**Half of DEC-013's rule runs here and half runs later, and the split is the pipeline's order**
(DEC-046). Conditions 1 and 4 — cite a passage, rest on no unresolved contradiction — read the
mapping, the catalog, and the source observations, all of which exist now. Conditions 2 and 3 read
`EvidenceAssessment`, which the Evidence Validation phase produces *after* this one. Checking them
here against a missing assessment would downgrade every `unmet` in every run and look like a strict
evidence rule rather than like a field that is not populated yet.

**Requirement existence is checked against the assessment's pinned catalog version**, not against
whatever is on disk. A mapping citing a requirement from another version is an error rather than a
warning, because the requirement text may have changed underneath it and the mapping's rationale
was written against text nobody can now recover.

**A run of nothing but `unverified` and `not_applicable` passes cleanly.** No warning, no flag, no
trigger. `data-model.md` section 19 states that a high proportion of `unverified` is the expected
result of assessing ordinary architecture documentation, and a validator that reported it would be
the mechanism by which the expected outcome came to read as a defect.

**Several of section 13's checks are already unreachable through the schema, and they stay.**
`ControlMapping` refuses a blank `applicability_reason` and refuses `satisfied`,
`partially_satisfied`, or `unmet` with no cited evidence, so a mapping violating those cannot be
constructed. Section 13 nevertheless assigns those responsibilities to this node, and a payload can
reach a validator by a path that skipped construction — a stored object read back, a future
loader, a test. The checks are the second line rather than the first, `test_mapping_validation.py`
exercises them through `model_construct` and says so, and which line is which is stated here so the
next reader does not conclude the node is doing the work the schema is doing.

**Errors are returned, not raised**, carrying an `ErrorClass` so the generating node routes on a
classification rather than on a message.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.control import ControlType, ImplementationStatus
from trace_ai.domain.control_mapping import (
    EVIDENCED_SATISFACTION_STATUSES,
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.source_observation import ObservationKind
from trace_ai.workflow.context_validation import ReviewTrigger
from trace_ai.workflow.errors import ErrorClass

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from trace_ai.domain.control import Control
    from trace_ai.domain.requirement import Requirement
    from trace_ai.domain.source_observation import SourceObservation
    from trace_ai.domain.threat import Threat

__all__ = [
    "SECTION_12_TRIGGERS",
    "ConflictingMappings",
    "Downgrade",
    "DuplicateMappings",
    "MappingValidationError",
    "MappingValidationOutcome",
    "Suppression",
    "apply_downgrades",
    "validate_mappings",
]

# `agent-design.md` section 12's human-review triggers, in the document's order.
SECTION_12_TRIGGERS: Final[tuple[str, ...]] = (
    "high_impact_requirement_has_contradictory_evidence",
    "inherited_control_scope_unclear",
    "compensating_control_requires_business_judgment",
    "applicability_depends_on_unknown_deployment_details",
    "requirement_may_be_satisfied_by_undocumented_enterprise_platform",
)

# The reasons a proposed `unmet` is lowered. Named constants rather than sentences written at the
# call site, because the value is stored on the mapping and a metric will group by it.
UNMET_WITHOUT_EVIDENCE: Final = (
    "unmet was proposed with no cited evidence. DEC-013 condition 1: absence cannot be quoted, "
    "so silence resolves to unverified."
)
UNMET_ON_UNRESOLVED_CONTRADICTION: Final = (
    "unmet was proposed while an unresolved contradiction bears on the cited evidence. DEC-013 "
    "condition 4: the conclusion rests on passages that disagree."
)
UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES: Final = (
    "unmet was proposed against a requirement carrying common_false_positives entries, and the "
    "mapping does not say why none of them applies (DEC-025)."
)


@dataclass(frozen=True, slots=True)
class MappingValidationError:
    """One problem with one mapping, named precisely enough to fix without reading the node."""

    mapping_id: str
    field: str
    rule: str
    message: str
    error_class: ErrorClass = ErrorClass.SCHEMA_VALIDATION_FAILURE

    @property
    def retryable(self) -> bool:
        from trace_ai.workflow.errors import RETRYABLE

        return self.error_class in RETRYABLE


@dataclass(frozen=True, slots=True)
class Downgrade:
    """One `unmet` the evidence rules did not support, and the reason it was lowered.

    Produced by validation and applied by `apply_downgrades`, which builds a new mapping rather
    than mutating one: domain objects are frozen, and `model_validate` is the only path that
    revalidates (`CLAUDE.md`).
    """

    mapping_id: str
    from_status: SatisfactionStatus
    to_status: SatisfactionStatus
    reason: str


@dataclass(frozen=True, slots=True)
class Suppression:
    """A conclusion the mapping agent declined, carried through validation (DEC-025).

    Surfaced rather than merely left on the object, so `evaluation-plan.md` section 8's
    false-negative measurement has a list to read without walking every mapping.
    """

    mapping_id: str
    requirement_id: str
    conclusion: str
    entry: str


@dataclass(frozen=True, slots=True)
class DuplicateMappings:
    """Two or more mappings for one threat-requirement pair. Surfaced, never deduplicated.

    Section 13 says "detect duplicate mappings" and stops there. Collapsing them would discard
    whichever rationale the collapse did not keep, and the two rationales are the interesting part
    — a genuine duplicate has two ways of saying the same thing, and a mistake has two different
    conclusions, which is the conflict case below.
    """

    threat_id: str
    requirement_id: str
    mapping_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConflictingMappings:
    """One requirement resolving to different satisfaction statuses for one threat."""

    threat_id: str
    requirement_id: str
    mapping_ids: tuple[str, ...]
    statuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MappingValidationOutcome:
    """What validated, what was lowered, what looks duplicated, and why a person should look."""

    errors: tuple[MappingValidationError, ...] = ()
    triggers: tuple[ReviewTrigger, ...] = ()
    downgrades: tuple[Downgrade, ...] = ()
    suppressions: tuple[Suppression, ...] = ()
    duplicates: tuple[DuplicateMappings, ...] = ()
    conflicts: tuple[ConflictingMappings, ...] = ()
    undiscriminated_threat_ids: tuple[str, ...] = ()
    """Threats for which every mapping is `applicable` — section 12's failure condition, which is
    about the shape of the output and not about any one mapping."""

    @property
    def valid(self) -> bool:
        """Whether the mapping set may move on to evidence validation.

        A downgrade does not block: it is the correction, already applied. Duplicates and conflicts
        do not block either — both are things for a person to look at, and neither makes the
        mappings unusable.
        """
        return not self.blocking_errors

    @property
    def blocking_errors(self) -> tuple[MappingValidationError, ...]:
        return tuple(
            error
            for error in self.errors
            if error.error_class is not ErrorClass.INSUFFICIENT_EVIDENCE
        )

    @property
    def clean(self) -> bool:
        """Nothing to report at all — the ordinary shape of an assessment under DEC-009.

        A run of `unverified` and `not_applicable` mappings reaches here, and it must: the whole
        point of `unverified` is that it is the honest answer, and a validator that emitted a
        warning for it would teach every reader to treat the honest answer as a problem.
        """
        return not (
            self.errors
            or self.triggers
            or self.downgrades
            or self.duplicates
            or self.conflicts
            or self.undiscriminated_threat_ids
        )


def _wrong_catalog_version_error(
    mapping: ControlMapping, *, pinned: str, seen_in: str | None
) -> MappingValidationError:
    where = (
        f"it belongs to catalog version {seen_in!r}"
        if seen_in
        else "it belongs to no version this assessment loaded"
    )
    return MappingValidationError(
        mapping_id=mapping.id,
        field="requirement_id",
        rule="referenced requirements exist in the assessment's catalog version "
        "(agent-design.md section 13; data-model.md section 5)",
        message=(
            f"requirement {mapping.requirement_id!r} is not in catalog version {pinned!r}; "
            f"{where}. A requirement's text may differ between versions, so a mapping written "
            f"against another version cites a statement nobody can now recover."
        ),
        error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
    )


def _reference_errors(
    mapping: ControlMapping,
    *,
    requirements: dict[str, Requirement],
    catalog_version: str,
    threat_ids: set[str],
    control_ids: set[str],
) -> list[MappingValidationError]:
    """Section 13's first three responsibilities: requirements, threats, and controls exist."""
    errors: list[MappingValidationError] = []

    requirement = requirements.get(mapping.requirement_id)
    if requirement is None:
        errors.append(_wrong_catalog_version_error(mapping, pinned=catalog_version, seen_in=None))
    elif requirement.catalog_version != catalog_version:
        errors.append(
            _wrong_catalog_version_error(
                mapping, pinned=catalog_version, seen_in=requirement.catalog_version
            )
        )

    if mapping.threat_id not in threat_ids:
        errors.append(
            MappingValidationError(
                mapping_id=mapping.id,
                field="threat_id",
                rule="referenced threats exist (agent-design.md section 13)",
                message=f"threat {mapping.threat_id!r} is not in this assessment.",
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        )

    missing = sorted(set(mapping.control_ids) - control_ids)
    if missing:
        errors.append(
            MappingValidationError(
                mapping_id=mapping.id,
                field="control_ids",
                rule="control identifiers exist (agent-design.md section 13)",
                message=f"these controls are not in this assessment: {missing}.",
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        )

    return errors


def _state_errors(mapping: ControlMapping) -> list[MappingValidationError]:
    """Permitted states and a present rationale.

    The enums make an impermissible state unrepresentable, so what is left to check is the one
    thing a string field cannot enforce on its own: a rationale that is present but blank. Section
    12 makes "requirements are applied without an applicability rationale" a failure condition, and
    a whitespace rationale satisfies `min_length=1` while saying nothing.
    """
    errors: list[MappingValidationError] = []

    if not mapping.applicability_reason.strip():
        errors.append(
            MappingValidationError(
                mapping_id=mapping.id,
                field="applicability_reason",
                rule="applicability rationales are enforced (agent-design.md section 13)",
                message=(
                    "applicability_reason is blank. Say why this requirement does or does not "
                    "apply to this threat, referring to its applicable_conditions or "
                    "non_applicable_conditions."
                ),
            )
        )

    if mapping.satisfaction_status in EVIDENCED_SATISFACTION_STATUSES and not mapping.evidence_ids:
        errors.append(
            MappingValidationError(
                mapping_id=mapping.id,
                field="evidence_ids",
                rule="the evidence policy is enforced (agent-design.md section 13; DEC-013)",
                message=(
                    f"satisfaction_status {mapping.satisfaction_status.value!r} cites no "
                    f"evidence. Absence of evidence resolves to 'unverified' (DEC-009)."
                ),
            )
        )

    if (
        mapping.applicability_status is ApplicabilityStatus.NOT_APPLICABLE
        and mapping.satisfaction_status
        not in {
            SatisfactionStatus.NOT_APPLICABLE,
            SatisfactionStatus.UNVERIFIED,
        }
    ):
        errors.append(
            MappingValidationError(
                mapping_id=mapping.id,
                field="satisfaction_status",
                rule="non-applicability conditions are not ignored "
                "(agent-design.md section 12, Prohibited operations)",
                message=(
                    f"the requirement is not applicable and satisfaction_status is "
                    f"{mapping.satisfaction_status.value!r}. A requirement that does not apply "
                    f"is not satisfied, partially satisfied, or unmet by this system."
                ),
            )
        )

    return errors


def _contradicted_evidence_ids(observations: Iterable[SourceObservation]) -> set[str]:
    """Evidence cited by an unresolved contradiction (DEC-013 condition 4).

    An observation the reviewer has approved or rejected is resolved: approval records that the
    contradiction was examined. What is left is `candidate`, which is a disagreement nobody has
    looked at.
    """
    return {
        evidence_id
        for observation in observations
        if observation.kind is ObservationKind.CONTRADICTION
        and observation.status is ObjectStatus.CANDIDATE
        for evidence_id in observation.evidence_ids
    }


def _downgrade_reason(
    mapping: ControlMapping,
    *,
    requirement: Requirement | None,
    contradicted: set[str],
) -> str | None:
    """Which DEC-013 condition this `unmet` fails, if any, among those checkable here.

    Conditions 2 and 3 are absent by design: both read `EvidenceAssessment`, which the Evidence
    Validation phase produces after this one. DEC-046 records the split and why checking them
    against a missing assessment would be worse than not checking them.
    """
    if mapping.satisfaction_status is not SatisfactionStatus.UNMET:
        return None

    if not mapping.evidence_ids:
        return UNMET_WITHOUT_EVIDENCE

    if contradicted & set(mapping.evidence_ids):
        return UNMET_ON_UNRESOLVED_CONTRADICTION

    # DEC-025's structural check. Not an attempt to decide whether an entry *matches* -- that is a
    # semantic judgment free text cannot support, and a node making it would be a model call in a
    # node section 4 classifies as deterministic. The check is whether the mapping addressed the
    # field at all.
    if (
        requirement is not None
        and requirement.common_false_positives
        and not mapping.suppressed_by
        and not _mentions_false_positives(mapping, requirement)
    ):
        return UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES

    return None


def _mentions_false_positives(mapping: ControlMapping, requirement: Requirement) -> bool:
    """Whether the mapping's own text addresses the requirement's false-positive entries.

    Structural rather than semantic: it looks for the field being named, or for an assumption or
    rationale quoting one of the entries. An agent can satisfy this with a plausible sentence while
    being wrong, and DEC-025 says so under Tradeoffs. What it cannot do is never look.
    """
    text = " ".join([mapping.applicability_reason, *mapping.assumptions]).casefold()
    if "common_false_positives" in text or "false positive" in text:
        return True
    return any(entry.casefold() in text for entry in requirement.common_false_positives)


def _groups(mappings: Sequence[ControlMapping]) -> dict[tuple[str, str], list[ControlMapping]]:
    grouped: dict[tuple[str, str], list[ControlMapping]] = defaultdict(list)
    for mapping in mappings:
        grouped[(mapping.threat_id, mapping.requirement_id)].append(mapping)
    return grouped


def _undiscriminated(mappings: Sequence[ControlMapping]) -> tuple[str, ...]:
    """Threats whose every mapping is `applicable` — section 12's failure condition.

    Only threats with more than one mapping are considered. A threat with a single `applicable`
    mapping has discriminated: it declined to map the rest of the catalog, and the absence of those
    mappings is the discrimination. Flagging it would fire on the most focused output there is.
    """
    per_threat: dict[str, list[ApplicabilityStatus]] = defaultdict(list)
    for mapping in mappings:
        per_threat[mapping.threat_id].append(mapping.applicability_status)

    return tuple(
        sorted(
            threat_id
            for threat_id, statuses in per_threat.items()
            if len(statuses) > 1
            and all(status is ApplicabilityStatus.APPLICABLE for status in statuses)
        )
    )


def _triggers(
    mappings: Sequence[ControlMapping],
    *,
    controls: dict[str, Control],
    contradicted: set[str],
    requirements: dict[str, Requirement],
) -> list[ReviewTrigger]:
    """Section 12's human-review triggers, for the ones this node can detect deterministically."""
    triggers: list[ReviewTrigger] = []

    contradictory = sorted(
        {
            mapping.id
            for mapping in mappings
            if contradicted & set(mapping.evidence_ids)
            and (requirements.get(mapping.requirement_id) is not None)
        }
    )
    if contradictory:
        triggers.append(
            ReviewTrigger(
                name=SECTION_12_TRIGGERS[0],
                object_ids=tuple(contradictory),
                detail=(
                    "A mapping rests on evidence an unresolved contradiction bears on. Whether "
                    "the requirement is met depends on which passage is right, and no rule here "
                    "can choose."
                ),
            )
        )

    unclear_scope = sorted(
        {
            mapping.id
            for mapping in mappings
            for control_id in mapping.control_ids
            if (control := controls.get(control_id)) is not None
            and control.control_type is ControlType.INHERITED
            and not control.is_documented_inheritance
        }
    )
    if unclear_scope:
        triggers.append(
            ReviewTrigger(
                name=SECTION_12_TRIGGERS[1],
                object_ids=tuple(unclear_scope),
                detail=(
                    "A mapping relies on an inherited control the documentation does not "
                    "establish (DEC-026). Whether the platform provides it is a question for "
                    "someone who can ask the platform."
                ),
            )
        )

    compensating = sorted(
        {
            mapping.id
            for mapping in mappings
            for control_id in mapping.control_ids
            if (control := controls.get(control_id)) is not None
            and control.control_type is ControlType.COMPENSATING
        }
    )
    if compensating:
        triggers.append(
            ReviewTrigger(
                name=SECTION_12_TRIGGERS[2],
                object_ids=tuple(compensating),
                detail=(
                    "A compensating control is cited. Whether it compensates enough is a business "
                    "judgment, and the documents do not contain one."
                ),
            )
        )

    unknown_applicability = sorted(
        {
            mapping.id
            for mapping in mappings
            if mapping.applicability_status
            in {ApplicabilityStatus.UNKNOWN, ApplicabilityStatus.CONDITIONALLY_APPLICABLE}
        }
    )
    if unknown_applicability:
        triggers.append(
            ReviewTrigger(
                name=SECTION_12_TRIGGERS[3],
                object_ids=tuple(unknown_applicability),
                detail=(
                    "Whether the requirement applies depends on something the documentation does "
                    "not settle. A reviewer who knows the deployment can settle it in a sentence."
                ),
            )
        )

    platform = sorted(
        {
            mapping.id
            for mapping in mappings
            if mapping.satisfaction_status is SatisfactionStatus.UNVERIFIED
            and any(
                (control := controls.get(control_id)) is not None
                and control.implementation_status
                in {ImplementationStatus.CLAIMED, ImplementationStatus.UNKNOWN}
                for control_id in mapping.control_ids
            )
        }
    )
    if platform:
        triggers.append(
            ReviewTrigger(
                name=SECTION_12_TRIGGERS[4],
                object_ids=tuple(platform),
                detail=(
                    "A control is claimed but not established, so the requirement may be "
                    "satisfied by an enterprise platform nobody documented. That is a question, "
                    "not a gap in the system."
                ),
            )
        )

    return triggers


def validate_mappings(
    mappings: Sequence[ControlMapping],
    *,
    catalog_version: str,
    requirements: Sequence[Requirement],
    threats: Sequence[Threat],
    controls: Sequence[Control] = (),
    observations: Sequence[SourceObservation] = (),
) -> MappingValidationOutcome:
    """Validate a set of candidate mappings. Returns problems, proposals, and downgrades.

    `mappings` are read and never written; `apply_downgrades` builds the edited objects. Nothing
    here makes a model call, and no provider SDK is imported.

    `requirements` are the assessment's pinned catalog version, passed rather than loaded, so that
    a `0.2/` appearing on disk mid-run cannot change what this run is validated against.
    """
    by_id = {requirement.id: requirement for requirement in requirements}
    threat_ids = {threat.id for threat in threats}
    control_by_id = {control.id: control for control in controls}
    contradicted = _contradicted_evidence_ids(observations)

    errors: list[MappingValidationError] = []
    downgrades: list[Downgrade] = []
    suppressions: list[Suppression] = []

    for mapping in mappings:
        errors.extend(
            _reference_errors(
                mapping,
                requirements=by_id,
                catalog_version=catalog_version,
                threat_ids=threat_ids,
                control_ids=set(control_by_id),
            )
        )
        errors.extend(_state_errors(mapping))

        reason = _downgrade_reason(
            mapping,
            requirement=by_id.get(mapping.requirement_id),
            contradicted=contradicted,
        )
        if reason is not None:
            downgrades.append(
                Downgrade(
                    mapping_id=mapping.id,
                    from_status=mapping.satisfaction_status,
                    to_status=SatisfactionStatus.UNVERIFIED,
                    reason=reason,
                )
            )

        if mapping.suppressed_conclusion and mapping.suppressed_by:
            suppressions.append(
                Suppression(
                    mapping_id=mapping.id,
                    requirement_id=mapping.requirement_id,
                    conclusion=mapping.suppressed_conclusion,
                    entry=mapping.suppressed_by,
                )
            )

    duplicates: list[DuplicateMappings] = []
    conflicts: list[ConflictingMappings] = []
    for (threat_id, requirement_id), group in sorted(_groups(mappings).items()):
        if len(group) < 2:
            continue
        identifiers = tuple(sorted(mapping.id for mapping in group))
        duplicates.append(
            DuplicateMappings(
                threat_id=threat_id, requirement_id=requirement_id, mapping_ids=identifiers
            )
        )
        statuses = Counter(mapping.satisfaction_status.value for mapping in group)
        if len(statuses) > 1:
            conflicts.append(
                ConflictingMappings(
                    threat_id=threat_id,
                    requirement_id=requirement_id,
                    mapping_ids=identifiers,
                    statuses=tuple(sorted(statuses)),
                )
            )

    return MappingValidationOutcome(
        errors=tuple(errors),
        triggers=tuple(
            _triggers(
                mappings,
                controls=control_by_id,
                contradicted=contradicted,
                requirements=by_id,
            )
        ),
        downgrades=tuple(downgrades),
        suppressions=tuple(suppressions),
        duplicates=tuple(duplicates),
        conflicts=tuple(conflicts),
        undiscriminated_threat_ids=_undiscriminated(mappings),
    )


def apply_downgrades(
    mappings: Sequence[ControlMapping], outcome: MappingValidationOutcome
) -> list[ControlMapping]:
    """The mapping set with every downgrade applied and recorded (DEC-013, DEC-046).

    New objects, not mutated ones: domain objects are frozen, and `model_validate` is the path a
    human- or application-supplied change takes so that the schema sees it (`CLAUDE.md`). Every
    mapping is returned, in the order given, so the caller persists one list rather than reconciling
    two.
    """
    by_id = {downgrade.mapping_id: downgrade for downgrade in outcome.downgrades}
    applied: list[ControlMapping] = []

    for mapping in mappings:
        downgrade = by_id.get(mapping.id)
        if downgrade is None:
            applied.append(mapping)
            continue
        applied.append(
            ControlMapping.model_validate(
                {
                    **mapping.model_dump(),
                    "satisfaction_status": downgrade.to_status,
                    "downgraded_from": downgrade.from_status,
                    "downgrade_reason": downgrade.reason,
                    # The downgraded status asserts nothing, so its evidence is no longer a
                    # citation for a conclusion. It stays: the passages the agent thought relevant
                    # are what a reviewer needs in order to disagree with the downgrade.
                }
            )
        )

    return applied
