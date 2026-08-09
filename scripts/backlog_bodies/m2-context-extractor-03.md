## Context

The Context Extraction Agent is designed to receive source chunks, document metadata, and existing structured input, and nothing else (`docs/architecture/agent-design.md` section 23). Section 23 gives the reason directly: a smaller input reduces token use, accidental cross-contamination, irrelevant reasoning, prompt-injection exposure, cost, and latency. Section 22 adds that evidence reaches an agent through an application-controlled retrieval interface, never through filesystem or database access. Assembly is deterministic, involves no model, and is fully testable without an API key.

## Scope

`src/trace_ai/services/context/input_package.py`:

- Build the extractor input from assessment metadata, source-document metadata, evidence references with their quoted text and identifiers, and the structured system input. The agent receives data; it never receives a path, a retrieval capability, or a credential.
- Fence untrusted content. Every source excerpt is wrapped in an explicitly labelled untrusted region carrying its evidence identifier, so the agent can cite the excerpt and so the trusted instructions remain outside the fence. Neutralise any fence delimiter occurring inside source text; `demo/forgeflow/input/sample-repository-notes.md` is a live test of exactly this, since a source document that can close the fence can escape it.
- Encode source precedence as data. `demo/forgeflow/input/structured-system-input.yaml` states that structured metadata is authoritative only for the fields it represents, that the Markdown documents remain the primary source for architectural reasoning, and that conflicts between structured and unstructured sources are surfaced rather than silently resolved. That rule belongs in the assembled package as an explicit statement in the trusted region, not left to model judgment.
- Consume the evidence location representation settled in DX-03, so a Markdown line range and a YAML key path are both citable and both round-trip.
- Enforce a size budget derived from the model profile, and report the evidence identifiers excluded rather than truncating silently. Silent truncation removes evidence a claim then appears to lack.
- Produce a deterministic result: the same assessment and the same evidence set yield byte-identical output, which is what makes the replay cache in the model abstraction usable.

## Acceptance criteria

- [ ] The assembled package contains every evidence identifier it quotes, and a test asserts no quoted excerpt appears without one.
- [ ] Fence delimiters appearing inside source text are neutralised; a test uses a crafted excerpt containing the delimiter.
- [ ] The injected block from `demo/forgeflow/input/sample-repository-notes.md` lands inside the untrusted region and appears nowhere in the trusted region.
- [ ] The package contains no filesystem path, no credential, no environment variable value, and no configuration object, with one test per category.
- [ ] The structured-input precedence rule appears in the trusted region as an explicit statement.
- [ ] Evidence citations use the DX-03 location representation, and a test covers a Markdown excerpt and a YAML excerpt.
- [ ] Exceeding the size budget reports the excluded evidence identifiers rather than truncating.
- [ ] Assembling the seven ForgeFlow input documents and the structured YAML completes with no model call and produces identical output across two runs.
- [ ] All tests run under a bare `uv run pytest` with no API key present.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Chunking, normalization, and evidence indexing, which the M1 document-loader and evidence issues provide.
- Deciding the evidence location representation, which is DX-03.
- Model calls, retries, and execution records.
- Semantic retrieval or embeddings. `docs/architecture/current-architecture.md` section 17 defers vector infrastructure.
- Input assembly for the other five agents, though the fencing helper is written to be reusable.

## References

- `docs/architecture/agent-design.md` section 22 (Tool Access Model), section 23 (Retrieval Design), section 24 (Prompt Structure — Input data), section 25 (Prompt Injection Handling), section 30 (Caching)
- `docs/architecture/current-architecture.md` section 12 (Security Boundaries — Source-document boundary), section 17 (Deferred Capabilities)
- `docs/architecture/data-model.md` section 7 (SourceDocument — Trust-level values), section 8 (EvidenceReference), section 39 open question 3
- `demo/forgeflow/input/structured-system-input.yaml` (`notes:` block)
- `demo/forgeflow/input/sample-repository-notes.md` ("Developer Scratch Notes")
