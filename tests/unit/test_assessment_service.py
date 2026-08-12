"""Tests for `AssessmentService`: creation, lookup, status, and the boundary between assessments.

This is the first place the two stores are used together, so it is the first place a half-created
state is possible. There is no transaction spanning SQLite and the filesystem; `create` orders the
two and cleans up on failure, and the test that matters injects a failure between them.

The isolation tests are the other half. `current-architecture.md` section 12 makes the
assessment-data boundary a trust boundary, and both stores enforce it individually -- this file
asserts it end to end, because a service that hands out the wrong repository would satisfy every
test in either store's own file. Issue #50.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from trace_ai.domain.assessment import (
    Assessment,
    AssessmentConfiguration,
    default_configuration,
)
from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import AssessmentId, EvidenceReferenceId, SourceDocumentId
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.filesystem.artifact_store import AREAS
from trace_ai.services.assessment import (
    ASSESSMENT_TRANSITIONS,
    AssessmentNotApprovableError,
    AssessmentNotFoundError,
    AssessmentService,
    InvalidStatusTransitionError,
    NonAuthoritativeRunError,
)


def _completed_run(
    service: AssessmentService, assessment_id: str, *, ablations: tuple[str, ...] = ()
) -> str:
    """A completed run whose report the assessment carries, so `approve` has a deliverable.

    Built directly against the repository: these are lifecycle tests, and running the whole
    pipeline to produce a real report would test the driver, not the transition.
    """
    from trace_ai.domain.execution import RunStatus, WorkflowRun
    from trace_ai.services.execution_ledger import start_run

    handle = service.handle(assessment_id)
    run = start_run(handle, workflow_version="0.1", model_profile="offline-fake")
    completed = WorkflowRun.model_validate(
        run.model_dump()
        | {"status": RunStatus.COMPLETED, "completed_at": now(), "ablations": list(ablations)}
    )
    assessment = service.get(assessment_id)
    with handle.objects.transaction():
        handle.objects.save(completed)
        handle.objects.save(
            Assessment.model_validate(
                assessment.model_dump() | {"final_report_path": f"outputs/report-{completed.id}.md"}
            )
        )
    return completed.id


class SourceDocument(DomainModel):
    """Named for the real object so `status()` counts it; #52 replaces this."""

    id: SourceDocumentId
    assessment_id: AssessmentId
    filename: str
    status: ObjectStatus = ObjectStatus.DRAFT
    created_at: datetime


class EvidenceReference(DomainModel):
    """Named for the real object so `status()` counts it; #51 replaces this."""

    id: EvidenceReferenceId
    assessment_id: AssessmentId
    quoted_text: str
    status: ObjectStatus = ObjectStatus.DRAFT
    created_at: datetime


@pytest.fixture
def service(tmp_path: Path) -> Iterator[AssessmentService]:
    with AssessmentStore.at_root(tmp_path) as store:
        yield AssessmentService(store, artifact_root=tmp_path)


def a_configuration() -> AssessmentConfiguration:
    return default_configuration("primary-development", "stride-scenario-based")


# ------------------------------------------------------------------------------------------
# Creation
# ------------------------------------------------------------------------------------------


def test_create_returns_an_assessment_that_get_returns_unchanged(
    service: AssessmentService,
) -> None:
    created = service.create(
        "ForgeFlow Security Review",
        a_configuration(),
        description="A fictional developer platform",
        tags=["demo"],
    )
    assert service.get(created.id) == created
    assert service.get(created.id).configuration == created.configuration


def test_create_allocates_sequential_identifiers(service: AssessmentService) -> None:
    """Assessment identifiers are unique across the database, not within one.

    They are the one prefix DEC-018's per-assessment counter cannot scope, because an assessment
    identifier is what every other identifier is qualified by.
    """
    first = service.create("First", a_configuration())
    second = service.create("Second", a_configuration())
    assert (first.id, second.id) == ("asm-001", "asm-002")


