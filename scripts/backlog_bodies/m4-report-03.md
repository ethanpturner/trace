## Context

Report rendering is a deterministic workflow node and uses no AI model
(`docs/architecture/agent-design.md` section 20, final line). It applies the report template,
renders approved findings, evidence references and tables, numbers sections, generates anchors,
includes methodology and limitations, and writes the output files. The separation from the
generation agent is the mechanism behind `docs/product/design-principles.md` section 17: structured
analysis stays authoritative and prose is a representation of it. The initial and only MVP output
format is Markdown (`docs/architecture/current-architecture.md` section 5.13 and section 14).

## Scope

- A renderer that takes the assembled approved input and the `ReportSections` produced by the
  generation agent and emits Markdown to the assessment's output directory, following the file
  naming and section ownership fixed in DX-12.
- Deterministic rendering of every section DX-12 assigns to the renderer, drawn from the objects
  rather than from agent prose: approved findings, documentation gaps, open questions, existing
  controls, assumptions, the evidence appendix, methodology and limitations.
- Findings render from `Finding` objects: title, severity, confidence, validation status, affected
  components and assets, impact, recommendation, assumptions, limitations and evidence citations.
- Evidence citations render source document, location and quoted text, using the location
  representation fixed in DX-03. Quoted text is reproduced unaltered.
- Stable section numbering and anchor generation, so two runs over identical approved state produce
  byte-identical output apart from timestamps.
- Artifact isolation: output is written under the assessment's own directory and never mixes
  assessments (`docs/architecture/current-architecture.md` section 5.16 and section 12,
  "Assessment-data boundary").
- The rendering module imports no model client. It does not construct one, does not receive one, and
  does not depend on any module that does.

## Acceptance criteria

- [ ] The rendering module imports no model client, and a test asserts this — by inspecting the
      module's import graph, or by running the renderer with the model abstraction patched to raise
      on any call, or both.
- [ ] Two runs over identical approved state produce identical output apart from timestamps.
- [ ] Every approved finding appears exactly once, and no rejected, deferred or provisional finding
      appears anywhere in the document.
- [ ] Every rendered finding shows at least one evidence citation resolving to a real
      `EvidenceReference`, with source document, location and quoted text.
- [ ] Quoted evidence in the rendered document matches the stored `quoted_text` byte for byte.
- [ ] With zero approved findings, the renderer produces a complete, well-formed report using the
      template's empty-findings wording, and the run succeeds. A report stating that no findings were
      identified is a correct report, not an empty one.
- [ ] Documentation gaps render as gaps and are never presented as confirmed weaknesses; a test named
      for DEC-009 asserts this over the rendered text.
- [ ] Anchors are unique within the document and stable across runs.
- [ ] Output is confined to the assessment's own directory; a test asserts no write outside it.
- [ ] `uv run pytest` passes with no provider credential configured. Rendering requires none.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Generating prose, which is the model-assisted Report Generation agent.
- Validating the agent's prose against approved objects, which is the report consistency validator.
- The output manifest and recording the artifact on the assessment, which is a separate issue.
- Formats other than Markdown. `docs/product/future-features.md` section 13.5 defers PDF, HTML and
  JSON and states that Markdown is sufficient for the MVP.
- The export package sketched in data-model section 37, which remains deferred.

## References

- `docs/architecture/agent-design.md` — section 4, section 20
- `docs/architecture/current-architecture.md` — section 5.13, section 5.16, section 12, section 14
- `docs/architecture/data-model.md` — section 8, section 21, section 22, section 23, section 32,
  section 37
- `docs/architecture/decision-log.md` — DEC-004, DEC-009
- `docs/product/design-principles.md` — section 7, section 8, section 17
- `docs/product/future-features.md` — section 13.5
- `docs/product/roadmap.md` — Stage 4, "Deterministic report rendering"
