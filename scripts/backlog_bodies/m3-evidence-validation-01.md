## Context

`docs/architecture/agent-design.md` section 14 defines the Evidence Validation Agent,
which evaluates whether proposed security conclusions are sufficiently supported. Its
output object is `EvidenceAssessment`, defined at `docs/architecture/data-model.md`
section 20. That section 40 places `EvidenceAssessment` in the deferred group, to be added
"once the main workflow begins operating" — which the mapping step now satisfies.
Promoting it into M3 is a deliberate departure from the section 40 ordering and is
recorded as such.

The object matters because it is the workflow's only structured record of the difference
between a claim that is supported and a claim that is merely repeated. Section 14 makes
"Treat repeated model claims as independent corroboration" a prohibited operation, and
without a first-class assessment object that prohibition has nowhere to live.

## Scope

- Add `src/trace_ai/domain/models/evidence_assessment.py` with an `EvidenceAssessment`
  model per `docs/architecture/data-model.md` section 20. Required fields: `id`,
  `assessment_id`, `subject_type`, `subject_id`, `evidence_ids`, `validation_status`,
  `rationale`, `confidence`, `generated_by`, `created_at`. Optional: `missing_evidence`,
  `contradictions`.
- Reuse `ValidationStatus` from section 4.7: `supported`, `partially_supported`,
  `unsupported`, `contradicted`, `requires_confirmation`, `not_evaluated`.
- Promote `subject_type` to a closed enumeration covering the object types section 14
  names as evaluable: context claim, control, control mapping, threat, and documentation
  gap candidate. A free string here makes the assessment unjoinable to its subject.
- Add an `EvidenceAssessmentProposal` variant omitting the application-owned fields,
  matching the established proposal pattern.
- Represent `contradictions` per the DX-14 decision rather than as free text, so a
  contradiction can be joined back to the evidence references that disagree.
- Encode the evidence hierarchy from section 14 as an ordered, referenceable vocabulary:
  reviewer-confirmed fact, direct implementation or configuration evidence, explicit
  architecture documentation, structured project input, multiple consistent contextual
  references, reasonable inference, unsupported assumption. Section 14 states it is
  guidance rather than a universal scoring formula, so encode it as a label the rationale
  can cite and not as an arithmetic score.
- Represent `confidence` per DX-19.

## Acceptance criteria

- [ ] `EvidenceAssessment` accepts the section 20 field set and rejects unknown fields.
- [ ] `subject_id` must resolve to an existing object of the declared `subject_type`, and
      a mismatch is rejected with both values named.
- [ ] `evidence_ids` is required and must reference existing evidence. Section 14 makes
      "Evidence references do not exist" a failure condition.
- [ ] `rationale` is required and rejects empty or whitespace-only text.
- [ ] `validation_status: supported` with an empty `evidence_ids` is rejected. Section 14
      makes "Unsupported claims are marked supported" a failure condition and the schema
      enforces the structural half.
- [ ] `validation_status: not_evaluated` with an empty `evidence_ids` is valid, because
      not evaluating something is a legitimate state and must not require evidence.
- [ ] The evidence hierarchy is available as an ordered vocabulary and carries no implied
      numeric score. A test asserts no arithmetic is performed over it.
- [ ] `contradictions` uses the DX-14 representation and a contradiction entry resolves to
      the evidence references that disagree.
- [ ] The departure from `docs/architecture/data-model.md` section 40's deferral is stated
      in the PR description with its reason.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The Evidence Validation agent itself.
- `Finding`, created by Finding Consolidation in M4.
- Numeric confidence scoring. DX-19 owns the confidence model and
  `docs/architecture/data-model.md` section 4.2 warns against false precision.
- Deciding the evidence threshold for satisfaction states. DX-08 owns it.

## References

- `docs/architecture/data-model.md` section 20 (EvidenceAssessment — Fields), section 4.7
  (ValidationStatus), section 4.2 (ConfidenceLevel), section 4.3 (EvidenceStrength),
  section 40 (Initial Implementation Priority — the deferral this issue departs from)
- `docs/architecture/agent-design.md` section 14 (Evidence Validation Agent —
  Responsibilities; Evidence hierarchy; Prohibited operations; Failure conditions)
- `docs/architecture/current-architecture.md` section 5.9 (Evidence Validation)
- `docs/architecture/decision-log.md` DEC-006, DEC-009
