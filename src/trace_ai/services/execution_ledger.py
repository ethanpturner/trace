"""Recording what ran: a context manager per node execution.

`current-architecture.md` section 5.17 makes local audit records the authoritative execution record.
This writes them, for the two deterministic nodes that exist today, so the first model-assisted node
finds a ledger rather than inventing one.

**The record is written whether the node succeeds or not.** A ledger that only records successes
answers "what happened" with a list of things that worked, which is the opposite of what an audit
record is for. On failure it stamps the terminal status, the error type, and a safe message.

**"Safe" is a property of the exceptions, not of this module.** Section 27 calls `error_message` a
safe error message, and nothing generic can inspect a string and know whether a document's contents
are in it. The rule is therefore upstream: the errors this codebase raises name identifiers,
filenames, and reasons rather than content. This module truncates and records the exception type
separately, so a message that grew long or unexpected is bounded rather than stored whole — and a
test asserts that a failure while reading the injection fixture records nothing from inside it.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from trace_ai.domain.base import now
from trace_ai.domain.execution import (
    ExecutionRecord,
    ExecutionStatus,
    ExecutionType,
    RunStatus,
    WorkflowRun,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from datetime import datetime

    from trace_ai.infrastructure.model.seam import ModelUsage
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["MAXIMUM_ERROR_MESSAGE", "Execution", "ExecutionLedger", "start_run"]

# Long enough for a parser's complaint, short enough that an unexpected message cannot become a
# storage problem or smuggle a document into a row.
MAXIMUM_ERROR_MESSAGE = 500


@dataclass(slots=True)
class Execution:
    """The handle a node uses to describe what it did while it is doing it."""

    node_name: str
    started_at: datetime
    input_object_ids: list[str] = field(default_factory=list)
    output_object_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    prompt_version: str | None = None
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: Decimal = field(default_factory=lambda: Decimal(0))

    def produced(self, *object_ids: str) -> None:
        """Record objects this execution created or modified."""
        self.output_object_ids.extend(object_ids)

    def consumed(self, *object_ids: str) -> None:
        self.input_object_ids.extend(object_ids)

    def record_usage(self, usage: ModelUsage) -> None:
        """Add one model call's tokens and cost to this execution.

        Accumulated rather than assigned: a node that makes two calls in one execution has one
        record, and section 27's token fields are that record's totals. The model name comes from
        the usage so it is the model that actually answered rather than the one that was asked
        for -- a provider that served a fallback would otherwise be invisible.
        """
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.estimated_cost += usage.estimated_cost
        self.model_name = usage.model


def safe_message(error: BaseException) -> str:
    """A bounded rendering of an exception, for `ExecutionRecord.error_message`."""
    text = str(error).strip() or error.__class__.__name__
    if len(text) > MAXIMUM_ERROR_MESSAGE:
        return text[: MAXIMUM_ERROR_MESSAGE - 1] + "…"
    return text


def start_run(
    handle: AssessmentHandle,
    *,
    workflow_version: str,
    model_profile: str,
    prompt_versions: dict[str, str] | None = None,
) -> WorkflowRun:
    """Open a workflow run for this assessment.

    `total_model_calls` starts at zero and stays there for a run that calls no model, which is
    every run in this milestone. It is the correct value, not a placeholder.
    """
    repository = handle.objects
    with repository.transaction():
        run = WorkflowRun(
            id=repository.allocate("run"),
            assessment_id=handle.assessment_id,
            workflow_version=workflow_version,
            status=RunStatus.RUNNING,
            started_at=now(),
            model_profile=model_profile,
            prompt_versions=prompt_versions or {},
            total_model_calls=0,
        )
        repository.save(run)
    return run


class ExecutionLedger:
    """Writes execution records for one workflow run."""

    def __init__(self, handle: AssessmentHandle, run: WorkflowRun) -> None:
        if run.assessment_id != handle.assessment_id:
            raise ValueError(f"{run.id} belongs to {run.assessment_id}, not {handle.assessment_id}")
        self.handle = handle
        self.run = run

    @contextmanager
    def record(
        self,
        node_name: str,
        *,
        node_version: str,
        execution_type: ExecutionType = ExecutionType.DETERMINISTIC,
        retry_number: int = 0,
        consumes: Sequence[str] = (),
    ) -> Iterator[Execution]:
        """Record one node execution, whether it succeeds or raises.

        The exception propagates. A ledger that swallowed it would turn an audit record into an
        error handler, and the caller would carry on with a failure recorded and nothing raised.
        """
        started = now()
        execution = Execution(
            node_name=node_name, started_at=started, input_object_ids=list(consumes)
        )
        try:
            yield execution
        except BaseException as error:
            self._write(
                execution,
                node_version=node_version,
                execution_type=execution_type,
                retry_number=retry_number,
                status=ExecutionStatus.FAILED,
                error_type=type(error).__name__,
                error_message=safe_message(error),
            )
            raise
        else:
            self._write(
                execution,
                node_version=node_version,
                execution_type=execution_type,
                retry_number=retry_number,
                status=ExecutionStatus.COMPLETED,
            )

    def _write(
        self,
        execution: Execution,
        *,
        node_version: str,
        execution_type: ExecutionType,
        retry_number: int,
        status: ExecutionStatus,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> ExecutionRecord:
        completed = now()
        repository = self.handle.objects
        with repository.transaction():
            record = ExecutionRecord(
                id=repository.allocate("exe"),
                workflow_run_id=self.run.id,
                assessment_id=self.run.assessment_id,
                node_name=execution.node_name,
                node_version=node_version,
                execution_type=execution_type,
                input_object_ids=list(execution.input_object_ids),
                output_object_ids=list(execution.output_object_ids),
                started_at=execution.started_at,
                completed_at=completed,
                status=status,
                retry_number=retry_number,
                error_type=error_type,
                error_message=error_message,
                duration_ms=max(int((completed - execution.started_at).total_seconds() * 1000), 0),
                prompt_version=execution.prompt_version,
                model_name=execution.model_name,
                input_tokens=execution.input_tokens or None,
                output_tokens=execution.output_tokens or None,
                estimated_cost=execution.estimated_cost or None,
                metadata=dict(execution.metadata),
            )
            repository.save(record)
        return record

    def records(self) -> list[ExecutionRecord]:
        """This run's execution records, in identifier order."""
        return [
            record
            for record in self.handle.objects.list(ExecutionRecord)
            if record.workflow_run_id == self.run.id
        ]

    def counters(self) -> dict[str, object]:
        """The section 26 counters, computed from the records this run wrote.

        Computed rather than incremented as the run goes, so they are a measurement of what was
        written rather than a parallel tally that can drift from it. Shared by `complete` and
        `pause`: a reviewer at a checkpoint asking what the run cost is asking the same question a
        finished run answers, and two implementations would eventually give two answers.
        """
        records = self.records()
        input_tokens = sum(record.input_tokens or 0 for record in records)
        output_tokens = sum(record.output_tokens or 0 for record in records)
        cost = sum((record.estimated_cost or Decimal(0) for record in records), Decimal(0))
        return {
            "total_model_calls": sum(
                1 for record in records if record.execution_type is ExecutionType.MODEL
            ),
            "total_input_tokens": input_tokens or None,
            "total_output_tokens": output_tokens or None,
            "estimated_cost": cost or None,
        }

    def complete(self, *, error_summary: str | None = None) -> WorkflowRun:
        """Close the run. `failed` when a summary is given, `completed` otherwise."""
        repository = self.handle.objects
        updated = WorkflowRun.model_validate(
            self.run.model_dump()
            | self.counters()
            | {
                "status": RunStatus.FAILED if error_summary else RunStatus.COMPLETED,
                "completed_at": now(),
                "error_summary": error_summary,
                "current_node": None,
            }
        )
        with repository.transaction():
            repository.save(updated)
        self.run = updated
        return updated

    def pause(self, *, current_node: str) -> WorkflowRun:
        """Mark the run paused at `current_node` (DEC-017).

        A pause is not a completion: `completed_at` stays unset, and the counters keep accumulating
        when the run resumes. What makes the pause self-describing is this field plus the state's
        `pending_human_review` block.

        The counters are brought up to date here as well as at completion. A paused run is one a
        person is looking at, and "what has this cost so far" is the question they ask; leaving the
        counters at zero until the run finished would answer it wrongly rather than not at all.
        """
        repository = self.handle.objects
        updated = WorkflowRun.model_validate(
            self.run.model_dump()
            | self.counters()
            | {"status": RunStatus.PAUSED, "current_node": current_node}
        )
        with repository.transaction():
            repository.save(updated)
        self.run = updated
        return updated
