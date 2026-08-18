# 2026-08-14 — WS10 part 1: one character budget for every input package (#451)

WS10 has three cost levers: prompt caching, unified budgets, and ranked evidence selection. This
session delivers the middle one and defers the other two for a reason that only became clear on
reading the code — both change the composed prompt, and the recorded runs the evaluation harness
replays cannot absorb a prompt change without being re-captured.

## What changed: the unified budget

Before this, the five model-input packages counted their input five different ways. Context and
threats charged the untrusted excerpts against the whole `max_input_characters` and dropped whatever
sorted last; threats first subtracted an estimate that covered only the architecture JSON. Evidence
validation and critique counted nothing and rendered every cited excerpt unconditionally. Mapping
measured the whole payload after assembly and hard-raised with no degradation. And *none* charged
the response-format schema the prompt teaches — a per-agent export of one to twenty-plus thousand
characters, substituted straight into the prompt body, entirely uncounted against a budget it plainly
consumes.

`src/trace_ai/services/budget.py` is now the one place that accounting lives:

- `schema_overhead(schema)` prices the schema export (provider-neutral, via `model_json_schema` —
  no reach behind the model seam).
- `fill_untrusted(rendered, *, profile, overhead_characters)` charges the trusted region and the
  schema as fixed overhead, greedy-fills the untrusted excerpts against what is left, and returns a
  `BudgetOutcome` that names what it shed. It never raises: whether a shed excerpt is tolerable
  degradation or a stop condition is the caller's to decide.

All five packages call it. Evidence validation and critique gain graceful degradation and an
`excluded_evidence_ids` field they never had. Mapping now sheds *evidence* before raising, and
raises `PayloadTooLargeError` only when the irreducible part — the catalog, threat, and schema, none
of which it may drop (DEC-024) — will not fit; its rich DEC-024 message stays where it was, because
the mapping stop condition is genuinely different from the others' exclusion. Every package records
the same budget keys (`characters`, `overhead_characters`, `residual_characters`, `budget_characters`,
`trusted_characters`, `evidence_included`, `evidence_excluded`), so their accounting finally reads
the same way.

The fill preserves the caller's excerpt order, so a package that does not overflow renders exactly
what it rendered before. That is the property that keeps the ForgeFlow replay canary byte-for-byte:
the demo corpus fits well within the (now correctly reduced) residual, so nothing is shed and no
prompt moves.

## Why caching and ranking are deferred

Both were in scope for #451 and both are held for a focused follow-up, sequenced after the
recorded-response re-capture (#461):

- **Prompt caching** cannot be done correctly without changing the composed prompt. The stated
  win — the requirements catalog cached across the mapping node's per-threat calls — needs the
  stable content (catalog, architecture) to be a cacheable *prefix* with the per-threat content
  after it, which means reordering the trusted region and giving the model seam a way to place a
  cache breakpoint mid-`system`. Caching the whole `system` block instead is not a safe shortcut:
  for mapping the `system` block *includes* the threat and so varies every call, and caching a
  block that changes every call writes a new cache entry each time and reads none — a net cost, not
  a saving. And the offline cache-token accounting the issue's test needs (`cache_read_tokens`
  non-zero on the second identical call) depends on the recorded-response envelope from #461, which
  is not built. The adapter already declares `PROMPT_CACHING`; making it real is a genuine seam
  change, not a one-liner, and belongs in its own PR.

- **Ranked evidence selection** reorders the prompt blocks (structured-input-named documents first),
  which changes every recorded prompt and breaks the replay the same way. A replay-safe variant
  exists — rank to decide *inclusion* but emit survivors in the original order — but its benefit only
  appears under overflow, and "structured-input-named first" needs the structured-input document
  list threaded into three packages that do not currently receive it. Better done alongside the
  caching change, after #461 makes a prompt move affordable.

No decision-log entry: charging overhead the budget always consumed is a correctness fix, not a
reversal, and mapping shedding evidence (never the catalog) is consistent with DEC-024, which is
about the catalog specifically.

## Verification

`ruff`, `ruff format`, `mypy` (strict, 297 files), `pre-commit run --all-files` all clean. Full
suite 3749 passed, coverage 85.15% over the 80 floor. `test_budget.py` pins the schema-overhead
accounting, order preservation, and overflow shedding; `test_evidence_validation_node.py` gains a
tiny-budget degradation test for a package that previously enforced nothing. The ForgeFlow replay
canary reproduces byte-for-byte (`sha256:63b3a83a…`).

## Open next

Caching + ranking (the rest of #451), sequenced after #461. Then WS11 (#452), and follow-up #455.
