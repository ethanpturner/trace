"""`trace verify` and the walk behind it (#262).

The property under test is tamper evidence: a stored file whose bytes changed out of band no
longer matches the hash recorded when it was assessed, and the walk says so by identifier and
hash — never by content. The manifest checks are agreement-with-the-store-now: the report's bytes
against its pin, and the approved counts against the objects the assessment holds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.verification import verify_assessment

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        document = loader.load_document(
            FORGEFLOW / "architecture-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )
        index_document(handle, document)
        yield handle


def test_a_clean_assessment_verifies(handle: AssessmentHandle) -> None:
    outcome = verify_assessment(handle)

    assert outcome.ok
    assert outcome.document_count == 1
    assert outcome.evidence_count > 0
    assert not outcome.manifest_checked, "no report exists yet, and the walk says so"


def test_a_tampered_source_document_is_named_with_both_hashes(handle: AssessmentHandle) -> None:
    stored = handle.artifacts.area("sources") / "architecture-overview.md"
    stored.write_text("changed out of band", encoding="utf-8")

    outcome = verify_assessment(handle)

    assert not outcome.ok
    (drift,) = outcome.document_drift
    assert drift.subject == "src-001"
    assert drift.expected.startswith("sha256:")
    assert drift.found.startswith("sha256:")
    assert drift.expected != drift.found
    assert "changed out of band" not in drift.line()
    assert outcome.evidence_failures, "the references into the changed file fail with it"


def test_a_missing_source_document_reads_artifact_missing(handle: AssessmentHandle) -> None:
    (handle.artifacts.area("sources") / "architecture-overview.md").unlink()

    outcome = verify_assessment(handle)

    assert not outcome.ok
    (drift,) = outcome.document_drift
    assert drift.found == "artifact_missing"
