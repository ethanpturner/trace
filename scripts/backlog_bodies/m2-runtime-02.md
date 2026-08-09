## Context

`prompts/` is scaffolded and empty. Prompts are designed to be version-controlled project artifacts rather than strings embedded across application code (`docs/architecture/current-architecture.md` section 10), and `docs/architecture/agent-design.md` section 34 names the file tree, including a `shared/` directory whose content is composed into agents through application code rather than copied into every prompt. `data-model.md` section 26 makes `prompt_versions` a required field on `WorkflowRun`, so a prompt cannot be used without a recorded version, and section 29 defines the metadata a prompt carries.

## Scope

`src/trace_ai/services/prompts/`:

- A registry that discovers prompt files under `prompts/` and exposes them by identifier and version. It reads the tree; it does not hold prompt text in Python.
- A composition loader that assembles an agent prompt from its own file plus the shared blocks it declares, in a fixed and recorded order. The three shared blocks named in `agent-design.md` section 34 are `prompts/shared/source-content-boundary-v1.md`, `prompts/shared/evidence-policy-v1.md`, and `prompts/shared/uncertainty-policy-v1.md`. Composition is the mechanism that keeps them single-sourced; a copy in an agent prompt is a defect this issue exists to prevent.
- A declaration mechanism by which an agent prompt names the shared blocks it requires, so composition is data in the prompt tree rather than a hard-coded list in the loader.
- `PromptDefinition` metadata per `data-model.md` section 29: `id`, `version`, `name`, `purpose`, `file_path`, `expected_input_schema`, `expected_output_schema`, `model_constraints`, `status`, `content_hash`. Section 40 defers persisting `PromptDefinition`, so the loader computes and returns the metadata without writing a record.
- `content_hash` computed over the composed result, not over the agent file alone, so a change to a shared block is visible in the hash of every prompt that includes it. The hash algorithm and format follow DX-20.
- Loud failure on a missing prompt file or a missing declared shared block. A silently shorter prompt is the worst failure mode available here, because it removes the untrusted-source boundary without removing the call.
- Resolve the file-naming conflict in the corpus. `agent-design.md` section 34 uses hyphenated names and a `shared/` tree; `current-architecture.md` section 10 uses underscored names and a different file set. Adopt section 34 and correct `current-architecture.md` section 10 in the same pull request so the two documents describe the same tree.

## Acceptance criteria

- [ ] The registry discovers prompts under `prompts/` and resolves one by identifier and version.
- [ ] Composing a prompt that declares all three shared blocks yields text containing each block exactly once.
- [ ] A test asserts that the text of each shared block appears exactly once across the whole `prompts/` tree, so a copied block fails CI.
- [ ] The returned `content_hash` changes when a shared block changes, and a test proves it by editing a fixture block.
- [ ] A missing prompt file raises a named error; a missing declared shared block raises a named error naming the block.
- [ ] `PromptDefinition` metadata matches `data-model.md` section 29 field for field.
- [ ] The loader records the composition order, and the same inputs produce byte-identical output across runs.
- [ ] `current-architecture.md` section 10 is corrected to the hyphenated names and the `shared/` tree from `agent-design.md` section 34.
- [ ] Loading performs no model call and needs no API key; the tests run under a bare `uv run pytest`.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Writing prompt content. The shared blocks and the context-extraction prompt are authored in the context-extractor issues.
- Prompt evaluation or tuning. `docs/architecture/evaluation-plan.md` section 12 requires a prompt change to be measured, and there is nothing yet to measure against.
- Persisting `PromptDefinition` records, deferred by `data-model.md` section 40.
- Assembling input data into a prompt, which is the extractor's input-package issue.

## References

- `docs/architecture/agent-design.md` section 24 (Prompt Structure), section 34 (Proposed Prompt Files)
- `docs/architecture/current-architecture.md` section 10 (Prompt Management)
- `docs/architecture/data-model.md` section 26 (WorkflowRun — `prompt_versions`), section 29 (PromptDefinition), section 40 (Initial Implementation Priority)
- `docs/architecture/decision-log.md` DEC-006
- `prompts/` (currently empty)
