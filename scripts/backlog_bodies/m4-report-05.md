## Context

`docs/architecture/agent-design.md` section 20 makes generating an output manifest a responsibility
of the rendering node, and DX-12 fixes the manifest's format and fields. The manifest is what makes a
rendered report reproducible and comparable across versions: `docs/architecture/evaluation-plan.md`
section 3 requires every evaluation to record the architecture, workflow, prompt and requirements
catalog versions along with the model and its configuration.
`docs/architecture/data-model.md` section 35 requires the database to store references and content
hashes for filesystem artifacts.

## Scope

- Write the output manifest alongside the rendered report, in the format and with the fields fixed
  in DX-12. At minimum it records the report path, the report content hash, the assessment and
  workflow run identifiers, every version identifier required by evaluation-plan section 3, and the
  counts of approved findings, documentation gaps and open questions.
- Content hashing follows the decision in DX-20.
- Set `Assessment.final_report_path` (data-model section 5) to the written report, and update
  `Assessment.updated_at`.
- Record the render as an `ExecutionRecord` with `execution_type` deterministic, naming the node and
  node version and the input and output object identifiers (data-model section 27).
- The manifest is written after validation passes. A report that fails the consistency validator
  produces no manifest and does not become the assessment's final report.
- Manifest generation is deterministic and uses no model.

## Acceptance criteria

- [ ] A manifest is written alongside every successfully rendered report.
- [ ] The manifest contains every field enumerated by DX-12, including all version identifiers from
      evaluation-plan section 3.
- [ ] The recorded content hash matches a freshly computed hash of the report file.
- [ ] `Assessment.final_report_path` points at the written report after a successful render.
- [ ] A render that fails validation produces no manifest and leaves `final_report_path` unchanged.
- [ ] The manifest records a finding count of zero for an assessment with no approved findings, and
      the render is still recorded as successful.
- [ ] An `ExecutionRecord` exists for the render with `execution_type` deterministic and no model
      name.
- [ ] Manifest generation makes no model call.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The manifest format decision itself, fixed by DX-12.
- The assessment export package of data-model section 37, which remains deferred.
- Evaluation metrics computed from the manifest, owned by the evaluation component.

## References

- `docs/architecture/agent-design.md` — section 20
- `docs/architecture/data-model.md` — section 5, section 26, section 27, section 35, section 37
- `docs/architecture/current-architecture.md` — section 5.16, section 5.17
- `docs/architecture/evaluation-plan.md` — section 3, section 17
- `docs/product/design-principles.md` — section 8, section 10
