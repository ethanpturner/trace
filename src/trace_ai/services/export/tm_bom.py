"""The TM-BOM export: the approved model, serialized for the ecosystem (DEC-072, issue #347).

TM-BOM is the OWASP Threat Model Library schema — Threat Dragon's declared future primary format
and the ecosystem door: diagramming and GRC tooling reads it with no Trace UI built. This module
is a post-approval serializer: it refuses an assessment whose context no reviewer approved,
serializes approved objects verbatim, and never rewrites approved text (the DEC-035 discipline,
applied to a different artifact family).

**Where TM-BOM demands an answer Trace honestly lacks, the export says so instead of guessing.**
The schema requires booleans and closed enums — a flow is `encrypted` or it is not — while
DEC-009 forbids reading silence as an answer. The rule here: the serialized value is the most
conservative one the schema allows, an `assumption` row with `validity: unconfirmed` names every
value chosen that way, and the raw Trace fields ride the `extensions` block untranslated. A
consumer that reads only the standard fields sees defensible defaults; one that reads the
assumptions and extensions sees exactly what Trace knew.

**Trace-specific content rides the namespaced extensions block.** Findings and documentation
gaps have no TM-BOM shape whose required risk arithmetic (likelihood, impact, score) Trace could
fill without manufacturing precision the reviewer never assigned, so they serialize verbatim
under `trace-ai.local/...` keys — DEC-072's stated hedge, which also survives the pre-1.0
schema's drift.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.control import Control, ImplementationStatus
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, ValidationStatus
from trace_ai.domain.threat import Threat
from trace_ai.domain.vocabulary import normalize_term
from trace_ai.services.findings.approved import approved_findings
from trace_ai.workflow.context_review import current_system_context

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["TM_BOM_SCHEMA_PATH", "ExportError", "export_tm_bom", "write_tm_bom"]

TM_BOM_SCHEMA_PATH: Final = PROJECT_ROOT / "schemas" / "tm-bom" / "threat-model.schema.json"

# The zone a component or actor lands in when the approved context states none. A real zone name
# would be a claim nobody made; this one says exactly what is known.
_UNSPECIFIED_ZONE: Final = "zone-unspecified"

# Trust the affirmative spellings only: `unknown` and everything else conservative-defaults to
# unencrypted, with the assumption row saying so.
_ENCRYPTED_TERMS: Final = frozenset(
    {"tls", "mtls", "https", "ssl", "encrypted", "tls_1_2", "tls_1_3"}
)

# Trace actor types that are adversaries: they become threat personas, not TM-BOM actors, whose
# enum describes legitimate external entities.
_ADVERSARIAL_ACTOR_TYPES: Final = frozenset({"external_attacker", "malicious_insider"})

_ACTOR_TYPE_MAP: Final = {
    "end_user": "user",
    "developer": "engineer",
    "administrator": "administrator",
    "service_identity": "system",
    "third_party_service": "third_party",
    "compromised_dependency": "third_party",
}

_SKILL_MAP: Final = {
    "opportunist": "script_kid",
    "skilled": "engineer",
    "organized_group": "oc_sponsored",
}
_ACCESS_MAP: Final = {
    "anonymous": "anonymous",
    "authenticated": "user",
    "privileged": "admin",
    "physical": "user",
}

_SENSITIVITY_MAP: Final = {
    "pii": "pii",
    "phi": "phi",
    "financial": "fin",
    "credentials": "cred",
    "intellectual_property": "ip",
    "restricted": "biz",
    "confidential": "biz",
    "internal": "biz",
    "telemetry": "op",
    "public": "biz",
}

_CONTROL_STATUS_MAP: Final = {
    ImplementationStatus.IMPLEMENTED: "active",
    ImplementationStatus.PARTIALLY_IMPLEMENTED: "active",
    ImplementationStatus.CLAIMED: "assumed",
    ImplementationStatus.UNKNOWN: "assumed",
    ImplementationStatus.ABSENT: "suggested",
}


class ExportError(RuntimeError):
    """An export that cannot be produced, with the reason named."""


def _zone_name(zone: str | None) -> str:
    if not zone:
        return _UNSPECIFIED_ZONE
    try:
        return normalize_term(zone).replace("_", "-")
    except ValueError:
        return _UNSPECIFIED_ZONE


def _degree(value: str | None) -> tuple[str, bool]:
    """Map free-text criticality onto TM-BOM's degree enum; the bool says whether it mapped."""
    if not value:
        return "moderate", False
    try:
        term = normalize_term(value)
    except ValueError:
        return "moderate", False
    aliases = {
        "minimal": "minimal",
        "low": "low",
        "moderate": "moderate",
        "medium": "moderate",
        "high": "high",
        "maximal": "maximal",
        "critical": "maximal",
    }
    if term in aliases:
        return aliases[term], True
    return "moderate", False


