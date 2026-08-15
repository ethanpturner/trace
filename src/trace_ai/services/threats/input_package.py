"""What the Threat Analysis agent sees: an approved architecture, and evidence behind a fence.

`agent-design.md` section 23 gives this agent three things -- the approved context, the relevant
architecture objects, and selected supporting evidence -- and the reasons it gives for the limit
are the same ones as everywhere else: fewer tokens, less cross-contamination, less irrelevant
reasoning, less prompt-injection exposure, less cost, less latency.

**The approved context is application data; the evidence is not.** This is the one structural
difference from the extractor's package, and it is worth stating because it looks like an
exception to the fence rule and is not. Components, assets, flows, and boundaries reached this
package through the Context Extraction node, the Context Validation node, and a human reviewer's
approval at checkpoint 1. They are objects the application owns, carrying identifiers the
application allocated. Quoted source text has been through none of that, so it stays inside the
fence, and `neutralize_fence` is imported from the extractor's package rather than reimplemented.

**Only an approved revision is assembled.** `current-architecture.md` section 5.6 has threat
analysis reason from the approved baseline rather than reinterpreting the documents, and
`assemble_threat_input` refuses an unapproved one by name. The alternative is a run that produces
threats against a context nobody signed off, which looks identical to a correct run in every
artifact it leaves behind.

**Rejected objects are excluded, and the identifier lists are the authority.** DEC-040 recomputes
an approved revision's membership from the store at approval, so an object the reviewer rejected is
absent from those lists. This module reads the lists rather than re-listing the store, because
re-listing would put the rejected object back.

**A budget overrun names what was dropped.** Evidence is excluded by identifier and reported, never
truncated mid-excerpt. Architecture objects are never dropped: a threat is asked to name the
components it affects, and a package that quietly omitted one would be asking the agent to
reference an identifier it was not given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.budget import fill_untrusted, schema_overhead
from trace_ai.services.context.input_package import fenced_excerpt


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

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.system_context import SystemContext
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import EvidenceIndex

__all__ = ["ThreatAnalysisInput", "UnapprovedContextError", "assemble_threat_input"]


class UnapprovedContextError(RuntimeError):
    """A step after checkpoint 1 was asked to reason from a context nobody approved.

    One class rather than one per step. `agent-design.md` section 9 states the rule once — threat
    analysis *and everything after it* works from the approved baseline — so `step` names the
    caller and the rest of the sentence is the same wherever it is raised. Two classes would be two
    places to keep the DEC-005 citation correct, and the one that stopped being updated would be
    the one whose message stopped explaining why the run stopped.
    """

    def __init__(self, version: int, *, step: str = "Threat analysis") -> None:
        super().__init__(
            f"system context version {version} is not approved. {step} reasons from the "
            f"approved baseline (current-architecture.md section 5.6), and checkpoint 1 is a phase "
            f"in the transition table rather than a step a node may skip (DEC-005)."
        )
        self.version = version
        self.step = step


@dataclass(frozen=True, slots=True)
class ThreatAnalysisInput:
    """The assembled package: a trusted region, a fenced untrusted region, and what was dropped."""

    trusted: str
    untrusted: str
    evidence_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    actor_ids: tuple[str, ...]
    data_flow_ids: tuple[str, ...]
    trust_boundary_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return not self.excluded_evidence_ids

    def referenceable_ids(self) -> frozenset[str]:
        """Every identifier a proposed threat may name.

        The validation the node runs against this is the answer to `agent-design.md` section 10's
        prohibition on inventing components: an identifier outside this set was not supplied, so a
        threat carrying one is about a system the agent was not given.
        """
        return frozenset(
            {
                *self.component_ids,
                *self.asset_ids,
                *self.actor_ids,
                *self.data_flow_ids,
                *self.evidence_ids,
            }
        )

    def substitutions(self) -> dict[str, str]:
        """What the prompt registry substitutes into `generate-scenario-threats-v1`."""
        return {"input.source_content": self.untrusted}


def _ordered(objects: Sequence[DomainModel], identifiers: Sequence[str]) -> list[DomainModel]:
    """The objects named by `identifiers`, in the order the approved revision lists them.

    Membership comes from the revision rather than from the store (DEC-040), so a rejected object
    is absent. An identifier the revision names and the store does not hold is skipped here and
    counted in the package metadata; `SystemContext.validate_against` is what reports it as a
    problem, and duplicating that report in an assembler would give it two owners.
    """
    by_id = {str(getattr(obj, "id", "")): obj for obj in objects}
    return [by_id[identifier] for identifier in identifiers if identifier in by_id]


def _components(objects: Sequence[DomainModel]) -> list[dict[str, Any]]:
    return [
        {
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
        for component in objects
        if isinstance(component, Component)
    ]


def _assets(objects: Sequence[DomainModel]) -> list[dict[str, Any]]:
    return [
        {
            "id": asset.id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "description": asset.description,
            "confidentiality_impact": asset.confidentiality_impact,
            "integrity_impact": asset.integrity_impact,
            "availability_impact": asset.availability_impact,
            "data_classification": asset.data_classification,
            "owner": asset.owner,
            "component_ids": list(asset.component_ids),
            "evidence_ids": list(asset.evidence_ids),
        }
        for asset in objects
        if isinstance(asset, Asset)
    ]


def _actors(objects: Sequence[DomainModel]) -> list[dict[str, Any]]:
    return [
        {
            "id": actor.id,
            "name": actor.name,
            "actor_type": actor.actor_type,
            "trust_level": actor.trust_level,
            "capabilities": list(actor.capabilities),
            "authentication_method": actor.authentication_method,
            "evidence_ids": list(actor.evidence_ids),
        }
        for actor in objects
        if isinstance(actor, Actor)
    ]


def _flows(objects: Sequence[DomainModel]) -> list[dict[str, Any]]:
    return [
        {
            "id": flow.id,
            "name": flow.name,
            "source_component_id": flow.source_component_id,
            "destination_component_id": flow.destination_component_id,
            "direction": flow.direction.value,
            "data_types": list(flow.data_types),
            "protocol": flow.protocol,
            "internet_exposed": flow.internet_exposed,
            # `unknown` is a value here, not an absence. DEC-036 and section 14 both refuse to let
            # silence read as "not encrypted" or as "encrypted".
            "encryption_in_transit": flow.encryption_in_transit,
            "authentication": flow.authentication,
            "crosses_trust_boundary_ids": list(flow.crosses_trust_boundary_ids),
            "evidence_ids": list(flow.evidence_ids),
        }
        for flow in objects
        if isinstance(flow, DataFlow)
    ]


def _boundaries(objects: Sequence[DomainModel]) -> list[dict[str, Any]]:
    return [
        {
            "id": boundary.id,
            "name": boundary.name,
            "boundary_type": boundary.boundary_type,
            "description": boundary.description,
            "inside_component_ids": list(boundary.inside_component_ids),
            "outside_component_ids": list(boundary.outside_component_ids),
            "controls": list(boundary.controls),
            "evidence_ids": list(boundary.evidence_ids),
        }
        for boundary in objects
        if isinstance(boundary, TrustBoundary)
    ]


def _claims(objects: Sequence[DomainModel]) -> list[dict[str, Any]]:
    return [
        {
            "id": claim.id,
            "subject_type": claim.subject_type,
            "subject_id": claim.subject_id,
            "predicate": claim.predicate,
            "value": claim.value,
            "status": claim.status.value,
            "confidence": claim.confidence.value,
            "rationale": claim.rationale,
            "evidence_ids": list(claim.evidence_ids),
        }
        for claim in objects
        if isinstance(claim, ContextClaim)
    ]


def _trusted_region(
    *,
    assessment_name: str,
    methodology: str,
    context: SystemContext,
    architecture: dict[str, list[dict[str, Any]]],
    manifest: list[dict[str, Any]],
) -> str:
    """The half of the package the agent may take as instruction.

    It carries the approved architecture and a manifest of which evidence is present -- never the
    excerpt text, which appears once, inside the fence.
    """
    sections = [
        "## Assessment",
        "",
        f"name: {assessment_name}",
        f"threat_methodology: {methodology}",
        "",
        "## Approved system context",
        "",
        json.dumps(
            {
                "version": context.version,
                "approved_at": context.approved_at.isoformat() if context.approved_at else None,
                "system_name": context.system_name,
                "system_purpose": context.system_purpose,
                "business_criticality": context.business_criticality,
                "environment": list(context.environment),
                "deployment_model": context.deployment_model,
                "data_classifications": list(context.data_classifications),
            },
            indent=2,
            sort_keys=True,
        ),
    ]

    for heading, key in (
        ("Components", "components"),
        ("Actors", "actors"),
        ("Assets", "assets"),
        ("Data flows", "data_flows"),
        ("Trust boundaries", "trust_boundaries"),
        ("Context claims", "context_claims"),
    ):
        sections += [
            "",
            f"## {heading}",
            "",
            json.dumps(architecture[key], indent=2, sort_keys=True),
        ]

    sections += ["", "## Evidence available", "", json.dumps(manifest, indent=2, sort_keys=True)]
    return "\n".join(sections)


def assemble_threat_input(
    handle: AssessmentHandle,
    *,
    context: SystemContext,
    index: EvidenceIndex,
    evidence_ids: Sequence[str],
    profile: ModelProfile,
    assessment_name: str,
    threat_methodology: str,
) -> ThreatAnalysisInput:
    """Build the threat agent's input from an approved context and the evidence behind it.

    `evidence_ids` are supplied by the caller rather than discovered here, so what the agent sees
    is a decision made in one place. Nothing in the package is a path, a credential, or a
    configuration object.
    """
    if not context.is_approved:
        raise UnapprovedContextError(context.version)

    components = _ordered(handle.objects.list(Component), context.component_ids)
    actors = _ordered(handle.objects.list(Actor), context.actor_ids)
    assets = _ordered(handle.objects.list(Asset), context.asset_ids)
    flows = _ordered(handle.objects.list(DataFlow), context.data_flow_ids)
    boundaries = _ordered(handle.objects.list(TrustBoundary), context.trust_boundary_ids)
    claims = _ordered(handle.objects.list(ContextClaim), context.context_claim_ids)

    architecture = {
        "components": _components(components),
        "actors": _actors(actors),
        "assets": _assets(assets),
        "data_flows": _flows(flows),
        "trust_boundaries": _boundaries(boundaries),
        "context_claims": _claims(claims),
    }

    excerpts = index.render_for_prompt(list(evidence_ids))

    # The trusted region (the architecture, the approved context, the manifest) and the schema
    # export share the input allowance with the excerpts (WS10). Both are charged as fixed overhead
    # against a trusted estimate built from every candidate, and the untrusted region fills what is
    # left. This replaces charging evidence against only the architecture JSON, which left the rest
    # of the trusted region and the whole schema uncounted.
    rendered = [(excerpt["evidence_id"], fenced_excerpt(excerpt)) for excerpt in excerpts]
    trusted_estimate = _trusted_region(
        assessment_name=assessment_name,
        methodology=threat_methodology,
        context=context,
        architecture=architecture,
        manifest=_manifest(excerpts),
    )
    outcome = fill_untrusted(
        rendered,
        profile=profile,
        overhead_characters=len(trusted_estimate) + schema_overhead(ThreatAnalysisProposal),
    )

    present = set(outcome.included_ids)
    manifest = _manifest([excerpt for excerpt in excerpts if excerpt["evidence_id"] in present])

    trusted = _trusted_region(
        assessment_name=assessment_name,
        methodology=threat_methodology,
        context=context,
        architecture=architecture,
        manifest=manifest,
    )

    return ThreatAnalysisInput(
        trusted=trusted,
        untrusted=outcome.untrusted,
        evidence_ids=outcome.included_ids,
        component_ids=tuple(component["id"] for component in architecture["components"]),
        asset_ids=tuple(asset["id"] for asset in architecture["assets"]),
        actor_ids=tuple(actor["id"] for actor in architecture["actors"]),
        data_flow_ids=tuple(flow["id"] for flow in architecture["data_flows"]),
        trust_boundary_ids=tuple(boundary["id"] for boundary in architecture["trust_boundaries"]),
        excluded_evidence_ids=outcome.excluded_ids,
        metadata={
            "context_version": context.version,
            "components": len(architecture["components"]),
            "actors": len(architecture["actors"]),
            "assets": len(architecture["assets"]),
            "data_flows": len(architecture["data_flows"]),
            "trust_boundaries": len(architecture["trust_boundaries"]),
            "context_claims": len(architecture["context_claims"]),
            "trusted_characters": len(trusted),
            **outcome.metadata(),
        },
    )
