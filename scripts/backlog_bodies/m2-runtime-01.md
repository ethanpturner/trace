## Context

No model call exists anywhere in `src/`. `anthropic`, `openai`, `langchain`, and `instructor` are declared in `pyproject.toml` and imported nowhere; their presence is not a choice. `docs/architecture/current-architecture.md` section 9 requires a model abstraction layer rather than direct provider calls scattered through the codebase. DX-05 settles the provider question, the structured-output mechanism, and whether a library is used; this issue builds what DX-05 records. CI must never need a provider API key — `pyproject.toml` deselects the `integration` and `evaluation` markers by default precisely so a bare `pytest` cannot spend money.

## Scope

`src/trace_ai/infrastructure/model/`:

- A protocol for structured generation: given rendered prompt text, a target Pydantic model, and generation settings, return either a validated instance or a structured failure. The failure type carries the raw output, because `data-model.md` section 33 requires an invalid output be preserved for debugging rather than discarded.
- A result type carrying the fields the execution ledger needs: model name, input tokens, output tokens, estimated cost, and duration, so `ExecutionRecord` (`data-model.md` section 27) and `WorkflowRun` (section 26) can be populated without the caller reaching into a provider response.
- Generation settings as a typed object, with the conservative defaults `agent-design.md` section 29 assigns to structured analytical agents. Context Extraction has a "Low" creativity need in that table.
- A provider adapter implementing the protocol against whatever DX-05 selects, reading credentials only through `trace_ai.config.Settings` and `Settings.require()`. No provider SDK is constructed at import time.
- A `model_profile` registry giving meaning to `AssessmentConfiguration.model_profile`, which `data-model.md` section 6 makes a required string pointing at nothing. The registry maps a profile name to a model, generation settings, and limits.
- Two test substitutes, which `current-architecture.md` section 9 lists as a required capability of the abstraction:
  - A deterministic fake returning a caller-supplied object or failure, used by every unit test.
  - A record-and-replay cache keyed on the content hash of the rendered prompt, the prompt version, and the model configuration, following `agent-design.md` section 30. `agent-design.md` section 30 also warns that caching must not hide workflow changes during evaluation, so the key includes every version identifier that could change behaviour.
- Timeout handling and bounded backoff for transient provider failures, classified so the retry policy can route on them rather than inspecting exception text.

## Acceptance criteria

- [ ] A single protocol is the only path from application code to a provider; a test asserts no module outside `src/trace_ai/infrastructure/model/` imports `anthropic`, `openai`, `langchain`, or `instructor`.
- [ ] A schema failure returns a structured failure carrying the raw output rather than raising, and a test asserts the raw output is recoverable.
- [ ] The result type exposes model name, input tokens, output tokens, estimated cost, and duration.
- [ ] Generation settings default to the conservative values `agent-design.md` section 29 assigns, and a test asserts the Context Extraction profile is among the low-creativity settings.
- [ ] `AssessmentConfiguration.model_profile` resolves through the registry, and an unknown profile name fails with a message naming the configured value and the known profiles.
- [ ] Credentials are read only through `Settings.require()`, and a missing key produces `MissingSettingError` rather than a provider authentication error.
- [ ] The deterministic fake satisfies the protocol and is used by at least one test that constructs no provider client.
- [ ] The replay cache key changes when the prompt content hash, the prompt version, or the model configuration changes; one test per component of the key.
- [ ] A bare `uv run pytest` with no API key present passes and makes no network call.
- [ ] Any live provider test carries the `integration` marker and is deselected by the default `addopts`.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Selecting the provider, the model, or the structured-output library. DX-05 settles those and this issue implements the result.
- Orchestration. Which node calls the model and in what order is the workflow runtime's concern.
- Retry policy and error taxonomy, which are a separate runtime issue; this issue only classifies provider-level transient failures so that policy can route on them.
- LangSmith or any external tracing. `current-architecture.md` section 5.17 requires the local audit record to remain authoritative and a data-handling review before external tracing is used.
- Multi-model or per-agent model selection. `agent-design.md` section 28 begins with one primary capable model.

## References

- `docs/architecture/current-architecture.md` section 9 (Model Interaction Architecture), section 5.17 (Trace and Audit Service), section 11 (Error Handling — Model-service failure), section 19 open questions 2 and 3
- `docs/architecture/agent-design.md` section 28 (Model Selection), section 29 (Temperature and Generation Controls), section 30 (Caching)
- `docs/architecture/data-model.md` section 6 (AssessmentConfiguration), section 26 (WorkflowRun), section 27 (ExecutionRecord), section 33 (Schema Validation)
- `src/trace_ai/config.py` (`Settings`, `SecretStr`, `require()`, `MissingSettingError`)
- `pyproject.toml` (`[tool.pytest.ini_options] addopts`, `markers`)
