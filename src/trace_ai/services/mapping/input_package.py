"""What the Requirement and Control Mapping agent sees: a threat, the whole catalog, and evidence.

`agent-design.md` section 22 lists what an agent must not have — internet, shell, arbitrary
filesystem, database writes, cloud credentials, dynamic code execution — and section 23 requires
each agent to receive the smallest useful context. Together those say the agent *calls nothing*.
The application assembles a payload and passes it, and this module is that assembler for the
mapping step.

**The whole catalog goes in every call** (DEC-024). There is no deterministic pre-filter and no
candidate set, because the only structured filter field in section 17 — `applicable_technologies` —
is populated on zero of the twenty-three requirements. Narrowing the *input* is also not what
section 12's prohibition asks for: "apply every catalog requirement to every component" describes
an output in which everything is marked applicable. Reading it as an instruction to narrow the
input produces a system that silently never considers most requirements, which is a false-negative
machine whose failure is invisible because the requirement never appears at all.

**A requirement is evaluated through one threat, so the payload is per-threat.** `threat_id` is on
the package and on every mapping the agent returns. The coverage consequence is DEC-024's and is
stated there: a requirement no threat reaches is never evaluated.

**`acceptable_implementations` carries its non-exhaustiveness as data, not as prompt wording.**
`requirements/README.md` says the field lists mechanism classes rather than approved products, and
section 12 makes "treat one implementation example as the only valid control" a prohibited
operation. The framing therefore travels with the values, in the same object, so that a prompt
edit cannot separate them.

**`common_false_positives` is always carried.** DEC-011 records under Tradeoffs that nothing
enforces the field is consulted, and DEC-025 is the enforcement — but a mapping cannot state why an
entry does not apply if the entry was never in the payload. Omitting it here would make DEC-011
unenforceable at the exact point it matters.

**Exceeding the bound stops the run; it never shrinks the request.** The threat package excludes
evidence by identifier and reports it, because a threat that cites fewer passages is still a
correct threat. A mapping run against part of the catalog is not a partial mapping run — it is a
complete-looking one that silently never considered the rest. DEC-024's escalation path is
partition fan-out, in which every partition runs for every threat and nothing is excluded, and
that is an orchestration decision rather than something an assembler may take on its own
(`agent-design.md` section 27).

**Only the approved baseline is assembled.** Section 9's workflow rule covers threat analysis and
everything after it, so the context objects come from the approved revision's identifier lists
(DEC-040) rather than from a store listing that would put a rejected object back.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.control import Control
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.proposals.mapping import MappingProposal
from trace_ai.services.budget import fill_untrusted, schema_overhead
from trace_ai.services.context.input_package import fenced_excerpt
from trace_ai.services.threats.input_package import UnapprovedContextError


def _manifest(excerpts: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The evidence manifest for the trusted region: identifiers and locations, never text."""
    return [
        {
            "evidence_id": excerpt["evidence_id"],
            "document": excerpt.get("source_filename"),
            "location": {
                key: value
                for key, value in (excerpt.get("location") or {}).items()
                if value is not None
            },
        }
        for excerpt in excerpts
    ]


if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.requirement import Requirement
    from trace_ai.domain.system_context import SystemContext
    from trace_ai.domain.threat import Threat
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.services.requirements.loader import LoadedCatalog

__all__ = [
    "ACCEPTABLE_IMPLEMENTATIONS_NOTE",
    "MappingInput",
    "PayloadTooLargeError",
    "UnapprovedContextError",
    "assemble_mapping_input",
]

# Travels with the values, in the payload, in every call. `requirements/README.md` states it and
# `agent-design.md` section 12 makes ignoring it a prohibited operation; carrying it only in the
# prompt would let one edit to one file remove it from every requirement at once.
ACCEPTABLE_IMPLEMENTATIONS_NOTE: Final = (
    "Non-exhaustive. These are example mechanism classes, not an approved set of products. A "
    "control using a mechanism absent from this list is not unsatisfied for that reason."
)


class PayloadTooLargeError(RuntimeError):
    """The assembled mapping payload does not fit, and nothing may be dropped to make it fit."""

    def __init__(self, *, size: int, budget: int, excluded_evidence_ids: Sequence[str]) -> None:
        dropped = (
            f" Fitting it would mean dropping evidence {sorted(excluded_evidence_ids)}."
            if excluded_evidence_ids
            else " The catalog and threat alone exceed the budget, before any evidence."
        )
        super().__init__(
            f"the mapping payload is {size} characters against a budget of {budget}.{dropped} "
            f"A shorter payload is not a smaller version of this request: the whole catalog goes "
            f"in every call (DEC-024), and a run against part of it looks complete and is not. "
            f"Exceeding a ceiling stops the run (agent-design.md section 27); the escalation path "
            f"is partitioning the catalog and running every partition for every threat."
        )
        self.size = size
        self.budget = budget
        self.excluded_evidence_ids = tuple(excluded_evidence_ids)


