"""What the Requirement and Control Mapping agent is given, and what it cannot reach.

Three properties are load-bearing here, and each is a rule stated somewhere in the corpus that
only becomes true when the assembler makes it true.

**The payload is inert.** `agent-design.md` section 22 lists what an agent must not have and
describes retrieval as an application-controlled interface. The strongest form of that is a payload
with nothing to call, so the test is that the whole thing serializes as JSON: a callable, an open
file, a database session, or an index would all fail that.

**The whole catalog goes in, and `common_false_positives` goes in with it.** DEC-024 rules out a
pre-filter — `applicable_technologies` is populated on zero of the twenty-three requirements — and
DEC-011 records that nothing enforces the false-positive field is consulted. DEC-025's structural
check is that enforcement, and it is unenforceable if the entries never reach the agent.

**A budget overrun stops the run.** The threat package drops evidence by identifier and reports it;
this one raises. A threat citing fewer passages is still a correct threat, while a mapping run
against part of the catalog is a complete-looking run that silently never considered the rest.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control import Control, ControlType, ImplementationStatus
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.mapping.input_package import (
    ACCEPTABLE_IMPLEMENTATIONS_NOTE,
    MappingInput,
    PayloadTooLargeError,
    UnapprovedContextError,
    assemble_mapping_input,
)
from trace_ai.services.requirements.loader import LoadedCatalog, current_version, load_catalog

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")


@pytest.fixture(scope="module")
def catalog() -> LoadedCatalog:
    return load_catalog(current_version())


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, SystemContext, Threat]]:
    """An approved context with one rejected component, one control, and one threat.

    The rejected component is the fixture for the approved-baseline rule: it is in the store and
    absent from the approved revision's `component_ids`, which is exactly the state DEC-040 leaves
    behind and the state a store listing would undo.
    """
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for name in ("architecture-overview.md", "github-integration.md"):
            index_document(
                handle,
                loader.load_document(
                    FORGEFLOW / name,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                ),
            )
        yield _populate(handle)


def _populate(handle: AssessmentHandle) -> tuple[AssessmentHandle, SystemContext, Threat]:
    stamped = now()
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]

    with handle.objects.transaction():
        receiver = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Webhook Receiver",
                "component_type": "service",
                "internet_accessible": True,
                "evidence_ids": [cited],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(receiver)

        rejected = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Speculative billing service",
                "component_type": "service",
                "source_origin": SourceOrigin.SYSTEM_GENERATED,
                "status": ObjectStatus.REJECTED,
            }
        )
        handle.objects.save(rejected)

        repository = Asset.model_validate(
            {
                "id": handle.objects.allocate("ast"),
                "assessment_id": handle.assessment_id,
                "name": "Customer source code",
                "asset_type": "data",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(repository)

        control = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Managed database encryption at rest",
                "description": "The managed database platform encrypts stored data.",
                "control_type": ControlType.INHERITED,
                "protected_asset_ids": [repository.id],
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "evidence_ids": [cited],
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(control)

        unrelated = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Office badge access",
                "description": "Physical access to the office is badged.",
                "control_type": ControlType.IMPLEMENTED,
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "evidence_ids": [cited],
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(unrelated)

        context = SystemContext.model_validate(
            {
                "assessment_id": handle.assessment_id,
                "system_name": "ForgeFlow",
                "system_purpose": "AI-assisted pull request review",
                "component_ids": [receiver.id],
                "asset_ids": [repository.id],
                "actor_ids": [],
                "data_flow_ids": [],
                "trust_boundary_ids": [],
                "context_claim_ids": [],
                "version": FIRST_VERSION + 1,
                "approved_at": stamped,
                "approved_by": "reviewer",
            }
        )
        handle.objects.save(context)

        threat = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Forged webhooks trigger unauthorized analysis jobs",
                "description": "An attacker submits unsigned webhook requests.",
                "methodology": "stride-scenario-based",
                "category": ["spoofing"],
                "affected_component_ids": [receiver.id],
                "affected_asset_ids": [repository.id],
                "impact": "Unauthorized jobs and disclosure of repository content",
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": [cited],
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )
        handle.objects.save(threat)

    return handle, context, threat


def package(
    prepared: tuple[AssessmentHandle, SystemContext, Threat],
    catalog: LoadedCatalog,
    **changes: Any,
) -> MappingInput:
    handle, context, threat = prepared
    options: dict[str, Any] = {
        "context": context,
        "threat": threat,
        "catalog": catalog,
        "index": EvidenceIndex(handle),
        "evidence_ids": sorted(r.id for r in handle.objects.list(EvidenceReference))[:4],
        "profile": PROFILE,
        **changes,
    }
    return assemble_mapping_input(handle, **options)


# The payload is inert


def test_the_assembled_payload_is_json_serializable(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """A callable, an open file, a session, or an index would all fail this."""
    assembled = package(prepared, catalog)

    round_tripped = json.loads(json.dumps(asdict(assembled)))

    assert round_tripped["threat_id"] == assembled.threat_id


def test_no_field_holds_a_callable(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """Section 22: there is no retrieval function the agent could invoke."""
    assembled = package(prepared, catalog)

    for name, value in asdict(assembled).items():
        assert not callable(value), name


def test_the_package_carries_no_handle_index_or_profile(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)
    held = set(asdict(assembled))

    assert not held & {"handle", "index", "profile", "store", "session", "repository"}


# The keys section 30 and section 27 need


def test_the_payload_carries_the_three_keys(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    handle, _, threat = prepared

    assembled = package(prepared, catalog)

    assert assembled.assessment_id == handle.assessment_id
    assert assembled.threat_id == threat.id
    assert assembled.catalog_version == catalog.version


def test_input_object_ids_is_populated_sorted_and_deduplicated(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    recorded = assembled.input_object_ids()

    assert recorded
    assert list(recorded) == sorted(set(recorded))
    assert assembled.threat_id in recorded
    assert set(assembled.requirement_ids) <= set(recorded)


def test_the_catalog_version_is_not_an_input_object_id(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """It is not an object identifier, and section 27's field is a list of those."""
    assembled = package(prepared, catalog)

    assert catalog.version not in assembled.input_object_ids()


