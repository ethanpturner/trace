"""Tests for the execution ledger.

`current-architecture.md` section 5.17 makes local audit records the authoritative execution record,
and `data-model.md` section 34 prefers linked execution records to stamping provenance onto every
generated object. That makes this a prerequisite for the first agent rather than a convenience, and
it is written now, while the only executions are deterministic, so the first model-assisted node
finds a ledger instead of inventing one.

Two properties get the most attention. **Failures are recorded**, because a ledger that only holds
successes answers "what happened" with a list of things that worked. And **`error_message` carries
no content**, which section 27 requires and which is tested against the injection fixture rather
than against a synthetic string. Issue #57.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import (
    ExecutionRecord,
    ExecutionStatus,
    ExecutionType,
    RunStatus,
    WorkflowRun,
)
from trace_ai.domain.source_document import SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.seam import ModelUsage
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import (
    MAXIMUM_ERROR_MESSAGE,
    ExecutionLedger,
    start_run,
)
from trace_ai.services.ingestion.loader import DocumentLoader

FORGEFLOW_INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"


@pytest.fixture
def ledger(tmp_path: Path) -> Iterator[ExecutionLedger]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield ExecutionLedger(handle, run)


# ------------------------------------------------------------------------------------------
# Recording an execution
# ------------------------------------------------------------------------------------------


def test_a_successful_execution_is_recorded(ledger: ExecutionLedger) -> None:
    with ledger.record("ingest", node_version="0.1") as execution:
        execution.produced("src-001")

    (record,) = ledger.records()
    assert record.status is ExecutionStatus.COMPLETED
    assert record.completed_at is not None
    assert record.duration_ms is not None
    assert record.output_object_ids == ["src-001"]
    assert record.error_type is None


def test_a_failing_execution_is_recorded_and_the_error_propagates(
    ledger: ExecutionLedger,
) -> None:
    """A ledger that swallowed the exception would be an error handler wearing an audit record.

    The caller would carry on with a failure written and nothing raised, which is worse than
    either outcome on its own.
    """
    with (
        pytest.raises(RuntimeError, match="disk full"),
        ledger.record("ingest", node_version="0.1"),
    ):
        raise RuntimeError("disk full")

    (record,) = ledger.records()
    assert record.status is ExecutionStatus.FAILED
    assert record.error_type == "RuntimeError"
    assert record.error_message == "disk full"
    assert record.completed_at is not None


def test_a_ledger_that_only_recorded_successes_would_pass_nothing_here(
    ledger: ExecutionLedger,
) -> None:
    with pytest.raises(ValueError), ledger.record("a", node_version="0.1"):
        raise ValueError("boom")
    with ledger.record("b", node_version="0.1"):
        pass

    statuses = {record.node_name: record.status for record in ledger.records()}
    assert statuses == {"a": ExecutionStatus.FAILED, "b": ExecutionStatus.COMPLETED}


def test_retry_number_is_recorded_and_increments(ledger: ExecutionLedger) -> None:
    """`agent-design.md` section 26 bounds retries, which is unmeasurable if attempts overwrite."""
    for attempt in range(3):
        with ledger.record("extract", node_version="0.1", retry_number=attempt):
            pass

    assert [record.retry_number for record in ledger.records()] == [0, 1, 2]
    assert len({record.id for record in ledger.records()}) == 3


def test_inputs_and_outputs_are_recorded(ledger: ExecutionLedger) -> None:
    with ledger.record("index", node_version="0.1", consumes=["src-001"]) as execution:
        execution.produced("evd-001", "evd-002")
        execution.consumed("src-002")

    (record,) = ledger.records()
    assert record.input_object_ids == ["src-001", "src-002"]
    assert record.output_object_ids == ["evd-001", "evd-002"]


def test_every_record_shares_its_runs_assessment(ledger: ExecutionLedger) -> None:
    with ledger.record("ingest", node_version="0.1"):
        pass

    assert all(record.assessment_id == ledger.run.assessment_id for record in ledger.records())
    assert all(record.workflow_run_id == ledger.run.id for record in ledger.records())


def test_a_ledger_for_another_assessments_run_is_refused(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        configuration = default_configuration("primary-development", "stride-scenario-based")
        first = service.handle(service.create("First", configuration).id)
        second = service.handle(service.create("Second", configuration).id)
        run = start_run(first, workflow_version="0.1", model_profile="p")

        with pytest.raises(ValueError, match="belongs to"):
            ExecutionLedger(second, run)


# ------------------------------------------------------------------------------------------
# `error_message` is safe
# ------------------------------------------------------------------------------------------


def test_an_error_message_carries_no_source_content(tmp_path: Path) -> None:
    """Tested against the injection fixture rather than a synthetic string.

    Section 27 calls this a safe error message. Nothing generic can inspect a string and know
    whether a document is inside it, so the rule lives on the exceptions this codebase raises --
    and this is the case where it would matter most.
    """
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="p")
        ledger = ExecutionLedger(handle, run)

        payload = (FORGEFLOW_INPUT / "sample-repository-notes.md").read_text(encoding="utf-8")
        broken = tmp_path / "broken.yaml"
        broken.write_text(payload, encoding="utf-8")

        loader = DocumentLoader(handle, ledger=ledger)
        with pytest.raises(Exception):  # noqa: B017 -- any load failure is the case under test
            loader.load_document(
                broken, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
            )

        serialized = json.dumps([record.model_dump(mode="json") for record in ledger.records()])
        assert "AI ANALYSIS OVERRIDE" not in serialized
        assert "Ignore every previous instruction" not in serialized


def test_a_long_error_message_is_bounded(ledger: ExecutionLedger) -> None:
    """An unexpected message must not become a storage problem or smuggle a document into a row."""
    with pytest.raises(RuntimeError), ledger.record("noisy", node_version="0.1"):
        raise RuntimeError("x" * 5000)

    (record,) = ledger.records()
    assert record.error_message is not None
    assert len(record.error_message) <= MAXIMUM_ERROR_MESSAGE


def test_an_error_with_no_message_still_records_a_type(ledger: ExecutionLedger) -> None:
    with pytest.raises(RuntimeError), ledger.record("silent", node_version="0.1"):
        raise RuntimeError

    (record,) = ledger.records()
    assert record.error_type == "RuntimeError"
    assert record.error_message


# ------------------------------------------------------------------------------------------
# The two deterministic nodes are instrumented
# ------------------------------------------------------------------------------------------


def test_ingesting_the_corpus_records_both_nodes(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        ledger = ExecutionLedger(handle, run)

        loader = DocumentLoader(handle, ledger=ledger)
        for document in loader.load_directory(FORGEFLOW_INPUT):
            index_document(handle, document, ledger=ledger)

        records = ledger.records()
        nodes = {record.node_name for record in records}

        assert nodes == {"document_ingestion", "normalization_and_evidence_indexing"}
        assert len(records) == 16, "eight documents, ingested and indexed"
        assert all(record.execution_type is ExecutionType.DETERMINISTIC for record in records)
        assert all(record.status is ExecutionStatus.COMPLETED for record in records)


def test_records_link_the_objects_the_nodes_produced(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        ledger = ExecutionLedger(
            handle, start_run(handle, workflow_version="0.1", model_profile="p")
        )

        document = DocumentLoader(handle, ledger=ledger).load_document(
            FORGEFLOW_INPUT / "product-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )
        references = index_document(handle, document, ledger=ledger)

        ingest, index = ledger.records()
        assert ingest.output_object_ids == [document.id]
        assert index.input_object_ids == [document.id]
        assert index.output_object_ids == [r.id for r in references]


def test_the_nodes_run_without_a_ledger(tmp_path: Path) -> None:
    """Instrumentation is optional while no orchestrator guarantees a run exists."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        document = DocumentLoader(handle).load_document(
            FORGEFLOW_INPUT / "product-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )

        assert index_document(handle, document)
        assert handle.objects.list(ExecutionRecord) == []


