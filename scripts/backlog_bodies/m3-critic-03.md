## Context

`docs/architecture/agent-design.md` section 15 gives the critic recommendation authority
only: it may recommend revision, rejection, consolidation, or reclassification, and it may
not directly approve findings or rewrite objects without preserving lineage. Section 27
requires the orchestrator to enforce maximum node executions, model calls, retries, cost,
duration, and explicit permitted transitions, and gives the worked example: "The critic may
recommend that a threat be reconsidered. It may not automatically start an unlimited
threat-generation and criticism loop." Nothing implements that boundary today, and it is
the boundary that keeps a quality-control agent from becoming a cost-unbounded one.

## Scope

- Add `src/trace_ai/workflow/nodes/critique_validation.py`. It is deterministic and makes
  no model call.
- Validate critiques: schema; the target object resolves and matches the declared
  `subject_type`; `recommended_action` is present; duplicate critiques against the same
  target with the same type are detected.
- Detect the section 15 failure conditions that are deterministically checkable: critiques
  lacking target objects; critiques lacking recommendations; and critique volume
  disproportionate to the reviewed object count, above a configured ratio.
- Route recommendations without executing them. A critique produces a recommendation
  record against its target and never mutates the target.
  `docs/architecture/data-model.md` section 32 requires the lineage from threat through
  mapping and evidence assessment to critique and finding to stay traceable, and an
  in-place mutation destroys it.
- Enforce loop prevention per section 27. A recommendation that would re-invoke an
  upstream node is counted against a configured budget and, past that budget, routed to
  human review rather than executed. `AssessmentConfiguration` already carries
  `maximum_model_calls`, `maximum_cost`, and `maximum_retries_per_node`.
- Persist validated critiques through the M1 persistence layer, since section 22 states
  that agents never write authoritative records.
- Surface the section 15 human-review triggers: the critic challenges a likely
  high-severity conclusion; two agents produce materially conflicting interpretations; a
  reviewer decision would affect multiple findings; the critic identifies a major
  architecture gap.
- Implement the budget check as ordinary Python. DEC-007 leaves LangGraph Proposed, so
  this must not depend on framework configuration, and DX-06 may change the orchestrator
  underneath it.

## Acceptance criteria

- [ ] The node makes no model call and imports no provider SDK.
- [ ] A critique whose `subject_id` does not resolve, or whose object type does not match
      the declared `subject_type`, is rejected with both values named.
- [ ] No code path allows a critique to mutate its target object. A test asserts the target
      is unchanged, field for field, before and after routing.
- [ ] A recommendation that would re-invoke an upstream node is bounded by the configured
      budget and is routed to human review past it, never executed automatically.
- [ ] Critique volume above the configured ratio is flagged as a possible section 15
      failure rather than passed through silently.
- [ ] Duplicate critiques against the same target with the same type are detected.
- [ ] Lineage from critique to target is preserved and queryable, per
      `docs/architecture/data-model.md` section 32.
- [ ] A test asserts that zero critiques is a valid, passing outcome that produces no
      warning.
- [ ] The budget check imports no orchestration framework, so it survives whatever DX-06
      decides.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Executing merges or reclassifications. `docs/architecture/agent-design.md` section 16
  assigns those to Finding Consolidation in M4.
- The human finding review checkpoint, fixed by DEC-005 and built in M4.
- Full orchestrator execution limits across the workflow, which DX-06 covers.
- Severity changes, owned by DX-11.

## References

- `docs/architecture/agent-design.md` section 15 (Allowed operations; Prohibited
  operations; Failure conditions; Human-review triggers), section 16 (Finding
  Consolidation Node — the boundary this node must not cross), section 22 (Write model),
  section 27 (Loop Prevention)
- `docs/architecture/data-model.md` section 24 (Critique), section 32 (Object Lineage),
  section 6 (AssessmentConfiguration), section 33 (Schema Validation)
- `docs/architecture/current-architecture.md` section 5.3 (Workflow Orchestrator),
  section 11 (Error Handling)
- `docs/architecture/decision-log.md` DEC-005, DEC-006, DEC-007
