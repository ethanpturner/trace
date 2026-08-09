## Context

`docs/architecture/agent-design.md` section 23 requires each agent to receive the smallest
useful context and names what the Mapping Agent gets: one or a small group of threats,
relevant requirements, related controls, and applicable context. Section 22 states that
agents receive evidence and domain objects through an application-controlled interface and
lists what they must not have — internet, shell, arbitrary filesystem, database writes,
cloud credentials, dynamic code execution. Agents therefore call nothing. The application
assembles a payload and passes it. That assembler does not exist, and without it the
mapping agent has no defined input.

## Scope

- Add `src/trace_ai/services/requirements/payload.py` assembling the mapping payload from
  the candidate requirement set, the threat under evaluation, the related approved context
  objects, existing `Control` objects associated with the affected components, and the
  supporting evidence references.
- The payload is a plain data structure with no callable surface. There is no retrieval
  function the agent can invoke, and a test asserts that.
- Include, per requirement, the fields the mapping step is required to reason over:
  `statement`, `rationale`, `applicable_conditions`, `non_applicable_conditions`,
  `acceptable_implementations`, `evidence_expectations`, and `common_false_positives`.
  Omitting `common_false_positives` from the payload would make DEC-011 unenforceable at
  the point it matters, since DEC-011 records under Tradeoffs that nothing yet enforces
  the field is consulted.
- Label `acceptable_implementations` in the payload as a non-exhaustive list of mechanism
  classes rather than an approved set, so the framing travels with the data and does not
  rely on prompt wording alone. `requirements/README.md` states that it is non-exhaustive
  by construction, and section 12 makes treating one example as the only valid control a
  prohibited operation.
- Carry `catalog_version`, the threat identifier, and the assessment identifier on the
  payload so the caching rules in section 30 and the `ExecutionRecord` inputs in
  `docs/architecture/data-model.md` section 27 can be keyed and recorded.
- Enforce a payload size bound consistent with the DX-10 batch decision, and fail loudly
  rather than truncating silently. A truncated payload produces a mapping run that looks
  complete and is not.
- Record the assembled input object identifiers for the `ExecutionRecord`
  `input_object_ids` field.

## Acceptance criteria

- [ ] The payload contains no callable, no open file handle, and no database session. A
      test asserts the assembled object is inert.
- [ ] Every requirement in the payload carries `common_false_positives` when the catalog
      defines it, and a test asserts the field survives assembly.
- [ ] `acceptable_implementations` is carried with an explicit non-exhaustive marker.
- [ ] The payload carries `catalog_version`, `threat_id`, and `assessment_id`.
- [ ] Exceeding the configured payload bound raises rather than truncating, and the error
      names what was dropped.
- [ ] The payload contains only approved context objects. A test asserts that a context
      object whose status is not approved is excluded, since
      `docs/architecture/agent-design.md` section 9 states that threat analysis and
      everything after it works from the approved baseline.
- [ ] The payload contains no source-document text beyond the quoted evidence excerpts it
      references, per section 23's context-minimisation rationale.
- [ ] `input_object_ids` is populated for the `ExecutionRecord`.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The model call and prompt composition, which belong to the mapping agent issue.
- Evidence retrieval and normalisation, settled by DX-03 and implemented in M2.
- A general-purpose retrieval service. Section 22 describes an interface; the MVP needs
  only this assembler.

## References

- `docs/architecture/agent-design.md` section 22 (Tool Access Model — Permitted
  agent-facing retrieval; Agents should not initially receive; Write model), section 23
  (Retrieval Design — Mapping Agent), section 12 (Inputs; Prohibited operations),
  section 9 (Human Context Review — Workflow rule), section 30 (Caching)
- `docs/architecture/data-model.md` section 17 (Requirement), section 18 (Control),
  section 27 (ExecutionRecord)
- `docs/architecture/decision-log.md` DEC-011
- `requirements/README.md` — *How to read a requirement*
