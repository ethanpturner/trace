## Context

The Report Generation agent receives only approved or explicitly reportable objects
(`docs/architecture/agent-design.md` section 19, "Inputs"), and the report is a representation of
approved analysis rather than an independent source of truth
(`docs/product/design-principles.md` section 17). Both the model-assisted agent and the
deterministic renderer need the same input set, assembled once, so that the two cannot disagree
about what was approved. DX-12 fixes the report section list and which sections each component
owns; this issue implements the structures both consume.

## Scope

- A `ReportSections` model whose fields correspond exactly to the model-written sections assigned to
  the Report Generation agent by DX-12. Sections assigned to the renderer are not fields on this
  model.
- A report input assembly step that gathers, from the approved-set accessor: approved context,
  approved findings, approved documentation gaps, open questions, confirmed controls, reviewer notes
  and assessment scope, plus the report template identifier and the version identifiers required by
  `docs/architecture/evaluation-plan.md` section 3.
- Rejected, deferred and superseded candidates are excluded from the assembly. There is no code path
  by which they reach either the agent or the renderer.
- The assembly is deterministic and repeatable: the same approved state produces the same input
  structure.
- An explicit representation of the empty case. When no findings are approved, the assembly carries
  that fact as a value rather than as an absent key, so downstream code renders the template's
  empty-findings wording rather than skipping a section.
- Assumptions and limitations recorded on approved findings and on the assessment are carried
  through, because the agent is forbidden from removing material limitations and the validator has to
  check that it did not.

## Acceptance criteria

- [ ] `ReportSections` has one field per model-written section named by DX-12, and no field for a
      renderer-owned section.
- [ ] The assembly draws findings solely from the approved-set accessor; a test asserts that a
      rejected finding never appears in the assembled input.
- [ ] The assembled input contains every version identifier listed in evaluation-plan section 3.
- [ ] Two assemblies over identical approved state are equal.
- [ ] With zero approved findings, the assembly succeeds and represents the empty finding set
      explicitly.
- [ ] Every limitation and assumption recorded on an approved finding appears in the assembled input.
- [ ] Assembly makes no model call.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Generating prose.
- Rendering Markdown.
- The report template artifact itself, fixed by DX-12.

## References

- `docs/architecture/agent-design.md` — section 19 ("Inputs", "Outputs"), section 20, section 23
- `docs/architecture/current-architecture.md` — section 5.13, section 7
- `docs/architecture/data-model.md` — section 9, section 18, section 21, section 22, section 23,
  section 26
- `docs/architecture/evaluation-plan.md` — section 3 ("Versioned")
- `docs/product/design-principles.md` — section 6, section 17
