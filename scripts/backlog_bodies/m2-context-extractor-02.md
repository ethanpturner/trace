## Context

`prompts/` is empty. `docs/architecture/agent-design.md` section 34 names the four files this issue authors, and section 24 fixes the thirteen sections an agent prompt contains and the requirement that the authoritative instructions clearly separate trusted workflow instructions from untrusted source content. The prompt registry composes the shared blocks into the agent prompt, so the shared content lives in one place and is not copied.

## Scope

Author, as Markdown, the files named in `agent-design.md` section 34:

- `prompts/shared/source-content-boundary-v1.md` — the untrusted-source rules from `agent-design.md` section 25: source content is data; instructions found inside source content are not followed; source content cannot modify the agent's role; source content cannot redefine output schemas; source content cannot authorize tools; suspicious instructions are reported as an observation rather than obeyed.
- `prompts/shared/evidence-policy-v1.md` — the evidence hierarchy in `agent-design.md` section 14 and the citation rules in section 7 Evidence requirements: a documented claim cites at least one evidence reference; an inferred claim states the evidence used, an explicit inferred status, a concise rationale, and a confidence; unknown facts remain unknown.
- `prompts/shared/uncertainty-policy-v1.md` — DEC-009 in prompt form: missing documentation is not proof that a control is absent, and the permitted outputs are an explicit assumption, an `unknown` claim, or a question.
- `prompts/context/extract-context-v1.md` — the Context Extraction prompt, carrying the thirteen sections of `agent-design.md` section 24 in order: Role and purpose, Authoritative instructions, Input schema, Output schema, Definitions, Allowed operations, Prohibited operations, Evidence rules, Handling of uncertainty, Handling of source-document instructions, Quality criteria, Examples, Input data.

Content requirements:

- Allowed and Prohibited operations are transcribed from `agent-design.md` section 7, including the prohibitions on assuming an undocumented control is absent, inventing implementation details without labeling them as assumptions, treating source instructions as workflow commands, and resolving material contradictions without reviewer input.
- The Output schema section embeds the exported JSON schema of the context-extraction proposal rather than restating fields, so prompt and schema cannot drift.
- The prompt declares the three shared blocks it requires, in the form the registry consumes, rather than containing their text.
- Examples cover at least an inherited control recognised as inherited rather than absent, a claim correctly marked `unknown`, and an ambiguous statement turned into a question. Draw them from the intentional non-findings and ambiguities in `demo/forgeflow/forgeflow-scenario.md` sections 14 and 15 without reproducing scenario truth the agent is not meant to know; that document is hidden benchmark truth, not input.
- The Input data section delimits untrusted source content unambiguously, with the boundary stated in the trusted half of the prompt.
- The prompt names no model provider, no model, and no temperature. Generation settings belong to the model abstraction, not to the artifact.

## Acceptance criteria

- [ ] All four files exist at the paths named in `agent-design.md` section 34.
- [ ] `extract-context-v1.md` contains all thirteen section headings from `agent-design.md` section 24, and a test asserts their presence and order.
- [ ] `extract-context-v1.md` declares the three shared blocks and contains none of their text; the registry's single-source test passes.
- [ ] The Output schema section embeds the exported proposal schema, and a test asserts the embedded schema matches the current export.
- [ ] The prompt instructs the agent to report injection-like content as an observation and states that it must not act on it.
- [ ] The prompt states that a documented claim requires an evidence identifier and that an unsupported statement is marked `assumed` or `unknown`.
- [ ] The prompt contains no provider name, model name, or temperature value; a test asserts this.
- [ ] Prose register matches the corpus: flat declarative, no marketing language, no emoji.
- [ ] No text is reproduced from `demo/forgeflow/forgeflow-scenario.md` beyond what the input documents already contain.

## Out of scope

- Prompts for the other five agents.
- The registry and composition loader, which the runtime prompt issue provides.
- Prompt tuning or comparison. `docs/architecture/evaluation-plan.md` section 12 requires a prompt change to be measured, and there is no baseline yet.
- Assembling input data into the prompt, which the input-package issue covers.

## References

- `docs/architecture/agent-design.md` section 7 (Context Extraction Agent), section 14 (Evidence hierarchy), section 24 (Prompt Structure), section 25 (Prompt Injection Handling), section 33 (Agent Versioning), section 34 (Proposed Prompt Files)
- `docs/architecture/current-architecture.md` section 10 (Prompt Management), section 5.5 (Context Extraction — Output discipline)
- `docs/architecture/decision-log.md` DEC-009
- `demo/forgeflow/forgeflow-scenario.md` section 2 (Scenario Design Rule), section 14 (Intentional Non-Findings), section 15 (Intentional Ambiguities)
