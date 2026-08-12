"""`WorkflowRun` and `ExecutionRecord`: the audit record, written before there is much to audit.

`data-model.md` section 34 says model-generated objects should carry generation metadata and that
the MVP should prefer linked execution records to duplicating that metadata onto every object. That
makes the ledger a prerequisite for the first agent rather than a convenience: without it, the first
model-assisted node either invents its own record or stamps provenance onto every object it
produces, and both are hard to undo once written.

`current-architecture.md` section 5.17 makes local audit records the authoritative execution record.
Nothing exports them anywhere, and `enable_external_tracing` is off unless someone turns it on.

**`checkpoint_reference` is absent, and its absence is a decision.** Earlier versions of section 26
carried it, holding a persistence reference to a framework checkpoint. DEC-016 removed the framework
and DEC-017 removed the field: `current_node` says where a run stopped and the assessment state's
pending-review block says what it is waiting for. A third field pointing at an object that no longer
exists is vestigial, and the next reader would find a use for it that the schema does not document.

**`total_model_calls` is required and is zero for every run in this milestone.** That is the correct
value rather than a placeholder, and a test asserts it after a full ingestion and indexing pass:
nothing here calls a model, and a ledger that could not express *no model was used* would be a
ledger that assumed one was.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import AssessmentId, ExecutionRecordId, WorkflowRunId

__all__ = [
    "ExecutionRecord",
    "ExecutionStatus",
    "ExecutionType",
    "RunStatus",
    "WorkflowRun",
]


class RunStatus(StrEnum):
    """A workflow run's state, as section 26 enumerates it."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    """Stopped at a checkpoint. DEC-017 makes this a complete, self-describing record on disk:
    the process exits, and `current_node` names the checkpoint it stopped at."""
    COMPLETED = "completed"
    FAILED = "failed"
    """A failed run does not fail its assessment (DEC-031). Another run may be started."""


class ExecutionStatus(StrEnum):
    """One node execution's state, as section 27 enumerates it."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRIED = "retried"
    """Superseded by a later attempt. The record stays: `agent-design.md` section 26 bounds
    retries, and a retry that erased its predecessor would make the bound unmeasurable."""


class ExecutionType(StrEnum):
    """What kind of step ran, per `agent-design.md` section 4's classification."""

    MODEL = "model"
    DETERMINISTIC = "deterministic"
    HUMAN_CHECKPOINT = "human_checkpoint"
    """A checkpoint is an execution too. It takes time, it can be waited on indefinitely, and the
    reviewer's decision is the thing the run resumed from -- so it belongs in the same record as
    everything else rather than being inferred from a gap between two others."""


class WorkflowRun(DomainModel):
    """One execution of the assessment workflow (section 26).

    An assessment may have several: retries, revisions, and evaluations all produce their own.
    """

    id: WorkflowRunId
    assessment_id: AssessmentId
    workflow_version: str
    status: RunStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_node: str | None = None
    model_profile: str
    prompt_versions: dict[str, str]
    total_model_calls: int = Field(ge=0)
    total_input_tokens: int | None = Field(default=None, ge=0)
    total_output_tokens: int | None = Field(default=None, ge=0)
    total_cache_read_tokens: int | None = Field(default=None, ge=0)
    total_cache_creation_tokens: int | None = Field(default=None, ge=0)
    """The DEC-067 rollups: each equals the sum of this run's records' cache fields, absent when
    no record reported the span. `total_input_tokens` stays uncached input only — the three
    input spans are disjoint."""

    estimated_cost: Decimal | None = Field(default=None, ge=0)
    error_summary: str | None = None
    ablations: list[str] = Field(default_factory=list)
    """Ablations the evaluation harness applied; empty for an ordinary run.

    A non-empty list marks the run non-authoritative (DEC-012, DEC-031, DEC-073). Written at run
    creation by the harness — the only caller that constructs an ablated run — and never by
    assessment configuration. Replaying recorded reviewer decisions is not an ablation and
    leaves this empty.
    """

    @property
    def is_authoritative(self) -> bool:
        return not self.ablations

    @model_validator(mode="after")
    def _timestamps_are_ordered(self) -> Self:
        if self.completed_at is not None:
            if self.started_at is None:
                raise ValueError("completed_at is set but started_at is not")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at precedes started_at")
        return self


class ExecutionRecord(DomainModel):
    """One node execution or deterministic processing step (section 27)."""

    id: ExecutionRecordId
    workflow_run_id: WorkflowRunId
    assessment_id: AssessmentId
    node_name: str
    node_version: str
    execution_type: ExecutionType
    prompt_version: str | None = None
    model_name: str | None = None
    input_object_ids: list[str] = Field(default_factory=list)
    output_object_ids: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    status: ExecutionStatus
    retry_number: int = Field(ge=0)
    error_type: str | None = None
    error_message: str | None = None
    """A **safe** error message (section 27): an exception's type and reason, never content.

    Nothing generic can guarantee that, so the rule is on the exceptions rather than here -- the
    errors this codebase raises name identifiers, filenames, and reasons. `ExecutionLedger`
    truncates, and a test asserts that a failure while reading the injection fixture records
    nothing from inside it.
    """

    duration_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    """Uncached input at the full rate. The three input spans are disjoint (DEC-067): cache
    reads and cache creation are never folded in."""

    output_tokens: int | None = Field(default=None, ge=0)
    cache_read_tokens: int | None = Field(default=None, ge=0)
    """Input served from the provider's cache at its discounted rate (DEC-067). Absent means
    "not reported" — the capability record says whether caching was in play."""

    cache_creation_tokens: int | None = Field(default=None, ge=0)
    """Input written into the provider's cache at its premium (DEC-067). Absent means "not
    reported"."""

    estimated_cost: Decimal | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _terminal_records_are_complete(self) -> Self:
        """A record that claims to have finished must say when.

        `completed_at` is optional because a running record has not got one, and that optionality
        is exactly what would let a completed record carry no end time and no duration.
        """
        terminal = {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.RETRIED}
        if self.status in terminal and self.completed_at is None:
            raise ValueError(f"status is {self.status} but completed_at is unset")
        if self.status is ExecutionStatus.RUNNING and self.completed_at is not None:
            raise ValueError("status is running but completed_at is set")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at precedes started_at")
        if self.status is ExecutionStatus.FAILED and not self.error_type:
            raise ValueError("a failed execution must record an error_type")
        return self