@dataclass(frozen=True, slots=True)
class MappingInput:
    """The assembled package: a trusted region, a fenced untrusted region, and what is in them.

    Inert by construction. Every field is a string, an integer, a tuple of strings, or a mapping of
    those — there is no store, no index, no open file, and no callable an agent could reach through
    to retrieve something. Section 22 describes retrieval as an application-controlled interface,
    and the strongest form of that is a payload with nothing to call.
    """

    trusted: str
    untrusted: str

    assessment_id: str
    threat_id: str
    catalog_version: str
    """The three keys section 30's caching rules and section 27's `ExecutionRecord` inputs need."""

    requirement_ids: tuple[str, ...]
    control_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    actor_ids: tuple[str, ...]
    data_flow_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...] = ()
    """Cited evidence the budget shed (WS10). The catalog is never shed -- an irreducible overflow
    raises PayloadTooLargeError -- so this names only excerpts, never a requirement."""
    metadata: dict[str, Any] = field(default_factory=dict)

    def referenceable_ids(self) -> frozenset[str]:
        """Every identifier a proposed mapping, control, or gap may name.

        `MappingProposal.validate_references` checks against this, which is how section 13's
        "referenced requirements exist" and "control identifiers exist" responsibilities are met
        for the half of them the package can answer: an identifier outside this set was not
        supplied, so a mapping carrying one is about objects the agent was not given.
        """
        return frozenset(
            {
                self.threat_id,
                *self.requirement_ids,
                *self.control_ids,
                *self.evidence_ids,
                *self.component_ids,
                *self.asset_ids,
                *self.actor_ids,
                *self.data_flow_ids,
            }
        )

    def input_object_ids(self) -> tuple[str, ...]:
        """What went into the call, for `ExecutionRecord.input_object_ids` (section 27).

        Sorted and deduplicated, so two records of the same inputs compare equal. The catalog
        version is not here: it is not an object identifier and it has its own field.
        """
        return tuple(sorted(self.referenceable_ids()))

    def substitutions(self) -> dict[str, str]:
        """What the prompt registry substitutes into the mapping prompt."""
        return {"input.source_content": self.untrusted}


def _requirement_entry(requirement: Requirement) -> dict[str, Any]:
    """One requirement as the mapping step must see it.

    Every field section 12 requires the agent to reason over is present. `default_severity` is
    deliberately absent: DEC-030 gives severity to the reviewer at checkpoint 2 and no node
    proposes one, so showing the mapper a severity would be handing it a judgment section 12
    already prohibits it from making.
    """
    return {
        "id": requirement.id,
        "title": requirement.title,
        "statement": requirement.statement,
        "rationale": requirement.rationale,
        "category": list(requirement.category),
        "status": requirement.status.value,
        "applicable_conditions": list(requirement.applicable_conditions),
        "non_applicable_conditions": list(requirement.non_applicable_conditions),
        "acceptable_implementations": {
            "note": ACCEPTABLE_IMPLEMENTATIONS_NOTE,
            "examples": list(requirement.acceptable_implementations),
        },
        "evidence_expectations": list(requirement.evidence_expectations),
        # DEC-011's distinction, kept where an implementer meets it rather than only in the prompt.
        "common_false_positives": list(requirement.common_false_positives),
    }


def _threat_entry(threat: Threat) -> dict[str, Any]:
    return {
        "id": threat.id,
        "title": threat.title,
        "description": threat.description,
        "category": list(threat.category),
        "methodology": threat.methodology,
        "threat_actor_ids": list(threat.threat_actor_ids),
        "affected_component_ids": list(threat.affected_component_ids),
        "affected_asset_ids": list(threat.affected_asset_ids),
        "related_data_flow_ids": list(threat.related_data_flow_ids),
        "preconditions": list(threat.preconditions),
        "attack_path": list(threat.attack_path),
        "impact": threat.impact,
        "likelihood": threat.likelihood,
        "confidence": threat.confidence.value,
        "evidence_ids": list(threat.evidence_ids),
    }


def _control_entry(control: Control) -> dict[str, Any]:
    """One existing control, with the three fields DEC-026 uses in place of a scope string.

    `provider_component_id`, the protected lists, and `limitations` *are* the inheritance scope.
    `is_documented_inheritance` is carried as a value rather than left for the agent to
    reconstruct: the distinction between a platform control the documentation establishes and one
    nothing establishes is what ForgeFlow's intentional non-findings turn on, and reconstructing it
    from three fields is where it would get collapsed.
    """
    return {
        "id": control.id,
        "name": control.name,
        "description": control.description,
        "control_type": control.control_type.value,
        "provider_component_id": control.provider_component_id,
        "protected_component_ids": list(control.protected_component_ids),
        "protected_asset_ids": list(control.protected_asset_ids),
        "implementation_status": control.implementation_status.value,
        "validation_status": control.validation_status.value,
        "limitations": list(control.limitations),
        "owner": control.owner,
        "is_documented_inheritance": control.is_documented_inheritance,
        "evidence_ids": list(control.evidence_ids),
    }


