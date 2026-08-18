# 2026-08-15 — Recorded-response envelope (#461)

Split out of WS7 (#448), which landed its other five fixes without touching the recording format.
This is the format change: the corpus-wide re-capture the issue named, done as far as it honestly can
be without a measured live run.

## The two problems

1. **The schema was inferred structurally.** `parse_recorded_response` tried all six proposal
   schemas and required exactly one match, even though the agent is in the filename. Adding a
   required field to any proposal failed every recording at once with no per-field detail, and
   relaxing a field could make a recording match two schemas.
2. **Offline runs produced an all-zero ledger.** Recordings were bare proposal JSON with no usage,
   so `DeterministicModel` reported zeros and the `Budget` cost path never ran offline.

## What changed

Recordings are now an envelope — `{"schema": <ProposalName>, "usage": {...}, "response": {...}}`:

- `recorded.py` validates the `response` against the schema its `schema` names and reports pydantic's
  field-level errors on a mismatch. A bare proposal (no envelope) still works, via the old structural
  inference kept as a legacy fallback.
- `load_recorded_responses` now returns `RecordedResponse(response, usage)`, and `DeterministicModel`
  replays the recorded `usage` when the envelope carries it — so the offline ledger and the `Budget`
  cost path run on real numbers whenever a recording has them. The queue accepts a bare proposal, a
  `ModelFailure`, or a `RecordedResponse`, so every existing caller and test is unchanged.
- `build_model(responses=...)` carries the wider type through to the fake.
- `scripts/capture_forgeflow.py` writes envelopes with the captured usage — a live capture is the one
  place real usage exists, and this is where it is written.
- `scripts/migrate_recordings.py` wrapped the 158 agent recordings in envelopes (idempotent, with a
  `--check` mode). Baseline recordings are read through a different path and are out of scope.

## The honest limit on usage

The issue's headline — a non-zero offline ledger from recorded usage — is delivered as *plumbing*,
not as populated corpus values. The migrated recordings carry **no** `usage`, because no live run has
ever been measured (`CLAUDE.md`), and the scorecard's committed stance is explicit: "a dash is
unmeasured, never zero." Writing synthetic usage would put fabricated cost into committed artifacts;
this change refuses that. So the offline ledger stays at zero and the scorecard cost column stays a
dash — the honest state — until a keyed live capture writes real usage into the envelopes, which the
capture script now does. `test_recorded.py` proves the replay-usage path at the unit level (an
envelope carrying usage yields a non-zero ledger), and the corpus guard test keeps every committed
recording a valid envelope. This was the user's call between "plumbing now, values later" and a
computed-estimate alternative; they chose plumbing-now.

## Verification

`ruff` / `ruff format` / `mypy` (strict, 307 files) / `pre-commit` clean. Full suite 3804 passed,
coverage 84.90%. The ForgeFlow replay canary is byte-for-byte unchanged (`sha256:63b3a83a…`) — the
envelope changes the file format, not the proposals — and `build_scorecard/comparison/ablation
--check` all report current, so no committed artifact moved. `migrate_recordings.py --check` reports
every agent recording is an envelope.

## Open next

Populating real per-recording usage is a keyed live-capture step the plumbing now supports. Remaining
program tail: the deferred #451 caching + ranking (now unblocked by this envelope), and the two minor
#452 gaps.