def export_tm_bom(handle: AssessmentHandle) -> dict[str, Any]:
    """Serialize the approved model as one TM-BOM document.

    Refuses an assessment with no approved context: exports are post-approval serializers, and a
    document derived from candidates would carry conclusions no reviewer saw.
    """
    try:
        context = current_system_context(handle)
    except ValueError as missing:
        raise ExportError(
            f"{handle.assessment_id} has no extracted context to export: {missing}"
        ) from None
    if not context.is_approved:
        raise ExportError(
            f"{handle.assessment_id} has no approved system context. Exports serialize approved "
            f"objects only (DEC-072); run the assessment through checkpoint 1 first."
        )

    repository = handle.objects

    def approved[ModelT](model: type[ModelT], listed: list[str]) -> list[ModelT]:
        """In the approved context, and — where the model carries an `ObjectStatus` — approved.

        `Actor` and `ContextClaim` carry no `ObjectStatus`; membership in the reviewer-approved
        context is their approval, and a claim's own `ClaimStatus` is a different vocabulary.
        """
        ids = set(listed)
        chosen = [obj for obj in repository.list(model) if obj.id in ids]  # type: ignore[type-var,attr-defined]
        return [
            obj
            for obj in chosen
            if not isinstance(getattr(obj, "status", None), ObjectStatus)
            or obj.status is ObjectStatus.APPROVED  # type: ignore[attr-defined]
        ]

    components = approved(Component, context.component_ids)
    actors = approved(Actor, context.actor_ids)
    assets = approved(Asset, context.asset_ids)
    flows = approved(DataFlow, context.data_flow_ids)
    claims = approved(ContextClaim, context.context_claim_ids)
    threats = [t for t in repository.list(Threat) if t.status is ObjectStatus.APPROVED]
    confirmed_controls = [
        c for c in repository.list(Control) if c.validation_status is ValidationStatus.SUPPORTED
    ]
    findings = approved_findings(handle)
    gaps = [gap for gap in repository.list(DocumentationGap) if gap.status is ObjectStatus.APPROVED]

    assumptions: list[dict[str, Any]] = []
    component_ids = {component.id for component in components}

    # -- zones and boundaries ------------------------------------------------------------
    zones = sorted(
        {_zone_name(component.deployment_zone) for component in components} | {_UNSPECIFIED_ZONE}
    )
    zone_of = {component.id: _zone_name(component.deployment_zone) for component in components}
    boundary_pairs: set[tuple[str, str]] = set()
    for flow in flows:
        zone_a = zone_of.get(flow.source_component_id)
        zone_b = zone_of.get(flow.destination_component_id)
        if zone_a and zone_b and zone_a != zone_b:
            boundary_pairs.add(tuple(sorted((zone_a, zone_b))))  # type: ignore[arg-type]

    # -- scope ------------------------------------------------------------------------------
    criticality, criticality_stated = _degree(context.business_criticality)
    if not criticality_stated:
        assumptions.append(
            {
                "description": (
                    "business_criticality was not stated in a form the TM-BOM degree vocabulary "
                    "carries; 'moderate' is the export's conservative default, not a reviewed "
                    "value."
                ),
                "validity": "unconfirmed",
            }
        )

    stated_exposures = [component.internet_accessible for component in components]
    exposure = "external" if any(value is True for value in stated_exposures) else "internal"
    if not any(value is True or value is False for value in stated_exposures):
        assumptions.append(
            {
                "description": (
                    "No approved component states internet accessibility either way; exposure "
                    "'internal' is the export's conservative default, not a reviewed value."
                ),
                "validity": "unconfirmed",
            }
        )

    classifications = [asset.data_classification for asset in assets if asset.data_classification]
    mapped = sorted({_SENSITIVITY_MAP[c] for c in classifications if c in _SENSITIVITY_MAP})
    sensitivity = mapped if mapped else ["biz"]
    if not mapped:
        assumptions.append(
            {
                "description": (
                    "No approved asset carries a data classification the TM-BOM sensitivity "
                    "vocabulary maps; 'biz' is the export's default, not a reviewed value."
                ),
                "validity": "unconfirmed",
            }
        )

    tier_by_degree = {
        "maximal": "mission_critical",
        "high": "business_critical",
        "moderate": "important",
        "low": "non_critical",
        "minimal": "non_critical",
    }

    # -- flows ------------------------------------------------------------------------------
    unstated_encryption: list[str] = []
    flow_rows: list[dict[str, Any]] = []
    for flow in flows:
        if flow.source_component_id not in component_ids:
            continue
        if flow.destination_component_id not in component_ids:
            continue
        encrypted = str(flow.encryption_in_transit) in _ENCRYPTED_TERMS
        if not encrypted and str(flow.encryption_in_transit) not in {"none", "unencrypted"}:
            unstated_encryption.append(flow.id)
        flow_rows.append(
            {
                "symbolic_name": flow.id,
                "title": flow.name,
                "description": flow.name,
                "source": {"type": "component", "object": flow.source_component_id},
                "destination": {"type": "component", "object": flow.destination_component_id},
                # Sensitivity per flow is not a fact Trace records; False is the schema's
                # conservative answer and the extensions carry the flow verbatim.
                "has_sensitive_data": False,
                "encrypted": encrypted,
            }
        )
    if unstated_encryption:
        assumptions.append(
            {
                "description": (
                    f"encryption in transit is unstated (not asserted absent) for "
                    f"{', '.join(sorted(unstated_encryption))}; 'encrypted: false' is the "
                    f"schema's conservative boolean, not an asserted weakness (DEC-009)."
                ),
                "validity": "unconfirmed",
            }
        )

    # -- actors and personas ----------------------------------------------------------------
    actor_rows: list[dict[str, Any]] = []
    personas: list[dict[str, Any]] = []
    persona_by_actor: dict[str, str] = {}
    for actor in actors:
        if str(actor.actor_type) in _ADVERSARIAL_ACTOR_TYPES:
            persona_by_actor[actor.id] = actor.id
            personas.append(
                {
                    "symbolic_name": actor.id,
                    "title": actor.name,
                    "description": f"{actor.name} ({actor.actor_type})",
                    "is_person": True,
                    "skill_level": _SKILL_MAP.get(str(actor.skill_level or ""), "engineer"),
                    "access_level": _ACCESS_MAP.get(str(actor.access_level or ""), "anonymous"),
                    "malicious_intent": True,
                    "applicability_to_org": "moderate",
                }
            )
        else:
            actor_rows.append(
                {
                    "symbolic_name": actor.id,
                    "title": actor.name,
                    "description": actor.trust_level or f"{actor.name} ({actor.actor_type})",
                    "type": _ACTOR_TYPE_MAP.get(str(actor.actor_type), "third_party"),
                    "trust_zone": _UNSPECIFIED_ZONE,
                }
            )

    fallback_persona = "unattributed-adversary"
    threat_rows: list[dict[str, Any]] = []
    needs_fallback = False
    for threat in threats:
        persona = next(
            (persona_by_actor[a] for a in threat.threat_actor_ids if a in persona_by_actor),
            None,
        )
        if persona is None:
            persona = fallback_persona
            needs_fallback = True
        threat_rows.append(
            {
                "symbolic_name": threat.id,
                "title": threat.title,
                "description": threat.description,
                "components_affected": [
                    c for c in threat.affected_component_ids if c in component_ids
                ],
                "threat_persona": persona,
                "event": threat.attack_path[0] if threat.attack_path else threat.title,
                "sources": ["adversary"],
            }
        )
    if needs_fallback:
        personas.append(
            {
                "symbolic_name": fallback_persona,
                "title": "Unattributed adversary",
                "description": (
                    "Trace records no persona for one or more approved threats; this persona's "
                    "skill and access values are conservative defaults, not reviewed values."
                ),
                "is_person": True,
                "skill_level": "engineer",
                "access_level": "anonymous",
                "malicious_intent": True,
                "applicability_to_org": "moderate",
            }
        )

    # -- controls -----------------------------------------------------------------------------
    approved_threat_ids = {threat.id for threat in threats}
    threats_by_control: dict[str, list[str]] = {}
    for mapping in repository.list(ControlMapping):
        if mapping.threat_id not in approved_threat_ids:
            continue
        for control_id in mapping.control_ids:
            threats_by_control.setdefault(control_id, []).append(mapping.threat_id)
    control_rows = [
        {
            "symbolic_name": control.id,
            "title": control.name,
            "description": control.description,
            "threats": sorted(set(threats_by_control.get(control.id, []))),
            "status": _CONTROL_STATUS_MAP[control.implementation_status],
            "priority": "none",
        }
        for control in confirmed_controls
    ]

    # -- claims as assumptions ---------------------------------------------------------------
    for claim in claims:
        if claim.status is ClaimStatus.ASSUMED:
            assumptions.append({"description": claim.predicate, "validity": "unconfirmed"})
        elif claim.status is ClaimStatus.USER_CONFIRMED:
            assumptions.append({"description": claim.predicate, "validity": "confirmed"})

    document: dict[str, Any] = {
        "version": str(context.version),
        "scope": {
            "title": context.system_name,
            "description": context.system_purpose or "Approved system context exported by Trace.",
            "business_criticality": criticality,
            "data_sensitivity": sensitivity,
            "exposure": exposure,
            "tier": tier_by_degree[criticality],
        },
        "trust_zones": [
            {
                "symbolic_name": zone,
                "title": zone.replace("-", " "),
                "description": (
                    "No deployment zone was stated for the objects in this zone."
                    if zone == _UNSPECIFIED_ZONE
                    else f"Deployment zone {zone!r} from the approved context."
                ),
            }
            for zone in zones
        ],
        "trust_boundaries": [
            {"trust_zone_a": zone_a, "trust_zone_b": zone_b}
            for zone_a, zone_b in sorted(boundary_pairs)
        ],
        "actors": actor_rows,
        "components": [
            {
                "symbolic_name": component.id,
                "title": component.name,
                "description": component.description or f"{component.component_type} component.",
                "trust_zone": zone_of[component.id],
            }
            for component in components
        ],
        "data_stores": [],
        "data_sets": [],
        "data_flows": flow_rows,
        "assumptions": assumptions,
        "threat_personas": personas,
        "threats": threat_rows,
        "controls": control_rows,
        # Trace-specific content, verbatim (DEC-072's hedge). Approved text is never rewritten.
        "extensions": {
            "trace-ai.local/assessment": {
                "assessment_id": handle.assessment_id,
                "context_version": context.version,
                "approved_by": context.approved_by,
            },
            "trace-ai.local/findings": [finding.model_dump(mode="json") for finding in findings],
            "trace-ai.local/documentation-gaps": [gap.model_dump(mode="json") for gap in gaps],
            "trace-ai.local/assets": [asset.model_dump(mode="json") for asset in assets],
            "trace-ai.local/data-flows": [flow.model_dump(mode="json") for flow in flows],
        },
    }
    return document


def write_tm_bom(handle: AssessmentHandle) -> Path:
    """Serialize and write the export to the assessment's outputs area.

    The filename is content-addressed, so re-exporting after checkpoint 2 edits writes a new
    artifact beside the old one instead of tripping the store's no-overwrite rule — exports
    accumulate append-only, like everything else with provenance.
    """
    from trace_ai.domain.hashing import content_hash

    document = export_tm_bom(handle)
    payload = json.dumps(document, indent=2, sort_keys=False) + "\n"
    digest = content_hash(payload.encode("utf-8")).removeprefix("sha256:")[:12]
    return handle.artifacts.store_output(f"tm-bom-{digest}.json", payload.encode("utf-8"))
