## Context

`docs/architecture/data-model.md` section 24 defines `Critique` but gives `critique_type`
and `recommended_action` as prose examples rather than as enumerations, and section 40
defers the object until "the main workflow begins operating" — which the mapping and
evidence-validation steps now satisfy. `docs/architecture/agent-design.md` section 15
makes "Critiques lack target objects" and "Critiques lack actionable recommendations"
invalid outputs, so both fields must be structurally enforced rather than left to prompt
wording.

DX-08 settles the critic's unit of work, the identity of the objects section 15 calls
"candidate finding material", and whether the critic may propose missing threats. This
issue builds the model against that decision; if missing-threat proposals are not
permitted, the corresponding critique type is omitted.

## Scope

- Add `src/trace_ai/domain/models/critique.py` with a `Critique` model per
  `docs/architecture/data-model.md` section 24.
- Promote `critique_type` to a closed `CritiqueType` enumeration from that section's
  examples: `unsupported_claim`, `missing_evidence`, `ignored_inherited_control`,
  `duplicate`, `severity_overstated`, `severity_understated`, `missing_precondition`,
  `weak_attack_path`, `generic_recommendation`, `documentation_gap_only`,
  `contradictory_analysis`, and `missing_high_impact_threat`. Include the last only if
  DX-08 permits missing-threat proposals.
- Promote `recommended_action` to a closed `RecommendedAction` enumeration from the five
  values section 24 names in its field description: `keep`, `revise`, `reject`, `merge`,
  `investigate`.
- Promote `subject_type` to a closed enumeration covering the object types DX-08 fixes as
  the critic's review scope. A free string makes a critique unjoinable to its target.
- Make `subject_type`, `subject_id`, `description`, `rationale`, and `recommended_action`
  required and non-empty.
- Add a `CritiqueProposal` variant omitting the application-owned fields, matching the
  established proposal pattern.
- Represent `confidence` per DX-19.
- The `severity_overstated` and `severity_understated` types reference severity that no M3
  agent assigns. Record in the model docstring that these types are reachable only once
  DX-11 places severity in the workflow, and that a critique of either type against an
  object with `severity: unassigned` is invalid.

## Acceptance criteria

- [ ] `Critique` rejects a payload whose `subject_id` does not resolve to an existing
      object in the assessment, and rejects a `subject_id` whose object type does not match
      the declared `subject_type`.
- [ ] `critique_type` and `recommended_action` accept only the enumerated values.
- [ ] `description`, `rationale`, and `recommended_action` are required and reject empty or
      whitespace-only text.
- [ ] `CritiqueProposal` rejects a payload containing `id`, `assessment_id`,
      `generated_by`, or `status`.
- [ ] A `severity_overstated` or `severity_understated` critique against an object with
      `severity: unassigned` is rejected, with a message naming DX-11.
- [ ] A test asserts the model carries no field permitting a critique to state an outcome
      rather than a recommendation. `docs/architecture/agent-design.md` section 15
      prohibits the critic from directly approving findings.
- [ ] The departure from `docs/architecture/data-model.md` section 40's deferral is stated
      in the PR description with its reason.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The Critical Review agent and its prompt.
- Applying critique recommendations.
- Severity assignment, owned by DX-11.
- `Finding`, created by Finding Consolidation in M4.

## References

- `docs/architecture/data-model.md` section 24 (Critique — Fields; Critique-type
  examples), section 4.2 (ConfidenceLevel), section 4.5 (Severity), section 40 (Initial
  Implementation Priority — the deferral this issue departs from)
- `docs/architecture/agent-design.md` section 15 (Critical Review Agent — Responsibilities;
  Outputs; Prohibited operations; Failure conditions), section 23 (Retrieval Design —
  Critical Review Agent)
- `docs/architecture/current-architecture.md` section 5.10 (Critical Review)
- `docs/architecture/decision-log.md` DEC-005, DEC-006
