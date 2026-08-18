"""`ReviewSession`: when a checkpoint's review was first put in front of a person.

`data-model.md` section 25a is authoritative for the fields. DEC-117 is the decision: the two
human checkpoints are the workflow's only unmeasured phases, and the pipeline cannot say how
long a review took because nothing records when it began. A `ReviewerDecision` carries the
moment a decision landed; this object carries the moment the reviewer started, and the
difference between the two is the measurement.

**The session starts when a review command renders the checkpoint's material.** `trace context
review` and `trace findings review` record one of these rows on entry, whichever path the
invocation takes — export, apply, or flags. The measurement is wall clock from that moment to
the checkpoint's conclusion; active attention is not measurable from a command line and is not
pretended to (DEC-117).

**A harness-answered checkpoint has no session.** The evaluation harness and the stability
protocol decide checkpoints programmatically without the review commands, so no row is written
and the timing metrics are absent — a dash, never a fabricated zero (the DEC-092 discipline).

**`checkpoint` is a closed vocabulary**, like `DataFlow.direction` and unlike the `*_type`
fields DEC-036 opens: there are exactly two structural checkpoints (DEC-005), and a session at
an unknown one would be a measurement of nothing.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import (
    AssessmentId,
    ReviewSessionId,
    WorkflowRunId,
)

__all__ = ["ReviewCheckpoint", "ReviewSession"]


class ReviewCheckpoint(StrEnum):
    """The two structural checkpoints (DEC-005). Closed: there is no third."""

    CONTEXT_APPROVAL = "context_approval"
    FINDING_APPROVAL = "finding_approval"


class ReviewSession(DomainModel):
    """One rendering of a checkpoint's review material to a person (section 25a)."""

    id: ReviewSessionId
    assessment_id: AssessmentId

    checkpoint: ReviewCheckpoint
    """Which structural checkpoint the session belongs to."""

    reviewer_id: str | None = None
    """A configured local string, not an authenticated identity (DEC-023)."""

    created_at: datetime
    """When the review command rendered the material. The session's start."""

    workflow_run_id: WorkflowRunId | None = None
