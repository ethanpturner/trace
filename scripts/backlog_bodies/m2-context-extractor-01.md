## Context

Agents propose; the application validates and persists. `docs/architecture/agent-design.md` section 22 states the write model plainly — agents return proposed structured objects and do not write authoritative records — and section 39 records it as a decision ready for the log. That boundary needs a concrete object: a single schema the model is asked to return, containing proposals and nothing authoritative. `data-model.md` section 33 requires validation immediately after model-generated structured output, and section 34 requires generation metadata, preferably through a linked `ExecutionRecord` rather than duplicated on every object.

## Scope

- `src/trace_ai/domain/proposals/context_extraction.py` — `ContextExtractionProposal` covering the outputs in `agent-design.md` section 7: system-level fields for `SystemContext`, plus proposed context claims, components, actors, assets, data flows, trust boundaries, and questions, plus the contradiction representation DX-14 records.
- Proposed objects use agent-local reference keys rather than application identifiers. The agent does not mint `cmp-` or `ast-` or `df-` identifiers, because identifier allocation belongs to the application under DX-02 and `data-model.md` section 2.1, and an agent-chosen identifier could collide with an existing record. A proposed data flow references components by the local key of a component proposed in the same response.
- Fields the schema must not contain, each enforced by a test: any severity, any finding-shaped object, `approved_at`, `approved_by`, an approved status, and any field that would let the response name a tool, a prompt, or a configuration value. These correspond to the prohibitions in `agent-design.md` section 7 and the tool-access limits in section 22.
- Evidence discipline carried into the proposal: every proposed claim states a status and a confidence, and `documented` and `inferred` proposals cite at least one evidence identifier drawn from the identifiers supplied in the input package. A proposal citing an identifier that was not supplied is rejected, since `agent-design.md` section 14 lists nonexistent evidence references among the failure conditions.
- A prompt-injection observation entry, in the form DX-13 records. `agent-design.md` section 25 says the workflow may create a context claim or a security event when injection-like content is detected without defining either; DX-13 settles it and this schema carries it, citing the evidence identifier of the offending passage.
- `src/trace_ai/domain/proposals/generation.py` — `GenerationMetadata` with the fields in `data-model.md` section 34: `generated_by`, `workflow_run_id`, `execution_record_id`, `model_name`, `prompt_version`, `generated_at`. `generated_by` is `context-extraction-v1` per `agent-design.md` section 33.
- A conversion function turning a validated proposal into domain objects with application-allocated identifiers, resolving local keys to those identifiers and failing on any unresolved key.
- JSON schema export, so the prompt embeds the schema rather than restating it by hand and the two cannot drift.

## Acceptance criteria

- [ ] `ContextExtractionProposal` covers every output listed in `agent-design.md` section 7 Outputs.
- [ ] Proposed objects carry local reference keys and no identifier field; a test asserts the schema accepts no application identifier for a newly proposed object.
- [ ] A proposal containing a severity, a finding, or an approval field fails schema validation, with one test per prohibition citing the relevant line of `agent-design.md` section 7.
- [ ] A proposed `documented` claim with no evidence reference fails validation.
- [ ] A proposed `assumed` or `unknown` claim with no evidence reference passes validation, and the test docstring cites DEC-009.
- [ ] A proposal citing an evidence identifier absent from the supplied input package is rejected.
- [ ] A proposed data flow whose local source key is absent from the proposed components fails conversion with a message naming the key.
- [ ] Conversion allocates identifiers under the DX-02 scheme using the prefixes in `data-model.md` section 2.1.
- [ ] `GenerationMetadata` matches `data-model.md` section 34 field for field, and `generated_by` is `context-extraction-v1`.
- [ ] The JSON schema of the proposal is exportable and stable across runs for unchanged models.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Calling a model, which the extraction node covers.
- Cross-object graph validation, which the Context Validation node covers. This issue governs schema shape, not the architecture's coherence.
- Choosing the contradiction representation or the prompt-injection object, which are DX-14 and DX-13.
- Persisting proposals. Where an invalid output is written is the retry policy's concern.

## References

- `docs/architecture/agent-design.md` section 5 (Shared Agent Contract), section 6 (Shared Agent Response Metadata), section 7 (Context Extraction Agent), section 14 (Evidence Validation Agent — Failure conditions), section 22 (Tool Access Model), section 25 (Prompt Injection Handling), section 33 (Agent Versioning), section 39 (Recommended Immediate Decisions)
- `docs/architecture/data-model.md` section 2.1 (Stable identifiers), section 33 (Schema Validation), section 34 (Model-Generated Output)
- `docs/architecture/decision-log.md` DEC-006, DEC-009
