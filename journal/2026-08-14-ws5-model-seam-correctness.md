# WS5: model seam correctness

Fifth workstream of the robustness program (#446), the second of phase 2. Six defects in the model
seam and retry loop; three were reproduced during exploration. One (truncation token-escalation) is
deferred to WS11 for the reason the issue itself gives.

## What changed

**`build_model` carries the profile object, not its name** (`factory.py`). The plain Anthropic path
returned `AnthropicModel(profile.name)`, which re-resolves the name from the global registry -- so an
ad-hoc profile (built with `replace(...)`) raised `UnknownModelProfileError`, and a
`with_creativity(...)` profile silently reverted to the registry's version. It did not bite only
because every node passes `settings=` explicitly. Now `AnthropicModel(profile)`.

**`CachingModel` returns a `ModelFailure` on recording drift** (`replay.py`). A cache hit ran
`schema.model_validate(recorded)` and raised `pydantic.ValidationError` on a drifted recording,
escaping the orchestrator's attempt loop (which catches only `AttemptFailedError`) and leaving a node
started and never finished. It now returns `ModelFailure(SCHEMA_VALIDATION_FAILURE, raw_output=...)`,
identical to a live schema failure, honouring the seam's no-exceptions contract.

**The cache key covers the system prompt and the provider** (`replay.py`). `CacheKey` hashed the
user `prompt` but nothing about `system` -- where the entire trusted region lives for every agent --
so two calls with an identical user prompt and a different architecture collided, which is a
wrong-conclusion bug by the module's own doctrine. Added `system_hash` and `provider`.

**Context Extraction declares `Creativity.LOW`** (`context_extraction.py`), like the other five
agents, rather than relying on the profile default -- so a default change cannot silently
mis-latitude exactly this one agent, and the execution record reports a decision rather than a
default nobody chose.

**`run_with_retries` classifies anything the attempt raises** (`retry.py`). It caught only
`AttemptFailedError`; a store error, an escaped `ValidationError`, or any other exception bypassed
the loop. A final `except Exception` now stops the run as a non-retryable
`unexpected_application_failure`, and `preserve_failed_output` is guarded (`_preserve_quietly`) so a
failed debug-artifact write cannot mask the real failure. Operator-facing errors --
`MissingSettingError` (unset key), `ResponsesExhaustedError` (missing recording) -- and the
already-classified `WorkflowError`/`LimitExceededError` pass through unchanged, so their clean
messages are preserved rather than re-wrapped with a redundant class prefix.

**Feedback accumulates across attempts, and jitter is injectable** (`retry.py`). Feedback was
overwritten each attempt, so attempt three never saw attempt one's complaint and a field it fixed
was free to regress; it now accumulates (deduplicated). `RetryPolicy.jitter` is an injectable hook
defaulting to identity, so delays stay deterministic for tests and for a single local process while a
concurrent deployment can spread retries.

## Deferred

**Truncation token-escalation** (`OUTPUT_TRUNCATED`): re-sending with the same `max_output_tokens`
is a repetition, and escalating requires each of the six agent attempt loops to raise its output
ceiling on retry. The issue itself flags this as landing with WS11's attempt-loop consolidation,
where the six loops become one; doing it here would mean six near-identical edits about to be merged.
The default ceiling is already 64,000 (raised in #324), so live truncation is rare in the meantime.

## Tests

The `build_model` ad-hoc and modified-creativity reproductions; a drifted recording returns a
failure not a raise; two systems (and two providers) with one user prompt get distinct keys and the
`CachingModel` keys on the system; Context Extraction declares LOW creativity; an unexpected
exception stops the run as an application fault while a classified `WorkflowError` is not re-wrapped;
feedback accumulates; jitter is injectable and off by default. Full suite green (3695); the ForgeFlow
replay reproduces byte-for-byte.

## Open next

WS6 (#447, CLI error contract) begins phase 3 and carries a decision-log entry for the exit-code
change. No dependency on this one.
