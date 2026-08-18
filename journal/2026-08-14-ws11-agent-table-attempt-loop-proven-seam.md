# 2026-08-14 — WS11: one agent table, one attempt loop, a proven seam (#452)

Extensibility consolidations. The theme was facts and code that must stay in agreement written in
several places with nothing asserting they agree — and one instance (context extraction's creativity)
had already drifted. This delivers all three of the issue's title clauses.

## One agent table

`src/trace_ai/infrastructure/model/agents.py` holds `AGENTS`, one `AgentSpec` per model-assisted
agent carrying `(name, schema, prompt_id, prompt_version, creativity)`. The three registries that
restated pieces of this now derive from it: `AGENT_BY_SCHEMA` (factory), `RESPONSE_SCHEMAS`
(recorded), `AGENT_NAMES` (profiles). Each node reads its creativity from the table via `spec_for`
rather than declaring `Creativity.LOW`/`MODERATE` inline — which is exactly how this value drifted
before. `test_agents.py` pins that the derivations match, that the node `PROMPT_ID`/`PROMPT_VERSION`
constants agree with the table, and that the table holds exactly the six agents DEC-030 caps — so a
seventh, or a disagreeing node, is a red check rather than a silent divergence.

## One attempt loop

`src/trace_ai/workflow/model_call.py` is the ~30-line body that every node ran around
`model.generate`, once: the budget projection and charge, the one attempt, the
`ModelFailure` → `AttemptFailedError` translation, the impossible-third-arm guard, the usage append,
and the condition-metadata copy. All six nodes now call `call_model` and `with_retry_feedback`; what
stays in each node is what genuinely differs — the retry instruction sentence, the schema, the system
region, and the domain validation of the returned object. The helper also copies `schema_grammar`
onto the execution record alongside `effort` and `creativity`, which no node did: a run where every
agent lost server-side schema enforcement was previously indistinguishable from one where none did.
The `context.model is None` guard the six nodes expressed as `# type: ignore[union-attr]` moved into
the helper as a classified fault. `context_extraction`'s now-dead `_projected_cost`/`_projected_cost_for`
were removed.

## A proven seam

`src/trace_ai/infrastructure/model/adapter_support.py` holds the three provider-neutral obligations a
second adapter would otherwise have to reimplement: `error_locations` (the security-sensitive
validation-error rendering that masks model-authored keys and caps at 20), `json_candidate` (fence
stripping before validation), and `classify_http_error` (the 500-boundary retryability rule). The
anthropic adapter now imports them; its exception ladder keeps the provider-specific types and defers
the status-code half to `classify_http_error`. `test_adapter_conformance.py` is the behavioural
contract — parametrized so a second adapter is one row — asserting an adapter never raises on a
provider condition, always returns usage with a non-negative duration, preserves `raw_output` on a
schema failure, keeps model text out of the failure message, and classifies retryability by the
ladder. The `@runtime_checkable` Protocol's `settings` was tightened to match its implementations
(`GenerationSettings | None = None`), and `OverlayRoutingModel.capabilities` now returns
`frozenset[ModelCapability]` rather than `frozenset[Any]`; the two outlier `generate` signatures
(DeterministicModel, OverlayRoutingModel) and the capture script were aligned, so the drift a
signature-blind `@runtime_checkable` was hiding is gone.

## Smaller gaps

- Shared blocks now raise on a duplicate stem, symmetric with the duplicate-`(id, version)` refusal
  — last-write-wins would silently change the composed text of every prompt including the block.
- `test_schema_export_size.py` pins a ceiling on each schema's `transform_schema` export, so a schema
  that grows toward the provider's grammar-too-large limit trips CI before the adapter silently
  degrades to `schema_grammar: too_large_omitted`.

## Deferred

Two of the issue's smaller gaps are held for a follow-up, noted on #452:

- **Pick one overlay-resolution path.** Two exist — the driver's `profile.for_agent(agent)` per node
  and `OverlayRoutingModel`'s schema routing — and neither is exercised, because no shipped profile
  carries an overlay. They resolve different things (the node's settings/limits vs the routed
  adapter), so collapsing them needs care to not break the untested overlay feature, for low value.
- **A second prompt hash over the pre-substitution composition.** DEC-019's stated purpose wants a
  hash of the template, not the fully-substituted request; adding it touches `traces/` and the
  stored prompt identity, which is replay-adjacent, so it belongs in its own change.

No decision-log entry: the agent-table test strengthens the DEC-030 cap rather than touching it, and
nothing here changes decided surface.

## Verification

`ruff`, `ruff format`, `mypy` (strict, 305 files), `pre-commit run --all-files` clean. Full suite
3797 passed, coverage 85.30% over the floor. The ForgeFlow replay canary reproduces byte-for-byte
(`sha256:63b3a83a…`) — the attempt-loop extraction and creativity-from-table change are behaviour-
preserving. New suites: `test_agents`, `test_model_call`, `test_adapter_support`,
`test_adapter_conformance`, `test_schema_export_size`, plus the stem-collision case.

## Open next

The two deferred #452 gaps above; the deferred #451 caching + ranking (after #461); and follow-up
#455.
