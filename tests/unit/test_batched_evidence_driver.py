"""The batched evidence-validation shape at the driver's seam (DEC-134).

The node tests hold the per-batch contract; these hold what the driver decides around it: which
workflow versions carry which shape, how a subject list splits into batches, and that several
batch proposals validate and persist as one set. The recorded corpus's compatibility rides the
version pin, so the selection function is pinned here in both directions.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import WORKFLOW_VERSION, default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import EvidenceAssessment, Recommendation, SubjectType
from trace_ai.domain.execution import ExecutionRecord, ExecutionType
from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.driver import (
    EVIDENCE_BATCH_SIZE,
    EvidenceAssessmentValidationAdapter,
    EvidenceValidationAdapter,
    _batched_evidence,
    _EvidenceHandoff,
)
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")


def test_the_version_pin_selects_the_call_shape() -> None:
    """Recordings pinned below 0.2 replay the single call they carry; everything current
    batches. An unparseable version is treated as current, never as an old recording."""
    assert not _batched_evidence("0.1")
    assert _batched_evidence("0.2")
    assert _batched_evidence("0.10")
    assert _batched_evidence("1.0")
    assert _batched_evidence("not-a-version")
    assert _batched_evidence(WORKFLOW_VERSION), "the current build batches"


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, ExecutionLedger, list[str]]]:
    """An assessment one subject past the batch size, so the split is two batches."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Batched", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        index_document(
            handle,
            DocumentLoader(handle).load_document(
                FORGEFLOW / "architecture-overview.md",
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            ),
        )
        cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]
        stamped = now()
        claim_ids: list[str] = []
        with handle.objects.transaction():
            component = Component.model_validate(
                {
                    "id": handle.objects.allocate("cmp"),
                    "assessment_id": handle.assessment_id,
                    "name": "Analysis Worker",
                    "component_type": "background_worker",
                    "evidence_ids": [cited],
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            )
            handle.objects.save(component)
            for position in range(EVIDENCE_BATCH_SIZE + 1):
                claim = ContextClaim.model_validate(
                    {
                        "id": handle.objects.allocate("ctx"),
                        "assessment_id": handle.assessment_id,
                        "subject_type": "component",
                        "subject_id": component.id,
                        "predicate": f"documented property {position}",
                        "value": "documented as present",
                        "status": "documented",
                        "confidence": ConfidenceLevel.MEDIUM,
                        "evidence_ids": [cited],
                        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                        "created_at": stamped,
                        "updated_at": stamped,
                    }
                )
                handle.objects.save(claim)
                claim_ids.append(claim.id)
        run = start_run(
            handle, workflow_version=WORKFLOW_VERSION, model_profile="primary-development"
        )
        yield handle, ExecutionLedger(handle, run), claim_ids


def _assessment_for(subject_id: str, cited: str) -> dict[str, Any]:
    return {
        "subject_type": SubjectType.CONTEXT_CLAIM,
        "subject_id": subject_id,
        "evidence_ids": [cited],
        "evidence_strengths": {cited: EvidenceStrength.DIRECT},
        "validation_status": ValidationStatus.SUPPORTED,
        "rationale": "The cited passage states the property.",
        "confidence": ConfidenceLevel.MEDIUM,
        "recommendation": Recommendation.CONTINUE,
    }


def test_two_batches_validate_and_persist_as_one_set(
    prepared: tuple[AssessmentHandle, ExecutionLedger, list[str]],
) -> None:
    """One subject past the batch size makes two calls, and the deterministic node persists the
    union — the batch boundary is a call-shape fact, not an analytical one."""
    handle, ledger, claim_ids = prepared
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]
    first, second = claim_ids[:EVIDENCE_BATCH_SIZE], claim_ids[EVIDENCE_BATCH_SIZE:]
    responses = [
        EvidenceValidationProposal.model_validate(
            {"assessments": [_assessment_for(subject_id, cited) for subject_id in batch]}
        )
        for batch in (first, second)
    ]
    context = NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=ledger.run.id
        ),
        model=DeterministicModel(responses),
    )
    handoff = _EvidenceHandoff()
    agent = EvidenceValidationAdapter(
        ledger=ledger, profile=PROFILE, registry=PromptRegistry(), handoff=handoff
    )

    result = agent.run(context)

    assert result.metadata["batches"] == 2
    assert result.metadata["subjects"] == len(claim_ids)
    assert len(handoff.outcomes) == 2

    validated = EvidenceAssessmentValidationAdapter(handoff=handoff).run(context)

    persisted = handle.objects.list(EvidenceAssessment)
    assert len(persisted) == len(claim_ids)
    assert validated.metadata["unassessed_subject_count"] == 0
    executions = [
        record
        for record in handle.objects.list(ExecutionRecord)
        if record.execution_type is ExecutionType.MODEL
        and record.node_name == "evidence-validation"
    ]
    assert len(executions) == 2
