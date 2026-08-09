## Context

The Context Extraction Agent is designed to propose Component, Actor, Asset, DataFlow, and TrustBoundary objects, with the application — not the agent — validating and persisting them (`docs/architecture/agent-design.md` section 7 Outputs, section 22 Write model). `docs/architecture/data-model.md` sections 11 through 15 are authoritative for the field names and types of these five objects. Nothing downstream can be built until they exist as Pydantic models, because `SystemContext` holds only identifier lists that point at them (`docs/architecture/data-model.md` section 9).

## Scope

New package `src/trace_ai/domain/models/`, one module per object, built on the shared base and enumerations delivered by M1 foundations:

- `component.py` — `Component`: `id`, `assessment_id`, `name`, `component_type`, `description`, `technology`, `ownership`, `deployment_zone`, `internet_accessible`, `externally_managed`, `data_classifications`, `authentication_mechanisms`, `authorization_mechanisms`, `evidence_ids`, `status` (`data-model.md` section 11).
- `actor.py` — `Actor`: `id`, `assessment_id`, `name`, `actor_type`, `trust_level`, `capabilities`, `authentication_method`, `evidence_ids` (section 13). Section 13 defines no `status` field; adding one is a design change requiring a decision-log entry.
- `asset.py` — `Asset`: the section 12 field list, including `confidentiality_impact`, `integrity_impact`, and `availability_impact`.
- `data_flow.py` — `DataFlow`: the section 14 field list, including `crosses_trust_boundary_ids` and `internet_exposed`.
- `trust_boundary.py` — `TrustBoundary`: the section 15 field list.

Identifier allocation follows the scheme settled in DX-02 and uses the prefixes in `data-model.md` section 2.1: `cmp-`, `ast-`, `df-`, `tb-`. Models do not mint their own identifiers.

Two sub-decisions are settled inside this issue and recorded in `docs/architecture/decision-log.md`, because the corpus leaves both open:

1. **The `component_type` vocabulary.** `data-model.md` section 11 heads its list "Component-type examples", not values. `demo/forgeflow/input/structured-system-input.yaml` uses `web_application`, `managed_database`, `managed_cache`, `managed_storage`, `managed_security_service`, and `internal_application`, of which only `service` appears in the data-model list. A closed enum would reject the project's own benchmark fixture. Choose an open string with normalization or an extended enum, and record which.
2. **Actor's place in the context baseline.** `SystemContext` (section 9) has no `actor_ids` field, `data-model.md` section 40 omits Actor from the initial implementation priority, and section 39 open question 4 asks whether actors should be first-class at all — while `agent-design.md` section 7 lists Actor objects as extractor output and `docs/product/roadmap.md` Stages 1 and 2 both list Actor. Either add `actor_ids` to `SystemContext` or defer Actor out of M2. An extracted actor that nothing references is worse than an absent one.

Two validation rules belong on the models rather than on the validation node:

- `DataFlow.source_component_id` must differ from `DataFlow.destination_component_id` (section 14 validation rules).
- `DataFlow.encryption_in_transit` and `DataFlow.authentication` represent unknown as an explicit `unknown` value, never as `false` or as absence. This is DEC-009 expressed at field level.

Tests live in `tests/unit/test_domain_models.py` and follow the conventions in `tests/unit/test_requirements_catalog.py`: parametrized per object, with failure messages naming the offending object and field.

## Acceptance criteria

- [ ] Component, Actor, Asset, DataFlow, and TrustBoundary each exist as a Pydantic model whose field names and required or optional status match `data-model.md` sections 11 through 15 exactly.
- [ ] A test asserts, per object, that the model's field set equals the section's field set, so drift from the data model fails CI rather than passing silently.
- [ ] A `DataFlow` with equal source and destination component identifiers is rejected.
- [ ] A `DataFlow` constructed with unknown transport encryption serialises to an explicit `unknown`, and a test asserts it does not serialise to `false` or `null`.
- [ ] `Actor` carries no `status` field, or a decision-log entry explains why one was added.
- [ ] The `component_type` decision is recorded in `docs/architecture/decision-log.md`, and every component type used in `demo/forgeflow/input/structured-system-input.yaml` is accepted by the model.
- [ ] The Actor decision is recorded in `docs/architecture/decision-log.md`, and if Actor is retained then `SystemContext.actor_ids` exists.
- [ ] Identifiers are allocated by the application using the DX-02 scheme and the section 2.1 prefixes; a test asserts no model accepts a caller-supplied identifier for a newly created object.
- [ ] `uv run mypy` passes under strict mode and `uv run ruff check .` passes.

## Out of scope

- Persistence. These are domain models only; database mapping is the M1 persistence issue's concern.
- Threat, Control, ControlMapping, Finding, Critique, and EvidenceAssessment, which belong to later milestones.
- Semantic duplicate detection. `agent-design.md` section 8 asks only for exact duplicates at this stage, and `data-model.md` section 39 open question 8 is unresolved.
- Any model call.

## References

- `docs/architecture/data-model.md` section 2.1 (Stable identifiers), section 4 (Shared Types), sections 11 through 15 (Component, Asset, Actor, DataFlow, TrustBoundary), section 33 (Schema Validation), section 40 (Initial Implementation Priority)
- `docs/architecture/agent-design.md` section 7 (Context Extraction Agent), section 8 (Context Validation Node), section 22 (Tool Access Model)
- `docs/architecture/decision-log.md` DEC-006, DEC-009
- `docs/product/roadmap.md` Stage 1 "Core application models", Stage 2 "Context Extraction Agent"
- `demo/forgeflow/input/structured-system-input.yaml`
- `tests/unit/test_requirements_catalog.py` (test conventions)
