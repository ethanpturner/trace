# 2026-08-15 — Prompt caching (#451, part 2 — closes it)

The last of #451's three levers (the unified budget was WS10; ranked evidence was part 1). The
adapter declared `PROMPT_CACHING` in `_CAPABILITIES` and never sent a `cache_control`; this makes the
declared capability real and prices it, so DEC-067's cost fields describe caching that happened.

## The change

The seam gains an optional `cache_prefix: str | None` on `generate` — a provider-neutral hint
(DEC-014), the stable leading span of the prompt an adapter may mark for reuse. It threads through
`call_model`, and every node computes it once with `cache_prefix_of(composed.text, <source>)`: every
agent prompt ends with its per-call source content (the fenced excerpts, or the report input — the
`input.source_content`/`input.report` marker is the last line of every template), so the span before
it — shared blocks, body template, and the schema export — is what is identical across a node's
calls and its retries.

- The Anthropic adapter splits the user message at the prefix: the stable span carries
  `cache_control: {"type": "ephemeral"}`, the per-call remainder does not. A `cache_prefix` that is
  not actually a prefix (stale) degrades to one plain block, never a wrong split.
- `capabilities_used` reports `PROMPT_CACHING` only when the response's usage shows a served or
  written cache span, so the result records caching as *used* rather than merely available.
- Every other `StructuredModel` — the deterministic fake, the overlay router, the caching wrapper,
  the capture models — accepts and forwards the hint; the fake reaches no provider and ignores it,
  and the replay cache key is unchanged because the hint does not change the prompt text.

## What it does and does not capture

The win is the span cached across a node's repeated calls (the mapping node's ~15 per-threat calls
reuse their shared blocks and schema export; every node's retries reuse the whole prefix). It does
**not** capture the mapping catalog: the catalog sits in the `system` region, which for mapping also
carries the per-threat content and so varies per call — caching a varying block would write a new
entry each call and read none, a net cost, so system is left uncached. Capturing the catalog would
mean splitting mapping's trusted region so the catalog is a stable cached prefix; that is a focused
follow-up, noted, not attempted here.

Offline this changes nothing observable: `DeterministicModel` ignores the hint and reports zero cache
tokens, so `PROMPT_CACHING` never appears offline, the scorecard cost/token columns are unchanged,
and the ForgeFlow replay canary is byte-for-byte identical. The behaviour is exercised against a
provider, which has not been measured — so the tests assert the request shape (a stub client
confirms the prefix is split and marked ephemeral, and a stale prefix is ignored) and the accounting
(`PROMPT_CACHING` reported iff the response serves cache tokens).

No decision-log entry: the capability was already declared (DEC-014), section 30 already sanctions
caching, and `cache_prefix` is a provider-neutral hint rather than a new decided surface.

## Verification

`ruff` / `ruff format` / `mypy` (strict, 307 files) / `pre-commit` clean. Full suite 3817 passed,
coverage 84.94%. Replay canary byte-for-byte (`sha256:63b3a83a…`); scorecard/comparison/ablation
checks current. New tests: `cache_prefix_of` (prefix before source; stable across retry feedback;
declines on empty/absent suffix), the adapter request shape (split-and-mark, plain when absent,
ignored when stale), and `PROMPT_CACHING` accounting.

## Open next

#451 is closed with this. Remaining program tail: the two minor #452 gaps (overlay-path pick-one;
second pre-substitution prompt hash), and the mapping-catalog cache-prefix optimization noted above.
