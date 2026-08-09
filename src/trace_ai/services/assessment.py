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
    "AssessmentNotFoundError",
    "AssessmentService",
    "AssessmentStatus",
    "InvalidStatusTransitionError",
]

# The `ObjectStatus` members an assessment may occupy, and where each may go next.
#
# Section 4.1 says "not every object needs every status", and this is one of the objects that
# does not. `candidate` describes a proposed object awaiting validation, which an assessment never
# is -- it is created, worked on, reviewed, and finished. `rejected` and `superseded` describe an
# object replaced or refused within an assessment, which the assessment itself cannot be.
#
# The corpus does not state this table, and #148 decides what replaces it. This is the narrowest
# reading that supports the workflow the rest of the corpus describes: work, then review, then
# approval, with `archived` terminal and reachable from anywhere.
#
# Two things here are known to be wrong and are kept only until #148 lands, because changing them
# without the decision would move the guess rather than settle it. `pending_review` means "at a
# checkpoint", which is ambiguous between the two checkpoints and duplicates
# `WorkflowRun.status == paused` -- a second authoritative answer to a question DEC-017 already
# answers. And `approved -> pending_review` implies a re-review that no node produces.
ASSESSMENT_TRANSITIONS: Final[dict[ObjectStatus, frozenset[ObjectStatus]]] = {
    ObjectStatus.DRAFT: frozenset({ObjectStatus.PENDING_REVIEW, ObjectStatus.ARCHIVED}),
    ObjectStatus.PENDING_REVIEW: frozenset(
        {ObjectStatus.APPROVED, ObjectStatus.DRAFT, ObjectStatus.ARCHIVED}
    ),
    ObjectStatus.APPROVED: frozenset({ObjectStatus.PENDING_REVIEW, ObjectStatus.ARCHIVED}),
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

    def update_status(self, assessment_id: str, status: ObjectStatus) -> Assessment:
        """Move an assessment to a new status, refreshing `updated_at`.

        The object is rebuilt through `model_validate` rather than `model_copy`, because
        `model_copy` validates nothing -- the edit path is the one place a value that did not come
        from the schema enters an object, and it is the worst place to skip it.
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
