"""Object-decision fingerprint matching for the stability protocol (#484, DEC-093).

The recorded review file's decisions were authored against the recorded run's objects, so the
recorded side's fingerprints come from the recorded extraction proposal — entries sorted by
allocated identifier correspond to the proposal lists in allocation order (DEC-018). A live
object whose fingerprint uniquely matches replays the recorded disposition; everything else
falls to the default policy and counts as defaulted. The conservative failure mode is always
"no match": ambiguity, a reshaped section, or an unresolvable reference must never pair a
decision with an object its reviewer never saw.
"""

from __future__ import annotations

from typing import Any

from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.infrastructure.model.recorded import parse_recorded_response
from trace_ai.services.context.review_file import read_review_file
from trace_ai.services.evaluation.matching import (
    context_decision_fingerprints,
    live_context_fingerprint,
)
from trace_ai.services.evaluation.registry import scenario


def _proposal(**overrides: Any) -> ContextExtractionProposal:
    payload: dict[str, Any] = {
        "system": {"system_name": "Sample"},
        "components": [
            {"key": "cmp_api", "name": "API Gateway", "component_type": "service"},
            {"key": "cmp_db", "name": "Database", "component_type": "data-store"},
        ],
        "actors": [{"key": "act_user", "name": "Customer", "actor_type": "human"}],
        "data_flows": [
            {
                "key": "flw_ingress",
                "name": "Ingress",
                "source_component_key": "cmp_api",
                "destination_component_key": "cmp_db",
                "direction": "one_way",
            }
        ],
    }
    payload.update(overrides)
    return ContextExtractionProposal.model_validate(payload)


def _document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "components": [
            {"id": "cmp-001", "decision": "approve"},
            {"id": "cmp-002", "decision": "reject"},
        ],
        "actors": [{"id": "act-001", "decision": "approve"}],
        "data_flows": [{"id": "flw-001", "decision": "approve"}],
    }
    document.update(overrides)
    return document


def test_fingerprints_pair_sorted_entries_with_proposal_order() -> None:
    fingerprints = context_decision_fingerprints(_proposal(), _document())

    assert fingerprints[("components", "api gateway")] == "approve"
    assert fingerprints[("components", "database")] == "reject"
    assert fingerprints[("actors", "customer")] == "approve"
    assert fingerprints[("data_flows", "api gateway", "database")] == "approve"


def test_a_count_mismatched_section_is_skipped_whole() -> None:
    """The correspondence is positional; a reshaped section would pair decisions with objects
    their reviewer never saw, so it contributes nothing rather than something wrong."""
    document = _document(components=[{"id": "cmp-001", "decision": "approve"}])

    fingerprints = context_decision_fingerprints(_proposal(), document)

    assert ("components", "api gateway") not in fingerprints
    assert ("components", "database") not in fingerprints
    assert fingerprints[("actors", "customer")] == "approve"


def test_duplicate_fingerprints_are_dropped_as_ambiguous() -> None:
    proposal = _proposal(
        components=[
            {"key": "cmp_a", "name": "Worker", "component_type": "service"},
            {"key": "cmp_b", "name": "Worker", "component_type": "service"},
        ],
        data_flows=[],
    )
    document = _document(
        components=[
            {"id": "cmp-001", "decision": "approve"},
            {"id": "cmp-002", "decision": "reject"},
        ],
        data_flows=[],
    )

    fingerprints = context_decision_fingerprints(proposal, document)

    assert ("components", "worker") not in fingerprints


def test_live_fingerprints_resolve_references_or_decline() -> None:
    """Stand-ins named like the domain classes, because `live_context_fingerprint` dispatches
    on the type name -- identifiers are per-run, so structure is all it may read."""
    component = type("Component", (), {"name": "API Gateway"})()
    assert live_context_fingerprint(component, {}) == ("components", "api gateway")

    flow_type = type(
        "DataFlow",
        (),
        {"source_component_id": "cmp-001", "destination_component_id": "cmp-404"},
    )
    assert live_context_fingerprint(flow_type(), {"cmp-001": "api gateway"}) is None
    assert live_context_fingerprint(
        flow_type(), {"cmp-001": "api gateway", "cmp-404": "database"}
    ) == ("data_flows", "api gateway", "database")

    claim = type("ContextClaim", (), {"subject_id": None, "predicate": "Deployment  Environment"})()
    assert live_context_fingerprint(claim, {}) == (
        "claims",
        "system",
        "deployment environment",
    )


def test_the_committed_forgeflow_recording_yields_a_full_decision_map() -> None:
    """The integration case the protocol actually runs: the flagship recording's own proposal
    and review file produce fingerprints for every unambiguous decided object, all approvals."""
    entry = scenario("forgeflow")
    document = read_review_file(
        (entry.recorded_dir / "decisions-context.yaml").read_text(encoding="utf-8")
    )
    recorded = parse_recorded_response(
        (entry.recorded_dir / "extraction" / "01-context-extraction.json").read_text(
            encoding="utf-8"
        ),
        described_as="forgeflow extraction",
    )
    assert isinstance(recorded.response, ContextExtractionProposal)

    fingerprints = context_decision_fingerprints(recorded.response, document)

    assert len(fingerprints) > 100, "the flagship recording decides well over a hundred objects"
    assert set(fingerprints.values()) == {"approve"}
    assert fingerprints[("components", "forgeflow api")] == "approve"
    assert fingerprints[("components", "webhook receiver")] == "approve"


def test_the_stability_protocol_replays_matched_decisions_instead_of_defaulting(
    tmp_path: Any,
) -> None:
    """A live run whose objects match the recorded run's replays the recorded reviewer's
    decisions; only genuinely novel or ambiguous objects fall to the default policy. Replaying
    the recorded extraction response is the exact-match case: the defaulted count collapses
    from every-object to the residue fingerprinting cannot claim."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.enums import SourceOrigin
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.infrastructure.model.fake import DeterministicModel
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.infrastructure.model.recorded import load_recorded_responses
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.context.pipeline import context_objects
    from trace_ai.services.driver import run_assessment
    from trace_ai.services.evaluation.harness import _apply_context_decisions_live
    from trace_ai.services.ingestion.loader import DocumentLoader

    entry = scenario("forgeflow")
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for path in entry.input_documents():
            loader.load_document(
                path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
            )
        responses = load_recorded_responses(
            sorted((entry.recorded_dir / "extraction").glob("[0-9]*.json"))
        )
        outcome = run_assessment(
            service,
            created.id,
            model=DeterministicModel(list(responses)),
            profile=resolve_profile("offline-fake"),
        )
        assert outcome.paused, "the run pauses at checkpoint 1"

        total = len(context_objects(handle))
        defaulted = _apply_context_decisions_live(entry, service, created.id, condition="clean")

    assert total > 100
    assert defaulted < total / 4, (
        f"{defaulted} of {total} decisions defaulted; fingerprint matching should replay "
        f"the recorded reviewer's decisions for an exact-match run"
    )
