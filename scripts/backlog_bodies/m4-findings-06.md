## Context

The second structural checkpoint exists to preserve reviewer authority and to prevent provisional
model output from becoming an official conclusion
(`docs/architecture/current-architecture.md` section 8, DEC-005). It only achieves that if the
reviewer can actually see what a conclusion rests on. `docs/product/design-principles.md` section 5
requires the review surface to show what changed, why a conclusion was generated, supporting and
contradictory evidence, assumptions, confidence, open questions and agent critiques. This issue
assembles that package; the checkpoint mechanics are separate.

## Scope

- A deterministic assembler that produces, for each provisional finding, a review package
  containing: title, summary, description, severity, confidence, validation status, affected
  components and assets, impact, recommendation, assumptions and limitations.
- Supporting evidence rendered with source document, section or line location, and quoted text, per
  the evidence location representation fixed in DX-03. Contradictory evidence is shown alongside
  supporting evidence rather than omitted.
- The originating threat and control mapping, with the applicability rationale that made the
  requirement apply.
- The critiques raised against the finding and what was done about each.
- Unresolved `Question` objects related to the finding, with their priority and whether they are
  blocking.
- The same package shape for provisional `DocumentationGap` objects, so the reviewer can see gaps and
  findings side by side and judge whether the classification is right. This is the reviewer's
  opportunity to catch a DEC-009 misclassification that survived consolidation.
- A summary header for the assessment: counts of provisional findings, documentation gaps and open
  questions, and an explicit statement when the finding count is zero.
- Rendering follows the interface decision in DX-17. Whichever surface is chosen, the package is
  produced as structured data first and formatted second, so the same package can back a CLI, a file
  round-trip and a later web view.

## Acceptance criteria

- [ ] Every provisional finding in the package shows at least one evidence citation with document,
      location and quoted text, or an explicit statement that it rests on a low-confidence
      justification with that justification shown.
- [ ] Quoted evidence in the package matches the stored `quoted_text` byte for byte.
- [ ] Contradictory evidence recorded against a finding appears in its package.
- [ ] Every critique raised against a finding appears with its recommended action and its outcome.
- [ ] Provisional documentation gaps appear in the package, visibly distinguished from findings.
- [ ] An assessment with zero provisional findings produces a complete, well-formed package stating
      that no findings were proposed, and does not read as a failure.
- [ ] The package is produced as structured data, and a test asserts that formatting is a separate
      step over that data.
- [ ] Assembling the package makes no model call; a test asserts this.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The pause, the reviewer actions and the recording of decisions, which are the checkpoint issue.
- A web interface. `docs/product/roadmap.md` Stage 5 owns the demonstration interface.
- The final report, which is a different audience and a different document.

## References

- `docs/architecture/current-architecture.md` — section 5.12, section 8 ("Checkpoint 2")
- `docs/architecture/agent-design.md` — section 18, section 23
- `docs/architecture/data-model.md` — section 8, section 21, section 22, section 23, section 24,
  section 32
- `docs/architecture/decision-log.md` — DEC-004, DEC-005, DEC-009
- `docs/product/design-principles.md` — section 5, section 8, section 15
- `docs/product/roadmap.md` — Stage 4, "Human finding review"
