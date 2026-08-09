## Context

`docs/architecture/agent-design.md` section 10 defines the Threat Analysis Agent: it
generates plausible, scenario-based threats from the approved architecture context, using
STRIDE as a coverage aid rather than as a checklist. It is the second agent in the build
order at section 35 Phase 2, and one of the six capped model-assisted agents at
section 36. `prompts/` is currently an empty scaffold, so this issue also establishes the
prompt-file convention and the shared prompt content that the mapping, evidence
validation, and critique agents all compose later.

Two source documents disagree on prompt file naming.
`docs/architecture/agent-design.md` section 34 proposes hyphenated names under a `shared/`
tree; `docs/architecture/current-architecture.md` section 10 proposes underscored names
with no shared tree. Section 34 wins because `agent-design.md` is authoritative for agent
contracts. The correction is noted here so the convention is set once.

This issue also carries a folded sub-decision: whether the agent is invoked once per
assessment, once per trust boundary, or once per bounded group of components.
`docs/architecture/agent-design.md` section 38 question 2 leaves it open, and it cannot be
deferred past the first invocation.

## Scope

**Prompt artifacts.** Create the files named in `docs/architecture/agent-design.md`
section 34, using that document's hyphenated naming:

- `prompts/shared/source-content-boundary-v1.md`
- `prompts/shared/evidence-policy-v1.md`
- `prompts/shared/uncertainty-policy-v1.md`
- `prompts/threats/generate-scenario-threats-v1.md`

Each agent prompt carries the thirteen sections listed in section 24, in that order, with
authoritative workflow instructions separated from untrusted source content. Shared
content is composed in by application code and never copied into an agent prompt, which
section 34 states directly.

**Prompt content specific to this agent.** Encode, from section 10: the prohibitions on
generating final findings, asserting that a control is missing, assigning final severity,
inventing nonexistent components, treating theoretical possibility as confirmed exposure,
creating threats unrelated to the approved context, and recommending controls as a
substitute for threat analysis. Encode the required threat shape — actor or failure
source, preconditions, attack path or misuse, affected component, affected asset, impact.
Encode the explicit instruction not to emit one generic threat per STRIDE category.
Encode the evidence rule that evidence establishes the architecture conditions making the
threat plausible and need not prove exploitation.

**Code.** Add `src/trace_ai/agents/threat_analysis.py` covering input assembly, prompt
composition, the model call through the M2 model abstraction layer, a structured parse
into `ThreatProposal`, and bounded retry.

- Input assembly follows section 23: approved context, relevant architecture objects,
  selected supporting evidence. Not the whole assessment.
- Generation settings use moderate creativity per section 29, subject to that section's
  constraint that creativity must not override architectural grounding.
- Retry uses `maximum_retries_per_node: 2` and retries only on
  `schema_validation_failure`, `transient_provider_failure`, and
  `missing_required_relationship` per section 26. It never retries on
  `insufficient_evidence`, and explicitly never retries because the threat count is low,
  which section 10 addresses directly.
- Emit an `ExecutionRecord` per invocation, including failed ones, using the M2
  implementation.
- Register `PromptDefinition` metadata per `docs/architecture/data-model.md` section 29,
  including the prompt `content_hash`.
- Decide and record the invocation unit of work in `docs/architecture/decision-log.md`,
  weighing per-boundary invocation against section 10's warning about generic
  category-filling output and section 23's context-minimisation goal.

## Acceptance criteria

- [ ] The four prompt files exist at the section 34 paths, and each agent prompt contains
      all thirteen sections from section 24.
- [ ] Shared prompt content is composed by application code. No shared block is duplicated
      into `generate-scenario-threats-v1.md`, and a test asserts the composed prompt
      contains each shared block exactly once.
- [ ] A fixture test asserts that generic STRIDE category labels are rejected, which is
      the case named in section 31 under Fixture tests.
- [ ] A fixture test using `demo/forgeflow/input/sample-repository-notes.md` asserts the
      embedded injection block changes no output field and produces no secret-bearing text.
      `demo/forgeflow/forgeflow-scenario.md` section 17 lists the expected behaviours.
- [ ] Every emitted threat references at least one component and one asset present in the
      approved context. A proposal referencing an unknown identifier is a validation
      failure, not a silent drop.
- [ ] Retry routing is tested for each retryable and non-retryable class in section 26.
- [ ] A test asserts that a run producing a single well-formed threat succeeds and
      triggers no retry. Section 10 states that quality is more important than volume.
- [ ] An `ExecutionRecord` is produced for every invocation, including failures.
- [ ] No test under `tests/unit/` makes a live model call. Provider-backed tests carry the
      `integration` marker, which `addopts` deselects by default, so `uv run pytest`
      passes with no API key configured.
- [ ] A decision-log entry records the invocation unit of work and marks
      `docs/architecture/agent-design.md` section 38 question 2 resolved.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Threat validation and duplicate detection.
- The model abstraction layer, provider selection, and structured-output mechanism, all of
  which DX-05 settles and M2 implements.
- Any seventh agent. Section 36 caps the set at six.
- A threat-pattern library.

## References

- `docs/architecture/agent-design.md` section 10 (Threat Analysis Agent — full contract),
  section 23 (Retrieval Design — Threat Analysis Agent), section 24 (Prompt Structure),
  section 25 (Prompt Injection Handling), section 26 (Retry Policy), section 29
  (Temperature and Generation Controls), section 31 (Testing Strategy), section 33 (Agent
  Versioning), section 34 (Proposed Prompt Files), section 35 (Phase 2), section 36 (MVP
  Agent Set), section 38 question 2
- `docs/architecture/data-model.md` section 27 (ExecutionRecord), section 29
  (PromptDefinition)
- `docs/architecture/current-architecture.md` section 5.7 (Threat Analysis), section 9
  (Model Interaction Architecture), section 10 (Prompt Management — note the naming
  conflict resolved above)
- `demo/forgeflow/input/sample-repository-notes.md`;
  `demo/forgeflow/forgeflow-scenario.md` section 17 (Embedded Prompt-Injection Fixture),
  section 18 (Expected High-Value Threats)
- `CLAUDE.md`, *Working norms* — CI must never need a provider API key
