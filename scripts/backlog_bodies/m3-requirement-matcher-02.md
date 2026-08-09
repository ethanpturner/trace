## Context

Nothing in the design corpus specifies how requirements reach the mapping step.
`docs/architecture/agent-design.md` section 23 says the Mapping Agent receives "Relevant
requirements" without defining relevance; section 22 lists "Retrieve requirements by
applicability filters" as a capability without naming a filter; section 38 questions 3 and
4 leave batch size and the filter-then-retrieve question open;
`docs/architecture/current-architecture.md` section 19 question 13 asks how applicability
should be determined. DX-10 resolves the shape: requirement selection is deterministic
application code, and the Control mapper remains the single model-assisted agent for the
mapping step. That preserves the six-agent cap at
`docs/architecture/agent-design.md` section 36. This issue implements the deterministic
half. If DX-10 is later overturned in favour of a second model-assisted agent, this
component is replaced rather than extended.

Four facts about the catalog as it exists constrain what deterministic selection can do,
and none of them is discoverable from the design documents alone.

- `applicable_technologies` is populated on zero of the 23 requirements. It is the only
  structured filter field in the section 17 schema and it carries no data.
- `applicable_conditions` and `non_applicable_conditions` are free text — 45 and 44
  distinct strings in version 0.1. They are model-readable and not filterable.
- Vector infrastructure is deferred by `docs/architecture/current-architecture.md`
  section 17, so semantic retrieval has no substrate.
- `category` is the only usable structured axis: 11 primary categories, list-typed, so a
  requirement carries several.

## Scope

- Add `src/trace_ai/services/requirements/selection.py` producing an ordered candidate
  requirement list for a threat, per the DX-10 strategy.
- Selection is pure and side-effect free. It makes no model call, performs no database
  write, and reads no filesystem path outside the catalog loader.
- Record why each requirement entered the candidate set, in machine-readable form, so a
  requirement the mapping agent later declines is distinguishable from one that was never
  offered. This is the input side of the applicability-precision metric in section 12.
- Record the requirements excluded and the reason, in a debug artifact governed by
  `AssessmentConfiguration.retain_debug_artifacts`. A requirement excluded silently is a
  false negative that no metric can see.
- Do not attempt to evaluate free-text `applicable_conditions` or
  `non_applicable_conditions` deterministically. Where a condition can be answered from
  structured approved-context facts, it may inform ordering; it must not by itself exclude
  a requirement from the candidate set unless DX-10 says otherwise. Excluding on a
  free-text match is how a genuine mapping is lost before any agent sees it.
- Carry `catalog_version` on the candidate set so `WorkflowRun.prompt_versions` and the
  caching rules in section 30 can key on it.
- **State the threat-gating consequence in the module docstring and in the PR
  description.** `docs/architecture/data-model.md` section 19 makes `threat_id` required
  on `ControlMapping`, so a requirement is only ever evaluated through a threat. A
  requirement that applies to the system but that no generated threat reaches is never
  evaluated and appears in no output. That is a coverage limit of the current schema, not
  a defect of this selector, and it must be visible to whoever reads the results.

## Acceptance criteria

- [ ] Selection is deterministic. The same threat and catalog version yield an identical
      ordered candidate list across runs.
- [ ] Selection makes no model call and imports no provider SDK.
- [ ] Every candidate carries a machine-readable reason for inclusion.
- [ ] Exclusions and their reasons are recorded when `retain_debug_artifacts` is true.
- [ ] The candidate set carries `catalog_version`.
- [ ] A fixture test over a ForgeFlow webhook-replay threat asserts that
      `req-WEBHOOK-001` and `req-WEBHOOK-002` are both candidates.
- [ ] A test asserts that a requirement is not excluded on the strength of a free-text
      `non_applicable_conditions` string match alone.
- [ ] A test asserts that a threat producing an empty candidate set is a valid outcome
      that raises no error, since the catalog is deliberately small and
      `requirements/README.md` states that none of its requirements is intended to apply
      to every component.
- [ ] The threat-gating consequence is stated in the module docstring, naming
      `docs/architecture/data-model.md` section 19 as the source of the constraint.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The applicability judgment itself, which is the mapping agent's.
- Semantic or embedding-based retrieval.
- Any change to how `applicable_conditions` is represented. That is
  `docs/architecture/data-model.md` section 39 question 5 and stays open.
- Changing `ControlMapping.threat_id` to optional. That is a data-model change and needs
  its own decision entry; this issue only makes the consequence visible.

## References

- `docs/architecture/agent-design.md` section 22 (Tool Access Model — Permitted
  agent-facing retrieval), section 23 (Retrieval Design — Mapping Agent), section 12
  (Prohibited operations; Failure conditions; Evaluation criteria — Applicability
  precision), section 30 (Caching), section 36 (MVP Agent Set), section 38 questions 3
  and 4
- `docs/architecture/data-model.md` section 17 (Requirement), section 19 (ControlMapping —
  Fields), section 6 (AssessmentConfiguration — retain_debug_artifacts), section 26
  (WorkflowRun), section 39 question 5
- `docs/architecture/current-architecture.md` section 17 (Deferred Capabilities),
  section 19 question 13
- `requirements/README.md` — *How to read a requirement*, *Applicability vocabulary*,
  *Version 0.1*
- `requirements/0.1/*.yaml`
- `journal/2026-08-08-requirements-catalog.md` — *Deliberately not decided*
