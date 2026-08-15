# WS7: evaluation harness integrity

Seventh workstream of the robustness program (#448), phase 3. Five of its six defects landed here;
the sixth — the recorded-response envelope — is split into #461 because it is a 166-file re-capture
event that changes the `DeterministicModel` contract and pairs with WS10/WS11, as the issue notes.

## What changed

**Finding-decision matching fails loudly on a count mismatch, and matches by identifier where it
can.** `_apply_finding_decisions` zipped the recorded decisions to the produced findings with
`strict=False` — so a run that produced four findings where the recording held five silently scored
a truth set the run no longer described, and a reordering landed a decision on the wrong finding. It
now raises `HarnessError` naming both counts on a mismatch, and matches by the recorded identifier
when every one resolves (the single-scenario case, where a fresh store re-mints the same ids, so
order cannot mislead); the documented positional fallback stands only for the shared-store `--all`
sweep, where the run's identifiers differ from the recording's.

**The scenario registry is validated.** `load_registry` raw-indexed `entry["slug"]` on
`yaml.safe_load` output, so a typo in `scenarios.yaml` was a `KeyError` traceback. It now parses
into a pydantic model with `extra="forbid"` — a misspelled key is named with its entry index — and
refuses an unsupported `registry_version` rather than misparsing a future layout as `1.0`. The CLI
validates `--condition` once before the loop, instead of twelve identical `HarnessError`s on `--all`.

**`--all --diff-against` no longer aborts the sweep on one missing prior feed.** The `diff_feeds`
call is wrapped in the per-scenario `try`, counted as that scenario's failure, and the sweep
continues — matching how a `HarnessError` was already handled.

**Temp directories are cleaned up.** Every `trace evaluate` path (`--all`, ablation set, stability)
and the four build/replay scripts used `mkdtemp` with no cleanup; they now use `TemporaryDirectory`
when no `--work-root` is named, so a `--all` run no longer leaves twelve stores behind and the CI
scorecard scripts leave nothing. Stability's summary — a deliverable — moves to `--results-root` or
the current directory so it is not deleted with the throwaway store.

**One deterministic stamp.** Five scripts and the harness each held a `GENERATED_AT`, and they had
drifted: the harness stamped `2026-08-11` while `report-hash.txt` was pinned against the replay
script's `2026-08-14`. A single `DETERMINISTIC_STAMP` in `services/evaluation/stamps.py` is imported
by all six (a sixth, `capture_forgeflow.py`, the issue did not list). The harness moves to `08-14`,
so it now renders the ForgeFlow report to the same hash the replay script pins; the committed
scorecard, comparison, and ablation pages are unchanged (they were already rendered at `08-14`), and
the ForgeFlow replay reproduces byte-for-byte.

## Deferred (#461)

The recorded-response envelope — named-schema validation plus a non-zero offline ledger from
recorded usage — is a corpus-wide re-capture event (166 recordings, a `DeterministicModel` contract
change, committed-artifact re-pins). The issue ties it to WS10 and WS11; filed as #461 to land as a
coherent unit there rather than a large re-pin buried in this diff.

## Tests

A decision-count mismatch raises `HarnessError` naming both counts (via a copied ForgeFlow scenario
with a sixth decision); a misspelled or missing registry key and an unsupported `registry_version`
raise `RegistryError`; `trace evaluate` leaves no temporary work root; `--diff-against` a missing
prior is a message, not a traceback, and the scenario's metrics still print. Full suite green (3708);
scorecard/comparison/ablation `--check` all current; ForgeFlow replay byte-for-byte.

## Open next

WS8 (#449, store query surface and evidence index) begins phase 4 (scalability); it carries a
decision-log entry for the new `purge` command.
