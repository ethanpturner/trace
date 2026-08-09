## Context

The Report Generation agent writes reviewer-facing prose from approved structured assessment data
(`docs/architecture/agent-design.md` section 19). It is the sixth and last of the capped
model-assisted agents. Its authority is deliberately narrow: it may improve readability, summarise,
reorder approved information and explain relationships, and it may not create findings, change
severity, add unsupported facts, remove material limitations, present assumptions as confirmed,
invent remediation requirements, alter quoted evidence or override reviewer decisions. Assembling
the final document is a separate deterministic node and is not part of this issue.

## Scope

- The prompt artifact `prompts/reporting/generate-report-sections-v1.md`, carrying every section
  required by `docs/architecture/agent-design.md` section 24, including the untrusted source-content
  boundary of section 25. Shared prompt fragments are composed by application code rather than
  copied (section 34).
- Agent implementation against the model abstraction and structured-output mechanism fixed in DX-05.
  No provider or model is selected here.
- Input is the assembled report input; the agent returns `ReportSections`, not an unconstrained
  document blob (agent-design section 19, "Outputs").
- Generation settings are conservative, per agent-design section 29 ("Low to moderate").
- Agent version `report-generation-v1`. Every result links to an `ExecutionRecord` recording node
  name, node version, prompt version, model name, token counts and duration (data-model section 27,
  agent-design section 6).
- Retry per agent-design section 19 and section 26: retry when required sections are absent, when the
  schema fails, when the report invents conclusions and when it contradicts approved objects.
  Retries are bounded by `maximum_retries_per_node`.
- Invalid output is preserved for debugging rather than discarded (data-model section 33).
- Unit tests against a stubbed model client covering prompt assembly, schema handling, retry routing
  and each failure condition in agent-design section 19. Any test reaching a live provider carries
  the `integration` marker.

## Acceptance criteria

- [ ] The prompt file exists at `prompts/reporting/generate-report-sections-v1.md` and contains every
      section required by agent-design section 24.
- [ ] A test asserts that rejected candidates and unapproved findings never appear in the assembled
      prompt input.
- [ ] Agent output validates against `ReportSections`; a response missing a required section is
      rejected and retried within `maximum_retries_per_node`.
- [ ] A response that names a finding not present in the approved input is rejected.
- [ ] With an empty approved-finding set, the agent produces a complete, valid section set using the
      template's empty-findings wording, and the run succeeds. A report with no findings is a
      successful report.
- [ ] The agent's output is not written to disk as the report; it is handed to the validator and the
      renderer.
- [ ] Prompt version and node version are recorded on the `ExecutionRecord`.
- [ ] Invalid output is preserved as a debug artifact.
- [ ] `uv run pytest` passes with no provider credential configured; every live-provider test is
      marked `integration` and is deselected by default.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Rendering Markdown, applying the template, numbering, anchors and file writing. Report rendering is
  a deterministic node that uses no model, and keeping the two apart is a binding constraint rather
  than a preference.
- Enforcing the prohibited operations. Prompt text states them; the deterministic validator
  guarantees them (`docs/product/design-principles.md` section 7).
- Selecting a model provider or model.
- The `PromptDefinition` object, which remains deferred in data-model section 40.

## References

- `docs/architecture/agent-design.md` — section 4 (classification table), section 6, section 19,
  section 20, section 22, section 23, section 24, section 25, section 26, section 29, section 32
  (Report Generation scorecard), section 33, section 34, section 36
- `docs/architecture/current-architecture.md` — section 5.13, section 9, section 10, section 11
- `docs/architecture/data-model.md` — section 21, section 23, section 27, section 33, section 34,
  section 40
- `docs/architecture/decision-log.md` — DEC-006, DEC-007
- `docs/product/design-principles.md` — section 7, section 12, section 17
