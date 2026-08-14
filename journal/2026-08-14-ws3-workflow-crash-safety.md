# WS3: workflow crash-safety and lifecycle

Third workstream of the robustness program (#444), phase 1, and the last of the correctness trio.
The common shape across its six defects: failure paths the design classifies and records were, in
the implementation, unclassified escapes that left persistent state lying about what happened.

## What changed

**The orchestrator classifies every failure, not two.** `run` wrapped only `_execute`, and only for
`WorkflowError`/`LimitExceededError`. A `StoreError`, a `ValidationError` from a typo'd state key in
`absorb`, a `TransitionError` from `advance`, or an `OSError` from a node escaped the loop and left
`WorkflowRun.status == running` forever, with no classified error and nothing for `_resumable_run`
to find. The whole loop is now wrapped; an unclassified exception becomes
`unexpected_application_failure` (section 11's class for a fault in this application, which no path
produced before), recorded on the run and persisted.

**State is persisted on every transition, and on stop and completion.** `save_state` ran only on a
checkpoint pause, so a failed run's state file lied (frozen at the last pause or absent) and a
completed run's said `paused` forever. It now writes after every phase advance and in
`_stop`/`_complete` (best-effort on the failure path, so a write failure cannot mask the failure it
is recording). The state file is therefore an accurate, resumable record of where the run reached.

**Resuming accepts a failed run.** `resume_assessment` restarts a failed run from the phase it
stopped in via a new `AssessmentState.restarted()` and `ExecutionLedger.reopen()` (which clears the
failed run's `completed_at`/`error_summary` so its row is a running run's again). The phases before
the failure completed, so their objects exist and are not re-run; only the failed phase re-executes.
`_paused_run` became `_resumable_run` (paused *or* failed). This avoids the old behavior where a
failed run could only be re-run from scratch with a new `WorkflowRun`, re-minting everything.

**Re-running a reviewed or approved assessment no longer crashes.** A fresh run moves the assessment
to `pending_review` on pausing, valid only from `draft`. `run_assessment` now returns a
`pending_review` assessment to `draft` (`resume_from_review`) or an `approved` one (`begin_revision`,
which had zero callers) before `start_run`, so the pause no longer raises
`InvalidStatusTransitionError` deep in the loop. `_persist_pause` also writes the state file *after*
its transaction commits, so a rolled-back pause cannot leave a `paused` state file for an unpaused
run.

**Authoritative writes are atomic.** New `infrastructure/filesystem/atomic.py`
(`write_text_atomic`/`write_bytes_atomic`, temp + rename) backs the state file and the retry
debug-output file; the artifact store's `_write` writes to a sibling temporary and hard-links it into
place, which is both atomic and exclusive (the link fails if the name exists, closing the
exists()/write TOCTOU). A crash mid-write leaves the old file or nothing, never a truncation that
would fail its own content hash and wedge the assessment.

**`approve` binds to a recorded run id.** It read the run from the report *filename*
(`rpartition("/")`), which a path separator or filename change would silently break. A new
`Assessment.final_report_run_id` field (data-model.md section 5, registry updated) records the
rendering run, and `approve` uses `repository.find` with the filename only as a fallback for reports
rendered before the field existed.

**`classify_model_failure` cannot `KeyError`.** It defaults an unmapped `FailureReason` to
`unexpected_application_failure` (non-retryable), and a new totality test asserts the map is still
explicitly complete so a new reason fails the test rather than silently taking the default.

## Tests

Added: an unclassified node error fails the run with the right class and a failed run row; failed and
completed runs persist accurate state files; state persists on transition; re-running an abandoned
review and re-running an approved assessment both pause cleanly; a failed run resumes from its phase
reusing the same run; an interrupted artifact write leaves no partial file; the atomic helper
preserves previous contents on a failed rename; the model-failure map is explicitly total. Full
suite green (3676); the ForgeFlow replay reproduces byte-for-byte.

## Open next

WS4 (#445, injection fence and prompt composition) is the next workstream and the first of phase 2
(security). It has no dependency on this one.
