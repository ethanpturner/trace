## Context

`SourceObservation` has a full specification and no work item. `data-model.md` section 10a
defines its purpose, ten fields, two `kind` values, four validation rules, and its relationship
to `ContextClaim.contradicted`. Section 2.1 carries the `obs-` prefix. DEC-021 settles that
contradictions and detected prompt-injection attempts are one object of this type rather than
two. DEC-027 gives every benchmark scenario an `expected-observations.yaml` to grade them
against. Section 40 now lists it seventh among the objects to build first.

Nothing in the backlog creates it. The M2 manifest has issues for the architecture objects,
`ContextClaim`, `Question`, `SystemContext`, and `ReviewerDecision`; there is no sixth for
observations, because the backlog was seeded the day before DEC-021 was recorded.

The gap is not only a missing model. Several M2 bodies — `m2-context-objects-02`,
`m2-context-extractor-01` through `-03` and `-06`, `m2-context-review-01` through `-03`,
`m2-runtime-04` — mention contradictions or injection attempts in the terms that were current
before DEC-021, when they were two separate concerns rather than one object with a `kind`. Those
descriptions are not wrong about what must happen; they are wrong about what it produces.

Without this issue the extractor step has nowhere to put a contradiction, the review package has
nothing to show the reviewer, and the ForgeFlow scenario — which expects contradictions and
contains a deliberate injection fixture — has an expected-output file that nothing populates.

## Scope

- Add `SourceObservation` to `src/trace_ai/domain/`, conforming to section 10a. Register it in
  `tests/unit/test_data_model_conformance.py` as `IMPLEMENTED` in the same change; the registry
  entry exists and is currently `PLANNED`.
- Implement the four validation rules from section 10a as schema-level constraints, not as
  conventions a caller is expected to honour:
  - `contradiction` requires at least two evidence references.
  - `injection_attempt` requires at least one.
  - No severity field, and no path by which an observation becomes a `Finding`.
  - A contradiction does not resolve itself.
- Model `kind` as an enumerated type. Section 10a lists its values under a `## Kind values`
  heading rather than in section 4, so it belongs on the object like `ContextClaim`'s status
  vocabulary rather than in `domain/enums.py`.
- Implement the one-directional link to `ContextClaim`: `ContextClaim.contradicted` means an
  observation references that claim in `subject_claim_ids`, and the claim carries no field naming
  what contradicts it. The direction is the point — it is what stops the two disagreeing about
  whether they disagree — so a test should assert there is no reverse field.
- Review the M2 bodies listed above and correct the ones that describe contradictions and
  injection attempts as separate outputs. This is an editorial pass over issue text, not a
  redesign of those issues.

## Acceptance criteria

- [ ] `SourceObservation` conforms to section 10a and the conformance guard is switched on for
      section `10a`.
- [ ] A `contradiction` with one evidence reference fails validation; with two it passes.
- [ ] An `injection_attempt` with no evidence reference fails validation.
- [ ] The model has no severity field, and a test asserts it, because the absence is a DEC-021
      rule rather than an omission.
- [ ] `ContextClaim` gains no field naming what contradicts it. A test asserts the link is
      one-directional.
- [ ] Setting `ContextClaim.status` to `contradicted` without a referencing observation is
      either impossible or detected. Which of the two is a design question for this issue.
- [ ] The injection fixture in `demo/forgeflow/input/sample-repository-notes.md` can be
      represented as a `SourceObservation` of kind `injection_attempt`. No agent is required to
      produce one for this issue; constructing it by hand in a test is enough.
- [ ] Every M2 issue body describing contradictions or injection attempts as separate outputs is
      corrected, or is listed here with a reason it was left alone.
- [ ] `uv run mypy` passes strict.

## Out of scope

- The Context Extraction agent producing observations. That is `m2-context-extractor-05`; this
  issue provides the object it proposes.
- Deciding how a contradiction is detected. DEC-021 settles the representation, not the method.
- `expected-observations.yaml` for ForgeFlow, which is `m4-evaluation-01` and needs the whole
  truth set authored together.
- Renumbering section 10a into its own section. The lettered number is untidy and harmless, and
  changing it would renumber every section after it.

## References

- `docs/architecture/data-model.md` sections 10a, 10 (`ContextClaim.contradicted`), 2.1, 40
- `docs/architecture/decision-log.md` DEC-021, DEC-027
- `tests/unit/test_data_model_conformance.py`, the `10a` registry entry
- `demo/forgeflow/input/sample-repository-notes.md`, the injection fixture
- Issue #45, which found section 40 missing the object
