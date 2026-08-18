"""Recording when a checkpoint review began, and deriving how long it took (DEC-117).

The recorder is called by the two review commands and nothing else. The harness and the
stability protocol decide checkpoints programmatically without passing through here, so a
replayed or protocol-driven run has no sessions and the timing metrics stay absent — the
DEC-092 dash discipline: unmeasured is never zero.

The derivation pairs the **earliest** session at a checkpoint with the checkpoint's conclusion.
Earliest, because a reviewer may render the material several times — export, look again, apply —
and the measurement DEC-117 defines is wall clock from the first rendering to the conclusion.
Per-object timings are deliberately not derived: a batch invocation writes many decisions in one
moment, and per-object numbers computed from shared timestamps would be fabricated precision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.domain.base import now
from trace_ai.domain.review_session import ReviewCheckpoint, ReviewSession

if TYPE_CHECKING:
    from datetime import datetime

    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["record_review_session", "review_seconds"]


def record_review_session(
    handle: AssessmentHandle,
    checkpoint: ReviewCheckpoint,
    *,
    reviewer_id: str | None,
    workflow_run_id: str | None,
) -> ReviewSession:
    """Record that a checkpoint's review material was rendered to a person, now."""
    with handle.objects.transaction():
        session = ReviewSession.model_validate(
            {
                "id": handle.objects.allocate("rvs"),
                "assessment_id": handle.assessment_id,
                "checkpoint": checkpoint,
                "reviewer_id": reviewer_id,
                "created_at": now(),
                "workflow_run_id": workflow_run_id,
            }
        )
        handle.objects.save(session)
    return session


def review_seconds(
    handle: AssessmentHandle,
    checkpoint: ReviewCheckpoint,
    concluded_at: datetime,
) -> float | None:
    """Wall-clock seconds from the checkpoint's first session to its conclusion.

    `None` when no session precedes the conclusion — a harness-decided checkpoint, or a
    conclusion recorded before the instrument existed. Sessions after the conclusion belong to
    a later revision cycle and do not measure this one.
    """
    starts = [
        session.created_at
        for session in handle.objects.list(ReviewSession)
        if session.checkpoint is checkpoint and session.created_at <= concluded_at
    ]
    if not starts:
        return None
    return (concluded_at - min(starts)).total_seconds()
