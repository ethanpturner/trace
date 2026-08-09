## Context

`docs/architecture/agent-design.md` section 8 defines a deterministic node between the extractor and the human checkpoint, with ten enumerated responsibilities and one constraint that shapes the whole design: the node does not reinterpret architecture or invent corrections. It reports and routes; it does not fix. This is also where DEC-009 is enforced structurally rather than by prompt wording, which matters because a prompt instruction is advisory and a validator is not.

## Scope

`src/trace_ai/workflow/nodes/context_validation.py`, implementing each responsibility in `agent-design.md` section 8:

- Schema validation of every converted object.
- Identifier uniqueness within the assessment.
- Referential integrity through `SystemContext.validate_against`: every referenced component, asset, trust boundary, evidence reference, and claim subject exists.
- Exact-duplicate detection across components, assets, data flows, and trust boundaries. Exact only — `agent-design.md` section 11 permits semantic comparison for threats but requires the merge decision to remain explicit and traceable, and `data-model.md` section 39 open question 8 is unresolved.
- Invalid data flows: self-referencing flows, dangling endpoints, and unknown transport encryption represented as false rather than as `unknown` (`data-model.md` section 14 validation rules).
- Evidence requirements: `documented` and `inferred` claims carry evidence; `assumed` and `unknown` claims are not penalised for lacking it. A claim is never silently downgraded to make it pass.
- Enumerated-value normalization, applying the `component_type` policy recorded with the architecture-object models.
- Missing required fields, reported per object and field.
- Confidence ranges, per the model DX-19 settles.
- A workflow-transition guard refusing to mark the context ready for review while a blocking error is outstanding.

Outputs, per `agent-design.md` section 8: validated context objects, structured validation errors, retry instructions, and the human-review package. The package is built with the shared builder from the checkpoint machinery.

Human-review triggers from `agent-design.md` section 7 are computed here and attached to the package: contradictory high-impact claims, unclear core system purpose, uncertain major trust boundaries, ambiguous authentication or authorization architecture, a significant component that is inferred rather than documented, and material change from a prior approved version.

Errors are classified using the workflow error taxonomy so the extraction node routes on them rather than inspecting messages.

## Acceptance criteria

- [ ] Every responsibility listed in `agent-design.md` section 8 has at least one test, and each test names the responsibility it covers.
- [ ] Validation errors are returned as structured objects carrying the offending object identifier, the field, and the rule violated, rather than raised on the first failure.
- [ ] The node mutates nothing it validates; a test asserts input objects are unchanged after a run that produces errors.
- [ ] A claim with status `unknown` and no evidence passes validation, and the test docstring cites DEC-009.
- [ ] A claim with status `documented` and no evidence produces a validation error and a retry instruction, not a silent status downgrade.
- [ ] Two components with identical normalised names produce a duplicate error and are not merged.
- [ ] A data flow with unknown encryption represented as false produces an error.
- [ ] Every error is classified as retryable or non-retryable using the workflow error taxonomy.
- [ ] The human-review package lists the triggers from `agent-design.md` section 7 that fired, with the objects that caused each.
- [ ] The node makes no model call; a test asserts the model seam is never invoked.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Semantic or embedding-based duplicate detection.
- Correcting or completing the architecture, explicitly forbidden by `agent-design.md` section 8.
- Rendering the review package for a reviewer, which the context review issues cover.
- Threat validation and mapping validation (`agent-design.md` sections 11 and 13).

## References

- `docs/architecture/agent-design.md` section 7 (Failure conditions; Human-review triggers), section 8 (Context Validation Node), section 11 (Threat Validation Node — Important constraint), section 26 (Retry Policy)
- `docs/architecture/data-model.md` section 9 (SystemContext), section 14 (DataFlow — Validation rules), section 33 (Schema Validation), section 39 open question 8
- `docs/architecture/current-architecture.md` section 2.6 (Deterministic where practical)
- `docs/architecture/decision-log.md` DEC-006, DEC-009
- `docs/product/roadmap.md` Stage 2 "Context validation"
