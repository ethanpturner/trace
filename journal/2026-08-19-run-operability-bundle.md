# 2026-08-19 — The run-operability bundle, and a prioritization pass over the whole backlog

## What changed

Three features landed on develop in one delivery wave, all runtime-side, all offline:

- **`trace runs repair` (DEC-137, #613, PR #625).** The orphaned-run hole found during the sweep
  pilot is closed: a `running` run whose process was killed can be marked failed by an operator's
  explicit assertion, through the ledger's own `complete(error_summary=...)` mechanics. Never
  automatic — a running run that looks stale may be a slow provider call, so the operator asserts
  and the summary names the external kill. Without `--force` the verb prints the run's facts and
  changes nothing.
- **Phase narration and `trace runs status` (DEC-138, #622, PR #626).** The orchestrator gained a
  notify-only observer: one stderr line per phase entered — phase number against the fourteen,
  model calls so far, running cost from the ledger — wired into `run`, `resume`, and the three
  capture stages. Beside it, `trace runs status` reads what `save_state` and the execution records
  already persist, with a `--json` view under the DEC-096 envelope. Derived, never stored; the
  observer holds no authority and its failure cannot touch the run.
- **The live response journal (DEC-139, #623, PR #627).** Ordinary `run` and `resume` now journal
  every live model response into the assessment's `traces/`, shaped exactly as the recorded-response
  loader reads them back. Replay is an operator's assertion (`--replay-journal`, mirroring
  `--response`), a served entry is marked spent so a deliberate retry cannot reuse the conclusion
  it meant to re-request, and a request-hash mismatch sets the journal aside and continues live —
  divergence spends money rather than serving a stale answer.

## Why this, why now

The session started as a prioritization pass: six parallel analyses over the backlog — product
docs, decision log, code, evaluation state, issue tracker, operator experience — converged on the
same reading. The pipeline is complete; the open front is measured evidence, and the issue tracker
is a dependency graph with the budget-parked live sweep (#484) at its root.

The bundle jumped the queue on firsthand testimony: driving the pipeline from a coordinating
session, the operator cannot see where a run is, and a machine going to sleep mid-phase forces a
restart from position. Those two complaints decomposed into exactly three mechanisms — no progress
seam, no journal of paid calls inside a phase, and no sanctioned repair for the orphan the kill
leaves behind. #613 was already filed from the pilot; #622 and #623 were filed to complete the
set, and all three were delivered because the sweep is twelve more forty-minute billable runs
driven exactly that way. Each interrupted capture is now a resume instead of a loss.

## How it was delivered

Three forks in isolated worktrees, one issue each, PRs to develop, merged in issue order. The
decision-log contiguity guard forces numbers to land in merge order, so each branch numbered its
entry DEC-137 provisionally and the second and third renumbered at merge time — the
renumber-at-final-push protocol from the last wave, exercised twice without incident. The #623
branch's squash commit subject on develop still reads "DEC-137" — the PR title edit raced the
merge — which is a cosmetic blemish in history only; the log itself carries DEC-139 and every
in-tree reference was swept.

## Decisions

DEC-137, DEC-138, DEC-139, each recording its rejected alternatives: the staleness heuristic and
heartbeat inference for repair; the heartbeat file and node-side narration for progress; automatic
journal replay and pop-past-mismatch serving for the journal. The common thread across all three
is the corpus's existing posture applied to operations: state is read where it already lives,
nothing gains authority it did not have, and anything that changes a run's story is an operator's
explicit act.

## Open next

- Unpark #484: twelve scenarios at the measured ~$5.25 each, now with narration, status, repair,
  and re-drive behind every capture. Keyed spend still needs the go-ahead with the number in view.
- The rest of the prioritized fifteen, headed by the measurement backbone: truth-set
  reconciliation (#589) before further sweep spend, live baselines, coverage enforcement (#588),
  and the second annotation set (#565), which has the longest external lead time and should start
  in parallel.