def test_create_makes_the_artifact_directory_with_all_five_areas(
    service: AssessmentService, tmp_path: Path
) -> None:
    created = service.create("Review", a_configuration())
    root = tmp_path / "assessments" / created.id
    for area in AREAS:
        assert (root / area).is_dir(), area


def test_a_created_assessment_starts_as_a_draft(service: AssessmentService) -> None:
    assert service.create("Review", a_configuration()).status is ObjectStatus.DRAFT


def test_creation_needs_no_api_key_or_network(
    service: AssessmentService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roadmap Stage 1: the foundation is verifiable with no model call."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert service.create("Review", a_configuration()).id


def test_a_failure_after_the_directory_leaves_neither_half(
    service: AssessmentService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The injected failure. A half-created assessment is worse than no assessment.

    Every later step would have to ask whether what it found was finished, and nothing in the
    object says.
    """

    def explode(self: object, obj: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr("trace_ai.infrastructure.database.store.AssessmentRepository.save", explode)

    with pytest.raises(RuntimeError, match="disk full"):
        service.create("Review", a_configuration())

    monkeypatch.undo()
    assert not (tmp_path / "assessments" / "asm-001").exists(), "the directory survived"
    with pytest.raises(AssessmentNotFoundError):
        service.get("asm-001")
    assert service.list() == []


def test_a_failed_creation_does_not_block_the_next_one(
    service: AssessmentService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The identifier is consumed, because DEC-018's counter is monotonic and gaps are expected."""

    def explode(self: object, obj: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr("trace_ai.infrastructure.database.store.AssessmentRepository.save", explode)
    with pytest.raises(RuntimeError):
        service.create("Doomed", a_configuration())
    monkeypatch.undo()

    recovered = service.create("Recovered", a_configuration())
    assert recovered.id == "asm-002", "a discarded number must not be handed out again"


# ------------------------------------------------------------------------------------------
# Lookup
# ------------------------------------------------------------------------------------------


def test_get_raises_for_an_unknown_identifier(service: AssessmentService) -> None:
    """Not `None`: a lookup returning `None` puts the same decision at every call site."""
    with pytest.raises(AssessmentNotFoundError, match="asm-404"):
        service.get("asm-404")


def test_get_raises_for_an_identifier_naming_another_object(service: AssessmentService) -> None:
    with pytest.raises(AssessmentNotFoundError):
        service.get("thr-007")


def test_get_raises_for_a_malformed_identifier(service: AssessmentService) -> None:
    with pytest.raises((AssessmentNotFoundError, ValueError)):
        service.get("not-an-identifier")


def test_list_returns_every_assessment(service: AssessmentService) -> None:
    service.create("First", a_configuration())
    service.create("Second", a_configuration())
    assert [a.name for a in service.list()] == ["First", "Second"]


def test_list_is_empty_on_a_fresh_store(service: AssessmentService) -> None:
    assert service.list() == []


def test_assessments_survive_reopening_the_store(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        AssessmentService(store, artifact_root=tmp_path).create("Review", a_configuration())

    with AssessmentStore.at_root(tmp_path) as reopened:
        assert AssessmentService(reopened, artifact_root=tmp_path).get("asm-001").name == "Review"


# ------------------------------------------------------------------------------------------
# The assessment-data boundary
# ------------------------------------------------------------------------------------------


def register_document(service: AssessmentService, assessment_id: str, index: int) -> None:
    handle = service.handle(assessment_id)
    handle.objects.save(
        SourceDocument(
            id=f"src-{index:03d}",
            assessment_id=assessment_id,
            filename=f"{assessment_id}-{index}.md",
            created_at=now(),
        )
    )


def test_two_assessments_do_not_see_each_others_objects(service: AssessmentService) -> None:
    first = service.create("First", a_configuration())
    second = service.create("Second", a_configuration())
    register_document(service, first.id, 1)
    register_document(service, second.id, 1)

    documents = service.handle(first.id).objects.list(SourceDocument)
    assert [document.filename for document in documents] == ["asm-001-1.md"]


def test_two_assessments_do_not_see_each_others_artifacts(service: AssessmentService) -> None:
    first = service.create("First", a_configuration())
    second = service.create("Second", a_configuration())

    stored = service.handle(second.id).artifacts.store_source("overview.md", b"second\n")
    assert not service.handle(first.id).artifacts.contains(stored)
    assert service.handle(second.id).artifacts.contains(stored)


def test_a_handle_carries_both_stores_scoped_together(service: AssessmentService) -> None:
    """The reason the service returns a handle rather than an identifier."""
    created = service.create("Review", a_configuration())
    handle = service.handle(created.id)

    assert handle.assessment_id == created.id
    assert handle.objects.assessment_id == created.id
    assert handle.artifacts.assessment_id == created.id


def test_a_handle_for_an_unknown_assessment_raises(service: AssessmentService) -> None:
    """A handle is a capability; issuing one for an assessment that does not exist creates it."""
    with pytest.raises(AssessmentNotFoundError):
        service.handle("asm-404")


def test_identifiers_do_not_collide_across_assessments(service: AssessmentService) -> None:
    """`src-001` in two assessments is two documents, per DEC-018."""
    first = service.create("First", a_configuration())
    second = service.create("Second", a_configuration())
    register_document(service, first.id, 1)
    register_document(service, second.id, 1)

    assert service.handle(first.id).objects.get(SourceDocument, "src-001").filename != (
        service.handle(second.id).objects.get(SourceDocument, "src-001").filename
    )


# ------------------------------------------------------------------------------------------
# Status
# ------------------------------------------------------------------------------------------


def test_status_reports_the_assessment_state(service: AssessmentService) -> None:
    created = service.create("Review", a_configuration())
    reported = service.status(created.id)

    assert reported.assessment_id == created.id
    assert reported.status is ObjectStatus.DRAFT
    assert reported.active_workflow_run_id is None


def test_status_counts_registered_objects(service: AssessmentService) -> None:
    created = service.create("Review", a_configuration())
    handle = service.handle(created.id)
    for index in (1, 2, 3):
        register_document(service, created.id, index)
    handle.objects.save(
        EvidenceReference(
            id="evd-001",
            assessment_id=created.id,
            quoted_text="Webhook requests are validated.",
            created_at=now(),
        )
    )

    reported = service.status(created.id)
    assert reported.source_documents == 3
    assert reported.evidence_references == 1


def test_status_counts_nothing_on_a_new_assessment(service: AssessmentService) -> None:
    """The assessment row itself is not counted as content."""
    created = service.create("Review", a_configuration())
    reported = service.status(created.id)
    assert reported.source_documents == 0
    assert reported.evidence_references == 0


def test_status_counts_are_per_assessment(service: AssessmentService) -> None:
    first = service.create("First", a_configuration())
    second = service.create("Second", a_configuration())
    for index in (1, 2):
        register_document(service, first.id, index)
    register_document(service, second.id, 1)

    assert service.status(first.id).source_documents == 2
    assert service.status(second.id).source_documents == 1


def test_status_raises_for_an_unknown_assessment(service: AssessmentService) -> None:
    with pytest.raises(AssessmentNotFoundError):
        service.status("asm-404")


# ------------------------------------------------------------------------------------------
# Status transitions (DEC-031)
# ------------------------------------------------------------------------------------------


def test_the_expected_lifecycle_is_allowed(service: AssessmentService) -> None:
    """Create, pause at a checkpoint, resume, complete, archive."""
    created = service.create("Review", a_configuration())
    service.begin_review(created.id)
    service.resume_from_review(created.id)
    _completed_run(service, created.id)
    service.approve(created.id)
    final = service.archive(created.id)
    assert final.status is ObjectStatus.ARCHIVED


def test_a_transition_refreshes_updated_at(service: AssessmentService) -> None:
    created = service.create("Review", a_configuration())
    updated = service.begin_review(created.id)

    assert updated.updated_at > created.updated_at
    assert updated.created_at == created.created_at, "creation time is not a mutable field"


def test_a_transition_persists(service: AssessmentService) -> None:
    created = service.create("Review", a_configuration())
    service.begin_review(created.id)
    assert service.get(created.id).status is ObjectStatus.PENDING_REVIEW


def test_pending_review_returns_to_draft_not_to_approved(service: AssessmentService) -> None:
    """There is no pending_review to approved edge.

    Resuming from checkpoint 2 returns the run to `running`, and report generation and evaluation
    still follow, so the assessment reaches `approved` when the pipeline finishes rather than when
    the reviewer answers.
    """
    created = service.create("Review", a_configuration())
    service.begin_review(created.id)

    assert ObjectStatus.APPROVED not in ASSESSMENT_TRANSITIONS[ObjectStatus.PENDING_REVIEW]
    assert service.resume_from_review(created.id).status is ObjectStatus.DRAFT


def test_a_disallowed_transition_is_refused(service: AssessmentService) -> None:
    created = service.create("Review", a_configuration())
    service.begin_review(created.id)
    with pytest.raises(InvalidStatusTransitionError, match="may not move to"):
        service.begin_review(created.id)


def test_archived_is_terminal(service: AssessmentService) -> None:
    created = service.create("Review", a_configuration())
    service.archive(created.id)
    with pytest.raises(InvalidStatusTransitionError, match="terminal"):
        service.resume_from_review(created.id)


def test_an_assessment_can_be_archived_from_any_live_status(service: AssessmentService) -> None:
    """An assessment may be abandoned at any point, including while it waits for a human."""
    waiting = service.create("Waiting", a_configuration())
    service.begin_review(waiting.id)
    assert service.archive(waiting.id).status is ObjectStatus.ARCHIVED

    finished = service.create("Finished", a_configuration())
    _completed_run(service, finished.id)
    service.approve(finished.id)
    assert service.archive(finished.id).status is ObjectStatus.ARCHIVED


def test_a_new_run_returns_an_approved_assessment_to_draft(service: AssessmentService) -> None:
    """Its conclusions no longer describe the current state."""
    created = service.create("Review", a_configuration())
    _completed_run(service, created.id)
    service.approve(created.id)
    assert service.begin_revision(created.id).status is ObjectStatus.DRAFT


def test_a_non_authoritative_run_cannot_approve(service: AssessmentService) -> None:
    """DEC-012 marks an ablated run non-authoritative; DEC-005 is what that protects.

    Findings no human approved must not become an approved assessment, and the gate belongs here
    rather than in the harness that produced the run.
    """
    created = service.create("Review", a_configuration())
    _completed_run(service, created.id, ablations=("no-critical-review",))
    with pytest.raises(NonAuthoritativeRunError, match="non-authoritative"):
        service.approve(created.id)

    assert service.get(created.id).status is ObjectStatus.DRAFT


def test_approval_is_refused_while_no_report_exists(service: AssessmentService) -> None:
    """DEC-082: the sign-off needs a deliverable; a bare assessment is refused in one line."""
    created = service.create("Review", a_configuration())
    with pytest.raises(AssessmentNotApprovableError, match="no report has been rendered"):
        service.approve(created.id)
    assert service.get(created.id).status is ObjectStatus.DRAFT


def test_approval_is_refused_while_the_reports_run_is_not_completed(
    service: AssessmentService,
) -> None:
    """A report naming a run that did not complete is not a finished deliverable."""
    from trace_ai.services.execution_ledger import start_run

    created = service.create("Review", a_configuration())
    handle = service.handle(created.id)
    run = start_run(handle, workflow_version="0.1", model_profile="offline-fake")
    with handle.objects.transaction():
        handle.objects.save(
            Assessment.model_validate(
                service.get(created.id).model_dump()
                | {"final_report_path": f"outputs/report-{run.id}.md"}
            )
        )
    with pytest.raises(AssessmentNotApprovableError, match="not completed"):
        service.approve(created.id)


def test_there_is_no_generic_status_setter(service: AssessmentService) -> None:
    """The transitions are named verbs, one per edge.

    A setter taking an arbitrary `ObjectStatus` is what let #50's version mean "at a checkpoint"
    without anyone deciding it should, and it would let a caller reach a status the table excludes
    by passing it.
    """
    public = {name for name in vars(AssessmentService) if not name.startswith("_")}
    assert "update_status" not in public
    assert {"archive", "begin_review", "resume_from_review", "approve", "begin_revision"} <= public


@pytest.mark.parametrize(
    "status", [ObjectStatus.CANDIDATE, ObjectStatus.REJECTED, ObjectStatus.SUPERSEDED]
)
def test_an_excluded_status_is_unreachable(status: ObjectStatus) -> None:
    """Section 4.1: not every object needs every status.

    `candidate` describes an agent proposal awaiting validation, which an assessment never is.
    `rejected` would report a completed assessment with zero findings as a failure, and
    design-principles.md treats that as a success. `superseded` belongs to re-generated objects,
    which DEC-023 limits to the two carrying `supersedes_id`.
    """
    assert status not in ASSESSMENT_TRANSITIONS
    reachable = {target for targets in ASSESSMENT_TRANSITIONS.values() for target in targets}
    assert status not in reachable


def test_there_is_no_failed_assessment_status(service: AssessmentService) -> None:
    """A failed run does not fail its assessment (DEC-031).

    `WorkflowRun.status` becomes `failed` and the assessment stays `draft`, because an assessment
    with a failed run is one somebody may run again. Nothing in the table can express failure, and
    that is deliberate rather than an omission.
    """
    reachable = {target for targets in ASSESSMENT_TRANSITIONS.values() for target in targets}
    assert not [status for status in reachable if "fail" in status.value]
    assert not [name for name in vars(AssessmentService) if "fail" in name]


def test_the_transition_table_only_names_reachable_statuses() -> None:
    """A status that can be entered but has no row saying where it may go is a one-way trap."""
    reachable = {target for targets in ASSESSMENT_TRANSITIONS.values() for target in targets}
    assert reachable <= set(ASSESSMENT_TRANSITIONS)


def test_every_status_can_reach_archived() -> None:
    for status, targets in ASSESSMENT_TRANSITIONS.items():
        if status is not ObjectStatus.ARCHIVED:
            assert ObjectStatus.ARCHIVED in targets, status


def test_a_transition_can_join_an_enclosing_transaction(service: AssessmentService) -> None:
    """DEC-031 requires the assessment status and the run status to be written together.

    The store holds transaction depth, so a caller wrapping both writes in one
    `repository.transaction()` gets one commit. This proves the inner write defers rather than
    landing early, which is what makes the pair atomic once `WorkflowRun` exists.
    """
    created = service.create("Review", a_configuration())
    repository = service.handle(created.id).objects

    with pytest.raises(RuntimeError, match="run write failed"), repository.transaction():
        service.begin_review(created.id)
        raise RuntimeError("run write failed")

    assert service.get(created.id).status is ObjectStatus.DRAFT, (
        "the status committed on its own instead of deferring to the enclosing transaction"
    )


def test_a_transition_does_not_use_model_copy(service: AssessmentService) -> None:
    """The edited object is rebuilt through the schema; `model_copy` validates nothing."""
    created = service.create("Review", a_configuration())
    updated = service.begin_review(created.id)
    assert isinstance(updated.status, ObjectStatus)
    assert Assessment.model_validate_json(updated.model_dump_json()) == updated


def test_the_artifact_directory_survives_a_status_change(
    service: AssessmentService, tmp_path: Path
) -> None:
    created = service.create("Review", a_configuration())
    service.handle(created.id).artifacts.store_source("overview.md", b"content\n")
    service.begin_review(created.id)

    assert service.handle(created.id).artifacts.read("sources", "overview.md") == b"content\n"


def test_removing_the_directory_does_not_remove_the_assessment(
    service: AssessmentService, tmp_path: Path
) -> None:
    """The known limit of `create`'s cleanup: the two stores can still diverge afterwards.

    DEC-020 records this as an open question -- whether anything detects that `data/` and the
    database have diverged -- and nothing does yet. Stated here so the gap is visible.
    """
    created = service.create("Review", a_configuration())
    shutil.rmtree(tmp_path / "assessments" / created.id)

    assert service.get(created.id).id == created.id
