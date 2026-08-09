## Context

`docs/architecture/agent-design.md` section 12 lists "DocumentationGap candidates" among
the Mapping Agent's outputs, so the object is needed at the mapping step rather than at
finding consolidation. `docs/architecture/data-model.md` section 23 defines it and states
the distinction the project exists to defend: a documentation gap means Trace cannot
determine whether a control exists or is effective, while a finding means available
evidence supports the conclusion that a meaningful weakness exists. DEC-009 makes the same
separation from the decision side. `DocumentationGap` is not in the section 40 initial
implementation set, so promoting it into M3 is a deliberate departure from that ordering
and is recorded as such.

## Scope

- Add `src/trace_ai/domain/models/documentation_gap.py` with a `DocumentationGap` model
  per `docs/architecture/data-model.md` section 23. Required fields: `id`,
  `assessment_id`, `title`, `description`, `importance`, `severity`, `status`,
  `generated_by`. Optional: `related_object_ids`, `requested_evidence`, `evidence_ids`.
- Add a `DocumentationGapProposal` variant omitting the application-owned fields, matching
  the established proposal pattern.
- `severity` on this object is the importance of the documentation gap, not the severity
  of a weakness. Represent it per DX-11 and state the distinction in the model docstring,
  since the same `Severity` vocabulary from section 4.5 is reused for a different meaning
  and that is an easy field to misread.
- `related_object_ids` must resolve to existing objects in the assessment.
- Record the departure from `docs/architecture/data-model.md` section 40's ordering in the
  PR description, with the reason: the mapping agent emits gap candidates, so the object
  is required before the mapping step can produce valid output.
- Add a helper distinguishing a gap candidate from a mapping outcome, so that a mapping
  resolving to `unverified` can produce a `DocumentationGap` where the primary issue is
  inability to verify, and produce nothing where the requirement simply does not apply.
  `docs/architecture/agent-design.md` section 16 states both rules.

## Acceptance criteria

- [ ] `DocumentationGap` accepts the section 23 field set and rejects unknown fields.
- [ ] `DocumentationGapProposal` rejects a payload containing `id`, `assessment_id`,
      `generated_by`, or `status`.
- [ ] `related_object_ids` entries that do not resolve to an existing object are rejected,
      with the identifier named.
- [ ] `description` and `importance` are required and reject empty or whitespace-only
      text. A gap without a stated reason it matters is indistinguishable from noise.
- [ ] The model docstring states that `severity` here rates the documentation gap and not
      a security weakness, and cites `docs/architecture/data-model.md` section 23.
- [ ] A test asserts that a `DocumentationGap` carries no field that would let it be read
      as an asserted weakness — no recommendation, no impact, no validation status.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- `Finding`, created by Finding Consolidation in M4.
- `Question`, which M1 implements as part of the core model set per
  `docs/product/roadmap.md` Stage 1.
- Deciding when a documentation gap should itself become a finding. That is one of
  DEC-009's open questions and is settled by DX-08.
- Report rendering of gaps, which is M4 or later.

## References

- `docs/architecture/data-model.md` section 23 (DocumentationGap — Fields; Important
  distinction), section 4.5 (Severity), section 40 (Initial Implementation Priority — this
  object's absence from it)
- `docs/architecture/agent-design.md` section 12 (Mapping Agent — Outputs), section 14
  (Evidence Validation Agent — Outputs), section 16 (Reclassification rules)
- `docs/architecture/decision-log.md` DEC-009
- `docs/architecture/current-architecture.md` section 5.9 (Evidence Validation)
- `demo/forgeflow/forgeflow-scenario.md` section 21 (Expected Documentation Gaps)