def _component_entry(component: Component) -> dict[str, Any]:
    return {
        "id": component.id,
        "name": component.name,
        "component_type": component.component_type,
        "description": component.description,
        "technology": list(component.technology),
        "ownership": component.ownership,
        "deployment_zone": component.deployment_zone,
        "internet_accessible": component.internet_accessible,
        "externally_managed": component.externally_managed,
        "data_classifications": list(component.data_classifications),
        "authentication_mechanisms": list(component.authentication_mechanisms),
        "authorization_mechanisms": list(component.authorization_mechanisms),
        "evidence_ids": list(component.evidence_ids),
    }


def _asset_entry(asset: Asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "description": asset.description,
        "data_classification": asset.data_classification,
        "confidentiality_impact": asset.confidentiality_impact,
        "integrity_impact": asset.integrity_impact,
        "availability_impact": asset.availability_impact,
        "component_ids": list(asset.component_ids),
        "evidence_ids": list(asset.evidence_ids),
    }


def _actor_entry(actor: Actor) -> dict[str, Any]:
    return {
        "id": actor.id,
        "name": actor.name,
        "actor_type": actor.actor_type,
        "trust_level": actor.trust_level,
        "capabilities": list(actor.capabilities),
        "authentication_method": actor.authentication_method,
        "evidence_ids": list(actor.evidence_ids),
    }


def _flow_entry(flow: DataFlow) -> dict[str, Any]:
    return {
        "id": flow.id,
        "name": flow.name,
        "source_component_id": flow.source_component_id,
        "destination_component_id": flow.destination_component_id,
        "direction": flow.direction.value,
        "data_types": list(flow.data_types),
        "protocol": flow.protocol,
        "internet_exposed": flow.internet_exposed,
        # `unknown` is a value, not an absence: silence must not read as "not encrypted" (DEC-036).
        "encryption_in_transit": flow.encryption_in_transit,
        "authentication": flow.authentication,
        "crosses_trust_boundary_ids": list(flow.crosses_trust_boundary_ids),
        "evidence_ids": list(flow.evidence_ids),
    }


