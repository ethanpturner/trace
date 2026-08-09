## Context

`docs/architecture/agent-design.md` section 15 defines the Critical Review Agent, which is
"not an adversarial chatbot" but "a structured quality-control agent" challenging the
draft analysis before findings are consolidated. It is the fifth of the six capped agents
at section 36 and the first deliverable of section 35 Phase 4, whose success condition is
"Trace produces a small, defensible set of provisional findings, questions, and
documentation gaps."

Its value is explicitly unproven. `docs/product/roadmap.md` Stage 4 sets a decision gate —
"If the critic or another agent does not improve results, remove or defer it" — and
`docs/architecture/agent-design.md` section 40 lists "The critic creates noise" as a
simplification trigger. Build it so it can be removed cleanly.

## Scope

**Prompt artifact.** Add `prompts/critique/challenge-analysis-v1.md`, following the
thirteen sections of section 24 and composing the three shared prompts created with the
threat agent.

**Prompt content specific to this agent.** Encode, from section 15:

- The twelve things the critic looks for, of which two matter most here: "Documentation
  gaps mislabeled as vulnerabilities" and "Ignored inherited controls". The first is the
  critic's DEC-009 backstop and the second is its DX-15 backstop.
- The prohibitions: no directly approving findings; no rewriting objects without
  preserving lineage; no criticism without identifying the target object; no rejecting
  evidence merely because it disagrees with an earlier agent; no increasing complexity for
  its own sake; no acting as an unrestricted second full assessment.
- The instruction that every critique names a target and carries an actionable
  recommendation drawn from the `RecommendedAction` vocabulary.
- The instruction that the absence of critiques is an acceptable result, so the agent has
  no incentive to manufacture volume. Section 15 makes "generates large quantities of
  superficial criticism" a failure condition.

**Code.** Add `src/trace_ai/agents/critical_review.py`. It assembles the bounded review
group DX-08 fixes, drawing on the object set that decision identifies as the critic's
inputs, and passes the smallest useful context per section 23 rather than the whole
assessment. It calls the model through the M2 abstraction layer, parses into
`CritiqueProposal`, and applies bounded retry per section 26 and section 15, which lists
schema failure, absent recommendations, generic critiques, and failure to inspect evidence
or mappings as its retry conditions. Generation uses low to moderate creativity per
section 29. The agent version is `critical-review-v1` per section 33. Emit an
`ExecutionRecord` per invocation.

## Acceptance criteria

- [ ] The prompt file exists at the section 34 path and carries all thirteen section 24
      sections.
- [ ] The composed prompt includes each shared prompt block exactly once.
- [ ] Fixture, documentation gap mislabelled: a mapping asserting a weakness where the
      documentation is merely silent draws a `documentation_gap_only` critique.
- [ ] Fixture, ignored inherited control: a mapping ignoring the ForgeFlow managed database
      encryption inheritance draws an `ignored_inherited_control` critique, per
      `demo/forgeflow/forgeflow-scenario.md` sections 12.2 and 14.2.
- [ ] Fixture, restraint: given a well-supported mapping and assessment set, the agent
      produces few or no critiques and the test treats that as success.
      `docs/architecture/evaluation-plan.md` section 20 forbids optimising for output
      volume, and section 15 makes superficial volume a failure condition.
- [ ] A critique that restates existing analysis without challenging it triggers a retry,
      per section 15 Retry behavior.
- [ ] Every emitted critique names a target object that resolves, and carries a
      recommendation. A proposal missing either fails validation.
- [ ] The agent proposes no object outside `Critique`, and proposes no threat unless DX-08
      permits it, in which case the proposal is bounded per that decision.
- [ ] A test asserts the agent approves nothing and emits no `Finding`.
- [ ] The review group passed to the model contains only the objects DX-08 fixes, and a
      test asserts the whole assessment is not passed.
- [ ] No test under `tests/unit/` makes a live model call, and `uv run pytest` passes with
      no API key configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Applying critique recommendations, which is the next issue in this component.
- Finding Consolidation and Severity Support, both M4.
- The critic-enabled versus critic-disabled comparison, which is
  `docs/architecture/evaluation-plan.md` section 14 in Stage 5.
- Approving anything. Section 15 prohibits it and DEC-005 reserves finding approval for
  the human checkpoint.

## References

- `docs/architecture/agent-design.md` section 15 (Critical Review Agent — full contract),
  section 3 (Workflow Overview — placement), section 23 (Retrieval Design — Critical
  Review Agent), section 24, section 26, section 27 (Loop Prevention), section 29,
  section 33, section 34, section 35 (Phase 4), section 36 (MVP Agent Set), section 40
  (Architecture Constraint)
- `docs/architecture/data-model.md` section 24 (Critique), section 20
  (EvidenceAssessment), section 19 (ControlMapping)
- `docs/architecture/current-architecture.md` section 5.10 (Critical Review)
- `docs/architecture/evaluation-plan.md` section 14 (Workflow Evaluation), section 20
- `docs/product/roadmap.md` Stage 4 (Deliverables; Decision gate)
- `demo/forgeflow/forgeflow-scenario.md` sections 12.2, 14, 22