# The whole catalog, with the fields section 12 reasons over


def test_every_requirement_in_the_catalog_is_present(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """DEC-024: no pre-filter. The only structured filter field is populated on nothing."""
    assembled = package(prepared, catalog)

    assert set(assembled.requirement_ids) == {r.id for r in catalog.requirements}


def test_common_false_positives_survives_assembly(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """Without it, DEC-025's structural check has nothing for the agent to have addressed."""
    assembled = package(prepared, catalog)
    payload = _requirements_in(assembled)

    for requirement in catalog.requirements:
        assert payload[requirement.id]["common_false_positives"] == list(
            requirement.common_false_positives
        )

    assert any(payload[r.id]["common_false_positives"] for r in catalog.requirements)


@pytest.mark.parametrize(
    "field",
    [
        "statement",
        "rationale",
        "applicable_conditions",
        "non_applicable_conditions",
        "acceptable_implementations",
        "evidence_expectations",
        "common_false_positives",
    ],
)
def test_the_fields_the_mapping_step_reasons_over_are_present(
    prepared: tuple[AssessmentHandle, SystemContext, Threat],
    catalog: LoadedCatalog,
    field: str,
) -> None:
    payload = _requirements_in(package(prepared, catalog))

    for entry in payload.values():
        assert field in entry


def test_acceptable_implementations_carries_its_non_exhaustive_marker(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """The framing travels with the data, so a prompt edit cannot separate them."""
    payload = _requirements_in(package(prepared, catalog))

    for identifier, entry in payload.items():
        assert entry["acceptable_implementations"]["note"] == ACCEPTABLE_IMPLEMENTATIONS_NOTE, (
            identifier
        )

    by_id = catalog.by_id()
    for identifier, entry in payload.items():
        assert entry["acceptable_implementations"]["examples"] == list(
            by_id[identifier].acceptable_implementations
        )


def test_the_payload_shows_the_mapper_no_severity(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """DEC-030: no node proposes severity, and section 12 prohibits this agent from assigning it."""
    payload = _requirements_in(package(prepared, catalog))

    for entry in payload.values():
        assert "default_severity" not in entry


# The approved baseline only


def test_a_rejected_component_is_excluded(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """Section 9: everything after checkpoint 1 works from the approved baseline."""
    handle, _, _ = prepared
    rejected = next(
        component
        for component in handle.objects.list(Component)
        if component.status is ObjectStatus.REJECTED
    )

    assembled = package(prepared, catalog)

    assert rejected.id not in assembled.component_ids
    assert rejected.name not in assembled.trusted


def test_an_unapproved_context_is_refused(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    _, context, _ = prepared
    draft = SystemContext.model_validate(
        {**context.model_dump(), "approved_at": None, "approved_by": None}
    )

    with pytest.raises(UnapprovedContextError, match="Requirement and control mapping"):
        package(prepared, catalog, context=draft)


def test_only_controls_bearing_on_the_threat_are_carried(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    handle, _, _ = prepared
    related = next(c for c in handle.objects.list(Control) if c.protected_asset_ids)
    unrelated = next(c for c in handle.objects.list(Control) if not c.protected_asset_ids)

    assembled = package(prepared, catalog)

    assert related.id in assembled.control_ids
    assert unrelated.id not in assembled.control_ids


def test_an_inherited_control_carries_its_documented_inheritance_verdict(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """DEC-026's distinction, read once rather than reconstructed from three fields per caller."""
    assembled = package(prepared, catalog)

    controls = json.loads(_section(assembled.trusted, "Existing controls"))
    inherited = next(entry for entry in controls if entry["control_type"] == "inherited")

    assert inherited["is_documented_inheritance"] is True


# Source text stays inside the fence


def test_the_trusted_region_carries_no_quoted_source_text(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """Section 23's context-minimisation rationale: excerpts appear once, inside the fence."""
    handle, _, _ = prepared
    assembled = package(prepared, catalog)
    index = EvidenceIndex(handle)

    for excerpt in index.render_for_prompt(list(assembled.evidence_ids)):
        assert excerpt["quoted_text"] not in assembled.trusted
        assert excerpt["quoted_text"] in assembled.untrusted


def test_the_evidence_manifest_names_identifiers_and_locations_only(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    manifest = json.loads(_section(assembled.trusted, "Evidence available"))

    assert {entry["evidence_id"] for entry in manifest} == set(assembled.evidence_ids)
    assert all("quoted_text" not in entry for entry in manifest)


def test_the_package_carries_no_path_or_credential(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    for forbidden in ("ANTHROPIC_API_KEY", "sk-ant-", str(PROJECT_ROOT)):
        assert forbidden not in assembled.trusted


# The bound


def test_exceeding_the_bound_raises_rather_than_truncating(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    tiny = replace(PROFILE, max_input_characters=500)

    with pytest.raises(PayloadTooLargeError) as raised:
        package(prepared, catalog, profile=tiny)

    assert raised.value.budget == 500
    assert raised.value.size > 500


def test_the_overrun_error_names_what_would_have_been_dropped(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    handle, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[:4]
    tiny = replace(PROFILE, max_input_characters=500)

    with pytest.raises(PayloadTooLargeError) as raised:
        package(prepared, catalog, profile=tiny, evidence_ids=cited)

    assert raised.value.excluded_evidence_ids == tuple(cited)
    for identifier in cited:
        assert identifier in str(raised.value)


def test_the_overrun_error_says_why_a_smaller_payload_is_not_the_answer(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    """DEC-024's escalation is partitioning, and section 27 forbids shrinking a request."""
    tiny = replace(PROFILE, max_input_characters=500)

    with pytest.raises(PayloadTooLargeError, match="DEC-024"):
        package(prepared, catalog, profile=tiny)


def test_a_payload_within_the_bound_is_assembled_whole(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    assert assembled.metadata["characters"] <= assembled.metadata["budget_characters"]
    assert assembled.metadata["requirements"] == len(catalog.requirements)


# Referenceable identifiers


def test_referenceable_ids_covers_everything_the_package_supplied(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    referenceable = assembled.referenceable_ids()

    assert assembled.threat_id in referenceable
    assert set(assembled.requirement_ids) <= referenceable
    assert set(assembled.control_ids) <= referenceable
    assert set(assembled.evidence_ids) <= referenceable


def test_an_identifier_the_package_never_supplied_is_not_referenceable(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    assert "req-NOPE-999" not in assembled.referenceable_ids()
    assert "cmp-404" not in assembled.referenceable_ids()


def test_the_prompt_substitution_is_the_fenced_region_only(
    prepared: tuple[AssessmentHandle, SystemContext, Threat], catalog: LoadedCatalog
) -> None:
    assembled = package(prepared, catalog)

    assert assembled.substitutions() == {"input.source_content": assembled.untrusted}


def _section(trusted: str, heading: str) -> str:
    """The JSON block under one `## heading` of the trusted region."""
    marker = f"## {heading}\n\n"
    start = trusted.index(marker) + len(marker)
    end = trusted.find("\n\n## ", start)
    return trusted[start:] if end == -1 else trusted[start:end]


def _requirements_in(assembled: MappingInput) -> dict[str, dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(_section(assembled.trusted, "Requirements catalog"))
    return {entry["id"]: entry for entry in entries}
