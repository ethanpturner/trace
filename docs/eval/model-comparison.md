# Model comparison — attempt record, incomplete

*Recorded 2026-08-20. Issue #332, which stays open: no live arm completed, and this page says so
rather than presenting a partial table as a comparison.*

The plan was three scenarios (missing-docs, reply-tuner, crypto-wallet) across three profiles:
the #484 sweep's `openai/gpt-5.1` captures as the recorded arm at no new cost, and live
`claude-opus-5` and `claude-sonnet-5` runs through the Anthropic adapter — its first measured
live pipeline runs. Checkpoint decisions replay from the sweep's recorded decision files by
content fingerprint, so the reviewer variable is held constant across arms.

What the attempt measured instead is two defects in the measurement machinery. Both are worth
more than the table would have been; the table remains buyable once they are fixed, and the
money already spent is preserved below as replayable journals.

## What was spent, and where it went

| Attempt | Arm | Died at | Billed | Recoverable |
|---|---|---|---|---|
| 1 | opus / missing-docs | critical review (18 calls) | $9.82 | no — the harness live path does not journal |
| 1 | sonnet / reply-tuner | evidence validation (8 calls) | $4.53 | no — same |
| 2 | opus / missing-docs | critical review | $9.50 | yes — journaled (19 + 18 envelopes preserved) |
| 2 | sonnet / reply-tuner | evidence validation | $6.60 | yes — journaled (11 + 13 envelopes preserved) |

Program total: **$30.45 billed, zero completed arms**, against a $40 stop-loss. The third
attempt was not made: under defect 2 every re-drive re-buys everything past extraction, so one
more attempt could not fit inside the remaining budget, and spending it would have bought the
same defect a third time. The unrun arms (opus/reply-tuner, both crypto-wallet live arms) were
already dropped against the cap before attempt 2.

Attempt 1 was killed by the session harness; attempt 2's first kill was the driver's own
timeout (operator error, $0 — the journals replayed), its second another harness-side kill
mid-run. The kills are an execution-environment problem, not a pipeline one: every run advanced
correctly until killed.

## Defect 1: the harness's live path does not journal

`run_scenario`'s live branch builds its model directly and never wraps it in `JournalingModel` —
DEC-139's protection covers `trace run`/`trace resume` and nothing else. The stability protocol
(DEC-077) and any live comparison arm therefore run the most expensive calls in the system with
no recovery record: attempt 1's $14.35 vanished precisely here. The fix is small (wrap the live
branch the way the CLI's `_run_model` does) and belongs with the harness.

## Defect 2: journal replay diverges at the first post-checkpoint call

Attempt 2 re-drove each scenario from a fresh work root with attempt 1½'s journal named for
replay. Measured behavior: the extraction entry served and was marked spent; the very next call
(threat analysis) missed on `call_sha256`, and per design the whole remaining journal was set
aside — every call from threat analysis onward re-bought live. Same registered inputs, same
pinned `GENERATED_AT`, same recorded checkpoint decisions applied by the same fingerprint
applier, fresh identical stores both times. Something non-deterministic enters the threat
prompt between two runs whose inputs are pinned; reviewer-decision timestamps
(`domain.base.now()` at checkpoint application, possibly surfacing through the DEC-141
settlement sections) are the unverified prime suspect. The rendered requests are not persisted,
so the diff could not be taken post-hoc — the reproduction is cheap and offline with the
deterministic model: run the same scenario twice through the harness's live-decision path and
compare `call_sha256` per call. Until this is fixed, DEC-139's "an interrupted phase re-drives
without re-spending" holds only for runs that die before checkpoint 1.

## What is preserved

- `journals/` — every paid response from the four journaled attempt-runs, in the DEC-139
  envelope shape (`schema`/`usage`/`response`/`call_sha256`), 61 files. Once defect 2 is fixed,
  the arms complete by replay for approximately the cost of their unbought tails.
- `feeds/` — the three `openai/gpt-5.1` labelled feeds (the recorded arm, complete and
  scored): missing-docs 0 matched / 0 missed / 0 spurious at $2.83; reply-tuner 1 matched /
  0 / 0 at $2.97; crypto-wallet 0 / 0 / 1 spurious at $4.87 — coverage 1.0 on all three,
  attribution per DEC-136. These are the sweep's captures re-scored under this comparison's
  labels; their spend was the sweep's.

## Caveats that will apply when the table is bought

n=1 per arm per scenario (variance is DEC-077's, not this page's); `defaulted_decisions`
reported per arm, since a defaulted checkpoint decision grades the arm with a more lenient
reviewer than the sweep's; per-row cost at each provider's published rates with any
interruption loss reported beside the table, never folded into it.