def _trusted_region(
    *,
    assessment_id: str,
    catalog_version: str,
    threat: dict[str, Any],
    requirements: list[dict[str, Any]],
    architecture: dict[str, list[dict[str, Any]]],
    controls: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> str:
    """The half of the package the agent may take as instruction.

    Application objects only: identifiers the application allocated, on objects a reviewer approved
    at checkpoint 1. No path, no credential, no environment value, no configuration object. Quoted
    source text appears once, inside the fence, and never here.
    """
    sections = [
        "## Assessment",
        "",
        f"assessment_id: {assessment_id}",
        f"requirements_catalog_version: {catalog_version}",
        "",
        "## Threat under evaluation",
        "",
        json.dumps(threat, indent=2, sort_keys=True),
        "",
        "## Requirements catalog",
        "",
        json.dumps(requirements, indent=2, sort_keys=True),
        "",
        "## Existing controls",
        "",
        json.dumps(controls, indent=2, sort_keys=True),
    ]

    for heading, key in (
        ("Components", "components"),
        ("Actors", "actors"),
        ("Assets", "assets"),
        ("Data flows", "data_flows"),
    ):
        sections += [
            "",
            f"## {heading}",
            "",
            json.dumps(architecture[key], indent=2, sort_keys=True),
        ]

    sections += ["", "## Evidence available", "", json.dumps(manifest, indent=2, sort_keys=True)]
    return "\n".join(sections)


def _approved(objects: Sequence[Any], identifiers: Sequence[str]) -> list[Any]:
    """The objects the approved revision names, in the order it names them.

    Membership comes from the revision rather than from the store (DEC-040): a candidate the
    reviewer rejected is absent from these lists, and re-listing the store would put it back.
    """
    by_id = {str(getattr(obj, "id", "")): obj for obj in objects}
    return [by_id[identifier] for identifier in identifiers if identifier in by_id]


def assemble_mapping_input(
    handle: AssessmentHandle,
    *,
    context: SystemContext,
    threat: Threat,
    catalog: LoadedCatalog,
    index: EvidenceIndex,
    evidence_ids: Sequence[str],
    profile: ModelProfile,
) -> MappingInput:
    """Build the mapping agent's input for one threat against one catalog version.

    `evidence_ids` are supplied by the caller rather than discovered here, so that what the agent
    sees is a decision made in one place. `catalog` is a loaded version rather than a directory,
    so a `0.2/` added mid-assessment cannot change what an in-flight run is assessed against.
    """
    if not context.is_approved:
        raise UnapprovedContextError(context.version, step="Requirement and control mapping")

    # Only what the approved revision names, and within that only what this threat reaches. The
    # narrowing is by the threat's own references, which are identifiers the threat validation node
    # already checked against the package it was given -- not a judgment made here.
    components = [
        component
        for component in _approved(handle.objects.list(Component), context.component_ids)
        if component.id in set(threat.affected_component_ids)
    ]
    assets = [
        asset
        for asset in _approved(handle.objects.list(Asset), context.asset_ids)
        if asset.id in set(threat.affected_asset_ids)
    ]
    actors = [
        actor
        for actor in _approved(handle.objects.list(Actor), context.actor_ids)
        if actor.id in set(threat.threat_actor_ids)
    ]
    flows = [
        flow
        for flow in _approved(handle.objects.list(DataFlow), context.data_flow_ids)
        if flow.id in set(threat.related_data_flow_ids)
    ]

    # A control is associated with this threat when it protects a component or an asset the threat
    # affects. Controls carry no revision list of their own -- they are scoped by what they protect
    # (DEC-026), and an approved component is what makes a control part of the approved baseline.
    affected = {component.id for component in components} | {asset.id for asset in assets}
    controls = [
        control
        for control in handle.objects.list(Control)
        if affected
        & (
            {*control.protected_component_ids, *control.protected_asset_ids}
            | ({control.provider_component_id} if control.provider_component_id else set())
        )
    ]

    architecture = {
        "components": [_component_entry(component) for component in components],
        "actors": [_actor_entry(actor) for actor in actors],
        "assets": [_asset_entry(asset) for asset in assets],
        "data_flows": [_flow_entry(flow) for flow in flows],
    }
    requirement_entries = [_requirement_entry(requirement) for requirement in catalog.requirements]
    control_entries = [_control_entry(control) for control in controls]

    excerpts = index.render_for_prompt(list(evidence_ids))
    rendered = [(excerpt["evidence_id"], fenced_excerpt(excerpt)) for excerpt in excerpts]

    def build_trusted(present: Sequence[dict[str, Any]]) -> str:
        return _trusted_region(
            assessment_id=handle.assessment_id,
            catalog_version=catalog.version,
            threat=_threat_entry(threat),
            requirements=requirement_entries,
            architecture=architecture,
            controls=control_entries,
            manifest=_manifest(present),
        )

    # The catalog, the threat, and the schema are the irreducible part: dropping a requirement is a
    # DEC-024 violation, not a smaller version of the request, so it is charged as fixed overhead.
    # Evidence, unlike the catalog, can be shed -- so the payload degrades by dropping excerpts and
    # naming them, and raises only when the irreducible part alone will not fit (WS10).
    irreducible = len(build_trusted(excerpts)) + schema_overhead(MappingProposal)
    if irreducible > profile.max_input_characters:
        raise PayloadTooLargeError(
            size=irreducible + sum(len(block) for _, block in rendered),
            budget=profile.max_input_characters,
            excluded_evidence_ids=[evidence_id for evidence_id, _ in rendered],
        )

    outcome = fill_untrusted(rendered, profile=profile, overhead_characters=irreducible)
    included = set(outcome.included_ids)
    present = [excerpt for excerpt in excerpts if excerpt["evidence_id"] in included]
    trusted = build_trusted(present)

    return MappingInput(
        trusted=trusted,
        untrusted=outcome.untrusted,
        assessment_id=handle.assessment_id,
        threat_id=threat.id,
        catalog_version=catalog.version,
        requirement_ids=tuple(entry["id"] for entry in requirement_entries),
        control_ids=tuple(entry["id"] for entry in control_entries),
        evidence_ids=outcome.included_ids,
        excluded_evidence_ids=outcome.excluded_ids,
        component_ids=tuple(entry["id"] for entry in architecture["components"]),
        asset_ids=tuple(entry["id"] for entry in architecture["assets"]),
        actor_ids=tuple(entry["id"] for entry in architecture["actors"]),
        data_flow_ids=tuple(entry["id"] for entry in architecture["data_flows"]),
        metadata={
            "context_version": context.version,
            "requirements": len(requirement_entries),
            "controls": len(control_entries),
            "components": len(architecture["components"]),
            "actors": len(architecture["actors"]),
            "assets": len(architecture["assets"]),
            "data_flows": len(architecture["data_flows"]),
            "evidence": len(excerpts),
            "trusted_characters": len(trusted),
            **outcome.metadata(),
        },
    )
