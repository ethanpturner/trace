"""Creating, reading, and advancing assessments: the seam between the two stores.

`current-architecture.md` section 5.2 gives the application service assessment creation, input
validation, file registration, and configuration management, and says it holds no agent prompts and
no substantial security-analysis logic. This is that service for the assessment itself.

**Creation is one operation.** An assessment persisted without its artifact directory, or a
directory without a persisted assessment, is a half-created state the rest of the milestone would
have to handle everywhere. There is no transaction spanning SQLite and the filesystem, so the two
are ordered and the failure path is explicit: directories first because they are cheap and
reversible, the row second inside a transaction, and any failure removes what was created. The
result is not atomicity -- a process killed between the two still leaves a directory -- but an
empty directory is inert, and a persisted assessment whose files are missing is not.

**A caller gets a handle, not an identifier.** `AssessmentHandle` carries the scoped repository and
the scoped artifact store together, so code holding one assessment cannot address another by
passing a different string. That is `current-architecture.md` section 12's boundary expressed the
same way both stores express it: as the object you hold rather than an argument you supply.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.assessment import Assessment, new_assessment
from trace_ai.domain.base import now
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import parse_id
from trace_ai.infrastructure.database.store import AssessmentRepository, StoreError
from trace_ai.infrastructure.filesystem.artifact_store import AREAS, ArtifactStore

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.domain.assessment import AssessmentConfiguration
    from trace_ai.infrastructure.database.store import AssessmentStore

__all__ = [
    "ASSESSMENT_TRANSITIONS",
    "AssessmentExistsError",
    "AssessmentHandle",
    "AssessmentNotApprovableError",
    "AssessmentNotFoundError",
    "AssessmentService",
    "AssessmentStatus",
    "InvalidStatusTransitionError",
    "NonAuthoritativeRunError",
]

# The `ObjectStatus` members an assessment may occupy, and where each may go next (DEC-031).
#
# `Assessment.status` is the deliverable's lifecycle -- may these conclusions be used, may work
# continue -- and never where the pipeline has reached. That belongs to `WorkflowRun.status`, and
# an assessment may have several runs, so it cannot mirror one.
#
# `pending_review` says that a human is required, never which of the two checkpoints;
# `WorkflowRun.current_node` says which. There is no `pending_review` to `approved` edge: resuming
# from checkpoint 2 returns the run to `running` and report generation still follows, so the
# assessment returns to `draft` and reaches `approved` when the pipeline finishes.
#
# `candidate`, `rejected`, and `superseded` are excluded. An assessment is never proposed by an
# agent; an assessment whose findings were all rejected is a completed assessment with zero
# findings, which design-principles.md treats as a success; and supersession belongs to
# re-generated objects, which DEC-023 limits to the two carrying `supersedes_id`.
ASSESSMENT_TRANSITIONS: Final[dict[ObjectStatus, frozenset[ObjectStatus]]] = {
    ObjectStatus.DRAFT: frozenset(
        {ObjectStatus.PENDING_REVIEW, ObjectStatus.APPROVED, ObjectStatus.ARCHIVED}
    ),
    ObjectStatus.PENDING_REVIEW: frozenset({ObjectStatus.DRAFT, ObjectStatus.ARCHIVED}),
    ObjectStatus.APPROVED: frozenset({ObjectStatus.DRAFT, ObjectStatus.ARCHIVED}),
    ObjectStatus.ARCHIVED: frozenset(),
}


class AssessmentServiceError(RuntimeError):
    """Something the service must refuse."""


class AssessmentNotFoundError(AssessmentServiceError):
    """No such assessment. Raised rather than returning `None`.

    A lookup that returns `None` puts the decision at every call site, and the decision is always
    the same: stop. Raising makes it one decision, made here.
    """

    def __init__(self, assessment_id: str) -> None:
        super().__init__(f"no assessment {assessment_id!r} in this store")
        self.assessment_id = assessment_id


class AssessmentExistsError(AssessmentServiceError):
    """An assessment with this identifier is already stored."""

    def __init__(self, assessment_id: str) -> None:
        super().__init__(
            f"assessment {assessment_id!r} already exists. Identifiers come from the store's "
            f"counter and are never reused, so this means two stores were mixed."
        )


class AssessmentNotApprovableError(AssessmentServiceError):
    """Approval is a sign-off on a finished deliverable, and this assessment lacks one (DEC-082).

    The refusal names what is missing — no rendered report, or a report whose run did not
    complete — so the operator knows what has to happen first rather than which flag to force.
    """

    def __init__(self, assessment_id: str, reason: str) -> None:
        super().__init__(f"{assessment_id} cannot be approved: {reason}")


class NonAuthoritativeRunError(AssessmentServiceError):
    """An ablated run may not produce an approved assessment.

    DEC-012 records a run that ablates a component as non-authoritative, and evaluation-plan.md
    section 14 ablates the human checkpoints. Findings that no human approved becoming an approved
    assessment is exactly what DEC-005 exists to prevent, so the gate is here rather than in the
    harness that produced the run.
    """

    def __init__(self, assessment_id: str) -> None:
        super().__init__(
            f"{assessment_id} cannot be approved: the completing run is non-authoritative. "
            f"An ablated run produces findings no human approved (DEC-012, DEC-031)."
        )


class InvalidStatusTransitionError(AssessmentServiceError):
    """A status change the assessment lifecycle does not allow."""

    def __init__(self, current: ObjectStatus, requested: ObjectStatus) -> None:
        allowed = sorted(ASSESSMENT_TRANSITIONS.get(current, frozenset()))
        super().__init__(
            f"an assessment in {current} may not move to {requested}. "
            f"Allowed from {current}: {allowed or 'nothing; it is terminal'}."
        )
        self.current = current
        self.requested = requested


@dataclass(frozen=True, slots=True)
class AssessmentHandle:
    """Everything belonging to one assessment, and nothing belonging to another."""

    assessment_id: str
    objects: AssessmentRepository
    artifacts: ArtifactStore


@dataclass(frozen=True, slots=True)
class AssessmentStatus:
    """What `trace assessment status` reports."""

    assessment_id: str
    status: ObjectStatus
    active_workflow_run_id: str | None
    object_counts: dict[str, int]

    @property
    def source_documents(self) -> int:
        return self.object_counts.get("SourceDocument", 0)

    @property
    def evidence_references(self) -> int:
        return self.object_counts.get("EvidenceReference", 0)


class AssessmentService:
    """Assessment lifecycle over the assessment store and the artifact store."""

    def __init__(self, store: AssessmentStore, artifact_root: Path) -> None:
        self._store = store
        self._artifact_root = artifact_root

    def handle(self, assessment_id: str) -> AssessmentHandle:
        """A scoped view. Raises if the assessment does not exist."""
        self.get(assessment_id)
        return self._handle(assessment_id)

    def _handle(self, assessment_id: str) -> AssessmentHandle:
        return AssessmentHandle(
            assessment_id=assessment_id,
            objects=self._store.repository(assessment_id),
            artifacts=ArtifactStore(assessment_id, root=self._artifact_root),
        )

    def create(
        self,
        name: str,
        configuration: AssessmentConfiguration,
        *,
        description: str | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
    ) -> Assessment:
        """Allocate an identifier, write the directory and the row, or leave neither behind."""
        assessment_id = self._store.allocate_assessment_id()
        repository = self._store.repository(assessment_id)

        if repository.find(Assessment, assessment_id) is not None:
            raise AssessmentExistsError(assessment_id)

        artifacts = ArtifactStore(assessment_id, root=self._artifact_root)
        for area in AREAS:
            artifacts.area(area)

        assessment = new_assessment(
            assessment_id,
            name,
            configuration,
            description=description,
            tags=tags or [],
            created_by=created_by,
        )
        try:
            with repository.transaction():
                repository.save(assessment)
        except BaseException:
            # The row is rolled back by the transaction; the directory is not, so remove it here.
            # A half-created assessment is worse than none: every later step would have to ask
            # whether the thing it found was finished.
            shutil.rmtree(artifacts.assessment_root, ignore_errors=True)
            raise

        return assessment

    def get(self, assessment_id: str) -> Assessment:
        parsed = parse_id(assessment_id)
        if parsed.prefix != "asm":
            raise AssessmentNotFoundError(assessment_id)
        try:
            found = self._store.repository(assessment_id).find(Assessment, assessment_id)
        except StoreError as error:  # a scope the store itself refuses
            raise AssessmentNotFoundError(assessment_id) from error
        if found is None:
            raise AssessmentNotFoundError(assessment_id)
        return found

    def list(self) -> list[Assessment]:
        """Every assessment in the store, oldest identifier first."""
        found: list[Assessment] = []
        for assessment_id in self._store.assessment_ids():
            existing = self._store.repository(assessment_id).find(Assessment, assessment_id)
            if existing is not None:
                found.append(existing)
        return found

    def status(self, assessment_id: str) -> AssessmentStatus:
        """The assessment's state and what it holds.

        Counts are reported per object type rather than for a fixed pair, because the types this
        milestone counts -- `SourceDocument` and `EvidenceReference` -- arrive with #52 and #51,
        and a hard-coded pair would report zero for everything else forever.
        """
        assessment = self.get(assessment_id)
        return AssessmentStatus(
            assessment_id=assessment_id,
            status=assessment.status,
            active_workflow_run_id=assessment.active_workflow_run_id,
            object_counts=self._store.repository(assessment_id).counts_by_type(),
        )

    def archive(self, assessment_id: str) -> Assessment:
        """Retire an assessment. The only transition a person performs (DEC-031).

        Reachable from every non-terminal status, because an assessment may be abandoned at any
        point -- including while it waits for a human who is not coming back.
        """
        return self._transition(assessment_id, ObjectStatus.ARCHIVED)

    def begin_review(self, assessment_id: str) -> Assessment:
        """A checkpoint has paused the run and is waiting for a human.

        DEC-031 requires this to be written in the same transaction that sets
        `WorkflowRun.status` to `paused`. The store's transaction depth lives on the store, so a
        caller that wraps both in one `repository.transaction()` gets exactly that -- the commit
        here defers to the enclosing one rather than landing early.
        """
        return self._transition(assessment_id, ObjectStatus.PENDING_REVIEW)

    def resume_from_review(self, assessment_id: str) -> Assessment:
        """Every pending object has a `ReviewerDecision`; the run continues (DEC-017)."""
        return self._transition(assessment_id, ObjectStatus.DRAFT)

    def approve(self, assessment_id: str) -> Assessment:
        """The person's sign-off on the completed deliverable (DEC-082).

        Three refusals make this a sign-off rather than a status setter: a rendered report must
        exist, the run that rendered it must have completed, and that run must be authoritative
        (DEC-012 — findings no human approved must not become an approved assessment). The
        checkpoints are not bypassed because no report exists without passing both; what this
        verb adds is the judgment the terminal node cannot make — that a person has read the
        rendered document and stands behind it.
        """
        from trace_ai.domain.execution import RunStatus, WorkflowRun

        current = self.get(assessment_id)
        if current.final_report_path is None:
            raise AssessmentNotApprovableError(
                assessment_id,
                "no report has been rendered; run the pipeline to completion first",
            )
        # The report filename embeds the run that rendered it (report-<run-id>.md), so the
        # sign-off binds to that run rather than to whichever run happens to be latest.
        run_id = (
            current.final_report_path.rpartition("/")[2].removeprefix("report-").removesuffix(".md")
        )
        repository = self._store.repository(assessment_id)
        run = next((run for run in repository.list(WorkflowRun) if run.id == run_id), None)
        if run is None:
            raise AssessmentNotApprovableError(
                assessment_id, f"the report names run {run_id!r}, which this assessment lacks"
            )
        if run.status is not RunStatus.COMPLETED:
            raise AssessmentNotApprovableError(
                assessment_id,
                f"the report's run {run.id} is {run.status.value}, not completed",
            )
        if not run.is_authoritative:
            raise NonAuthoritativeRunError(assessment_id)
        return self._transition(assessment_id, ObjectStatus.APPROVED)

    def begin_revision(self, assessment_id: str) -> Assessment:
        """A new run begins against an approved assessment, so its conclusions are stale again."""
        return self._transition(assessment_id, ObjectStatus.DRAFT)

    def _transition(self, assessment_id: str, status: ObjectStatus) -> Assessment:
        """Apply a transition, refreshing `updated_at`.

        Private, and reached only through the named verbs above, so no caller can set an arbitrary
        status. A generic setter would re-admit the ambiguity DEC-031 removes -- it is what let
        #50's version mean "at a checkpoint" without anyone deciding it should.

        The object is rebuilt through `model_validate` rather than `model_copy`, because
        `model_copy` validates nothing and this is the edit path.
        """
        current = self.get(assessment_id)
        if status not in ASSESSMENT_TRANSITIONS.get(current.status, frozenset()):
            raise InvalidStatusTransitionError(current.status, status)

        updated = Assessment.model_validate(
            current.model_dump() | {"status": status, "updated_at": now()}
        )
        repository = self._store.repository(assessment_id)
        with repository.transaction():
            repository.save(updated)
        return updated
