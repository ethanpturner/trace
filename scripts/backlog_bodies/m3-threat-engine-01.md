## Context

`docs/architecture/data-model.md` section 16 defines `Threat` and section 40 places it
eleventh in the initial implementation priority. Section 33 requires Pydantic validation
at input, after model-generated structured output, before persistence, and before workflow
transitions. `docs/architecture/agent-design.md` section 2.5 and section 22 require that
agents return proposed objects which the application validates and persists, so the schema
an agent returns is deliberately not the schema that is stored. Both are needed here.

This issue also carries a folded sub-decision. `docs/architecture/agent-design.md`
section 11 requires the Threat Validation node to "Confirm threat categories use permitted
values", but no document enumerates those values. Section 16 of the data model types
`Threat.category` as `list[string]` and its worked example uses `spoofing` and
`elevation_of_privilege`. The vocabulary is decided and recorded here rather than in M0,
because it is narrow and has no consumer outside the threat engine.

## Scope

- Add `src/trace_ai/domain/models/threat.py` with a `Threat` Pydantic model carrying every
  field in `docs/architecture/data-model.md` section 16. A field marked Required there is
  non-optional here.
- Reuse the shared enumerations from sections 4.1 and 4.2 — `ObjectStatus`,
  `ConfidenceLevel` — from wherever M1 placed them. Do not redefine them.
- Decide and record the permitted threat category vocabulary. Propose the STRIDE set in
  the snake_case form the section 16 example already uses. Decide whether a category
  outside the set is rejected or accepted with a warning, and state how AI-specific
  threats are categorised given that STRIDE has no category for them while
  `docs/architecture/agent-design.md` section 10 requires them "where applicable". Record
  the outcome in `docs/architecture/decision-log.md`.
- Decide whether `AssessmentConfiguration.threat_methodology` is validated against a
  registry of known values or remains free text for the MVP, and record that alongside.
- Add a separate `ThreatProposal` model as the agent-facing output schema. It omits every
  field the application owns — `id`, `assessment_id`, `created_at`, `generated_by`,
  `status` — so an agent structurally cannot mint an identifier or set its own review
  state. Referenced objects stay as identifier lists, because the agent selects from
  identifiers supplied to it.
- Add a promotion function converting a validated `ThreatProposal` plus workflow context
  into a `Threat` with `status: candidate` and `generated_by: threat-analysis-v1`, per
  `docs/architecture/agent-design.md` section 33.
- Unit tests under `tests/unit/`.

## Acceptance criteria

- [ ] `Threat` accepts the worked example in `docs/architecture/data-model.md` section 16
      (`thr-007`) without any modification to that example.
- [ ] `ThreatProposal` rejects a payload containing `id`, `assessment_id`, `status`,
      `generated_by`, or `created_at`, rather than silently ignoring them.
- [ ] `affected_component_ids` and `affected_asset_ids` are required and non-empty.
      `docs/architecture/agent-design.md` section 10 makes "Threats do not identify
      affected assets or components" an invalid output.
- [ ] `impact` is required and rejects empty or whitespace-only text. Section 10 makes
      "Threats lack plausible security impact" an invalid output.
- [ ] `confidence` accepts only the values fixed by DX-19.
- [ ] `category` accepts only the vocabulary decided in this issue.
- [ ] Promotion assigns `status: candidate` and never `approved`.
- [ ] A decision-log entry records the category vocabulary, the handling of an
      uncategorisable threat, and the `threat_methodology` validation choice.
- [ ] `uv run mypy` passes in strict mode and `uv run ruff check .` passes.
- [ ] No test in this issue makes a model call.

## Out of scope

- The Threat Analysis agent itself.
- Duplicate detection, which belongs with the validation node.
- Persistence mechanics, which DX-04 settles and M1 implements.
- A threat-pattern library. `docs/architecture/agent-design.md` section 10 lists one as an
  optional input and it is not required for the MVP.

## References

- `docs/architecture/data-model.md` section 16 (Threat — Fields, Example), section 4.1
  (ObjectStatus), section 4.2 (ConfidenceLevel), section 6 (AssessmentConfiguration —
  threat_methodology), section 33 (Schema Validation), section 34 (Model-Generated Output),
  section 40 (Initial Implementation Priority)
- `docs/architecture/agent-design.md` section 10 (Threat Analysis Agent — Methodology;
  Prohibited operations; Failure conditions), section 11 (Threat Validation Node —
  Responsibilities), section 2.5 (Agents propose), section 22 (Write model), section 33
  (Agent Versioning), section 38 question 15
- `docs/architecture/current-architecture.md` section 15 (Repository Structure)