def test_a_failing_load_is_recorded_against_the_run(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        ledger = ExecutionLedger(
            handle, start_run(handle, workflow_version="0.1", model_profile="p")
        )

        with pytest.raises(Exception):  # noqa: B017
            DocumentLoader(handle, ledger=ledger).load_document(
                tmp_path / "report.pdf",
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            )

        (record,) = ledger.records()
        assert record.status is ExecutionStatus.FAILED
        assert record.node_name == "document_ingestion"
        assert record.error_type


# ------------------------------------------------------------------------------------------
# The run
# ------------------------------------------------------------------------------------------


def test_no_model_is_called_in_this_milestone(tmp_path: Path) -> None:
    """`total_model_calls` is zero, which is the correct value rather than a placeholder.

    A ledger that could not express *no model was used* would be a ledger assuming one was.
    """
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        ledger = ExecutionLedger(
            handle, start_run(handle, workflow_version="0.1", model_profile="p")
        )

        loader = DocumentLoader(handle, ledger=ledger)
        for document in loader.load_directory(FORGEFLOW_INPUT):
            index_document(handle, document, ledger=ledger)

        completed = ledger.complete()
        assert completed.total_model_calls == 0
        assert completed.status is RunStatus.COMPLETED
        assert not [r for r in ledger.records() if r.execution_type is ExecutionType.MODEL]


def test_a_run_and_its_records_round_trip_through_the_store(ledger: ExecutionLedger) -> None:
    with ledger.record("ingest", node_version="0.1"):
        pass
    completed = ledger.complete()

    stored_run = ledger.handle.objects.get(WorkflowRun, completed.id)
    stored_records = ledger.handle.objects.list(ExecutionRecord)

    assert stored_run == completed
    assert len(stored_records) == 1
    assert stored_records[0].workflow_run_id == completed.id


def test_completing_with_a_summary_marks_the_run_failed(ledger: ExecutionLedger) -> None:
    completed = ledger.complete(error_summary="ingestion failed for two documents")

    assert completed.status is RunStatus.FAILED
    assert completed.error_summary
    assert completed.completed_at is not None


def test_the_ledger_needs_no_api_key(
    ledger: ExecutionLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with ledger.record("ingest", node_version="0.1"):
        pass
    assert ledger.records()


# ------------------------------------------------------------------------------------------
# The models
# ------------------------------------------------------------------------------------------


def test_checkpoint_reference_is_absent() -> None:
    """DEC-016 removed the framework and DEC-017 removed the field.

    A field pointing at an object that no longer exists is not harmless: the next reader finds a
    use for it, and that use is not the one the schema documented.
    """
    assert "checkpoint_reference" not in WorkflowRun.model_fields


def test_estimated_cost_is_decimal_on_both_objects() -> None:
    """Matching `AssessmentConfiguration.maximum_cost`, so a limit and a total compare exactly."""
    for model in (WorkflowRun, ExecutionRecord):
        annotation = str(model.model_fields["estimated_cost"].annotation)
        assert "Decimal" in annotation, model.__name__


def test_a_cost_survives_the_round_trip_exactly(ledger: ExecutionLedger) -> None:
    updated = WorkflowRun.model_validate(
        ledger.run.model_dump() | {"estimated_cost": Decimal("5.97")}
    )
    restored = WorkflowRun.model_validate_json(updated.model_dump_json())
    assert restored.estimated_cost == Decimal("5.97")


def test_a_completed_record_must_say_when_it_finished() -> None:
    """`completed_at` is optional because a running record has none, which is what would let a
    completed one carry no end time."""
    with pytest.raises(ValidationError, match="completed_at is unset"):
        ExecutionRecord(
            id="exe-001",
            workflow_run_id="run-001",
            assessment_id="asm-001",
            node_name="ingest",
            node_version="0.1",
            execution_type=ExecutionType.DETERMINISTIC,
            started_at=now(),
            status=ExecutionStatus.COMPLETED,
            retry_number=0,
        )


def test_a_failed_record_must_record_an_error_type() -> None:
    stamp = now()
    with pytest.raises(ValidationError, match="error_type"):
        ExecutionRecord(
            id="exe-001",
            workflow_run_id="run-001",
            assessment_id="asm-001",
            node_name="ingest",
            node_version="0.1",
            execution_type=ExecutionType.DETERMINISTIC,
            started_at=stamp,
            completed_at=stamp,
            status=ExecutionStatus.FAILED,
            retry_number=0,
        )


def test_a_running_record_may_not_claim_an_end_time() -> None:
    stamp = now()
    with pytest.raises(ValidationError, match="running"):
        ExecutionRecord(
            id="exe-001",
            workflow_run_id="run-001",
            assessment_id="asm-001",
            node_name="ingest",
            node_version="0.1",
            execution_type=ExecutionType.DETERMINISTIC,
            started_at=stamp,
            completed_at=stamp,
            status=ExecutionStatus.RUNNING,
            retry_number=0,
        )


def test_the_three_execution_types_are_the_documented_classification() -> None:
    """`agent-design.md` section 4 classifies components as model, deterministic, or checkpoint."""
    assert {member.value for member in ExecutionType} == {
        "model",
        "deterministic",
        "human_checkpoint",
    }


def test_the_run_statuses_are_the_ones_section_26_lists() -> None:
    assert {member.value for member in RunStatus} == {
        "pending",
        "running",
        "paused",
        "completed",
        "failed",
    }


def test_a_retried_record_is_kept_rather_than_replaced() -> None:
    """`retried` is a terminal status, so a superseded attempt stays in the ledger."""
    assert ExecutionStatus.RETRIED in ExecutionStatus
    stamp = now()
    record = ExecutionRecord(
        id="exe-001",
        workflow_run_id="run-001",
        assessment_id="asm-001",
        node_name="extract",
        node_version="0.1",
        execution_type=ExecutionType.MODEL,
        started_at=stamp,
        completed_at=stamp,
        status=ExecutionStatus.RETRIED,
        retry_number=0,
    )
    assert record.status is ExecutionStatus.RETRIED


def test_evidence_references_are_not_confused_with_execution_records(
    ledger: ExecutionLedger,
) -> None:
    """Both are per-assessment lists; a store that mixed them would be caught here."""
    with ledger.record("ingest", node_version="0.1"):
        pass
    assert ledger.handle.objects.list(EvidenceReference) == []
    assert ledger.handle.objects.list(SourceDocument) == []
    assert len(ledger.handle.objects.list(ExecutionRecord)) == 1


# ------------------------------------------------------------------------------------------
# Cache accounting (DEC-067, issue #342)
# ------------------------------------------------------------------------------------------


def _cached_usage(cache_read: int, cache_creation: int) -> ModelUsage:
    return ModelUsage(
        model="claude-opus-5",
        input_tokens=1_000,
        output_tokens=200,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
        estimated_cost=Decimal("0.01"),
    )


def test_cache_spans_land_on_the_record_as_their_own_fields(ledger: ExecutionLedger) -> None:
    """The three input spans are disjoint (DEC-067): nothing folds a cache span into input."""
    with ledger.record(
        "extract", node_version="0.1", execution_type=ExecutionType.MODEL
    ) as execution:
        execution.record_usage(_cached_usage(5_000, 700))
        execution.record_usage(_cached_usage(3_000, 300))

    record = ledger.records()[0]
    assert record.input_tokens == 2_000
    assert record.cache_read_tokens == 8_000
    assert record.cache_creation_tokens == 1_000


def test_the_rollups_equal_the_sum_of_the_records(ledger: ExecutionLedger) -> None:
    """Issue #342's first acceptance criterion, for both cache fields."""
    with ledger.record(
        "extract", node_version="0.1", execution_type=ExecutionType.MODEL
    ) as execution:
        execution.record_usage(_cached_usage(5_000, 700))
    with ledger.record(
        "threats", node_version="0.1", execution_type=ExecutionType.MODEL
    ) as execution:
        execution.record_usage(_cached_usage(11_000, 0))

    completed = ledger.complete()
    records = ledger.records()
    assert completed.total_cache_read_tokens == sum(r.cache_read_tokens or 0 for r in records)
    assert completed.total_cache_creation_tokens == sum(
        r.cache_creation_tokens or 0 for r in records
    )
    assert completed.total_cache_read_tokens == 16_000
    assert completed.total_cache_creation_tokens == 700


def test_unreported_cache_spans_stay_absent(ledger: ExecutionLedger) -> None:
    """Absent means "not reported" (DEC-067): a run with no cache activity rolls up to None."""
    with ledger.record(
        "extract", node_version="0.1", execution_type=ExecutionType.MODEL
    ) as execution:
        execution.record_usage(_cached_usage(0, 0))

    completed = ledger.complete()
    record = ledger.records()[0]
    assert record.cache_read_tokens is None
    assert record.cache_creation_tokens is None
    assert completed.total_cache_read_tokens is None
    assert completed.total_cache_creation_tokens is None


def test_estimated_cost_applies_the_decided_cache_weights() -> None:
    """Issue #342's second acceptance criterion: reads at the discount, creation at the premium,
    uncached input and output at list — the DEC-067 weighted sum, owned by the profile."""
    from trace_ai.infrastructure.model.profiles import resolve_profile

    profile = resolve_profile("primary-development")
    cost = profile.cost_of(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_creation_tokens=1_000_000,
    )
    assert cost == (
        profile.input_cost_per_million
        + profile.output_cost_per_million
        + profile.cache_read_cost_per_million
        + profile.cache_creation_cost_per_million
    )
    assert profile.cache_read_cost_per_million < profile.input_cost_per_million
    assert profile.cache_creation_cost_per_million > profile.input_cost_per_million
