## Context

`ContextClaim` carries the distinction the project exists to defend: a claim states its own epistemic status, so a documented fact, an inference, an assumption, and an unknown are never collapsed (`docs/architecture/data-model.md` sections 2.3 and 10). DEC-009 depends on that field being honest — missing documentation resolves to `unknown` or `assumed`, never to a claim that a control is absent. `agent-design.md` section 7 lists ContextClaim objects among the Context Extraction Agent's outputs.

## Scope

- `src/trace_ai/domain/models/context_claim.py` — `ContextClaim` with the section 10 field list: `id`, `assessment_id`, `subject_type`, `subject_id`, `predicate`, `value`, `status`, `confidence`, `confidence_score`, `evidence_ids`, `source_origin`, `generated_by`, `reviewer_notes`, `created_at`, `updated_at`, `supersedes_id`.
- `ClaimStatus` with exactly the seven values in section 10 "Status values": `documented`, `inferred`, `user_confirmed`, `assumed`, `unknown`, `contradicted`, `rejected`.
- Identifiers use the `ctx-` prefix from section 2.1, allocated under the DX-02 scheme.
- The confidence representation follows DX-19. `confidence` is required and `confidence_score` is optional; the relationship between them is DX-19's to define and this model enforces it rather than inventing one.

Model validators expressing `agent-design.md` section 7 "Evidence requirements":

- `status == documented` requires at least one entry in `evidence_ids`.
- `status == inferred` requires at least one entry in `evidence_ids`.
- `status` in `{assumed, unknown}` must not require evidence and must not be rejected for lacking it. This is the DEC-009 path and a test pins it.
- `confidence_score`, when present, lies within the range DX-19 fixes and does not contradict `confidence`.

Two typing problems are resolved here:

1. `ContextClaim.value` is typed `any` in section 10. Under `mypy --strict` this needs a concrete JSON-compatible union. Define one narrow alias covering scalars, lists, and string-keyed mappings, and record in the module docstring that `data-model.md` section 39 open question 1 — flexible subject-predicate-value against typed models — remains open and is not answered by this alias.
2. `agent-design.md` section 7 requires inferred claims to carry "a concise rationale", and section 10 defines no `rationale` field. `reviewer_notes` is the reviewer's field, not the agent's. Either add `rationale` to `ContextClaim` with a decision-log entry, or record in the module docstring where the agent's rationale is stored instead.

The `contradicted` status is populated according to the contradiction representation settled in DX-14; this issue implements whatever DX-14 records rather than choosing.

## Acceptance criteria

- [ ] `ContextClaim`'s field set matches `data-model.md` section 10 exactly, with a test that fails on drift.
- [ ] `ClaimStatus` has exactly the seven values listed in section 10, and a test asserts the count and the members.
- [ ] Constructing a `documented` claim with an empty `evidence_ids` raises a validation error naming the field.
- [ ] Constructing an `assumed` or `unknown` claim with an empty `evidence_ids` succeeds, and the test docstring cites DEC-009.
- [ ] A `confidence_score` outside the DX-19 range is rejected.
- [ ] `ContextClaim.value` has a concrete JSON-compatible type and `uv run mypy` passes strict.
- [ ] The rationale question is resolved: either a `rationale` field exists with a decision-log entry, or the module docstring records where the agent rationale lives.
- [ ] Round-tripping a claim through JSON preserves `value` for a scalar, a list, and a nested mapping.

## Out of scope

- `DocumentationGap`. The Context Extraction Agent's output list in `agent-design.md` section 7 does not include it; it is produced by the mapping and evidence-validation steps in sections 12 and 14.
- Deciding the `predicate` vocabulary. It stays free text, following the precedent recorded for `applicable_conditions` in `requirements/README.md`, so a vocabulary can be observed before it is fixed.
- Choosing the contradiction representation, which is DX-14.
- Answering questions or applying reviewer edits.

## References

- `docs/architecture/data-model.md` section 2.1 (Stable identifiers), section 2.3 (Facts, assumptions, and interpretations are different objects), section 4.2 (ConfidenceLevel), section 4.4 (SourceOrigin), section 10 (ContextClaim), section 39 open questions 1 and 7
- `docs/architecture/agent-design.md` section 7 (Evidence requirements; Prohibited operations), section 14 (Evidence hierarchy)
- `docs/architecture/decision-log.md` DEC-006, DEC-009
- `requirements/README.md` ("Applicability vocabulary")
