## Context

`docs/architecture/agent-design.md` section 14 defines the Evidence Validation Agent: it
evaluates whether proposed security conclusions are sufficiently supported by available
evidence, and it is the fourth of the six capped agents at section 36. Section 35 Phase 3
groups it with the mapping agent under the success condition "Trace distinguishes among
satisfied, unverified, and unmet requirements without treating missing documentation as
proof of weakness." It runs after mapping validation and before critical review, per
section 3.

Its distinguishing responsibility is the one the project is built around: it may recommend
that a candidate be downgraded to a question, and it may recommend documentation-gap
treatment. Those are the two DEC-009 escape hatches, and this is the agent that proposes
taking them.

## Scope

**Prompt artifact.** Add `prompts/evidence/validate-evidence-v1.md`, following the
thirteen sections of section 24 and composing the three shared prompts created with the
threat agent. `prompts/shared/evidence-policy-v1.md` carries most of this agent's
substance, so this prompt should be thin and specific rather than restating it.

**Prompt content specific to this agent.** Encode, from section 14:

- The evidence hierarchy as a labelled ranking the rationale must cite, with section 14's
  own caveat that it is guidance and not a universal scoring formula.
- The prohibitions: creating evidence; altering quoted evidence; assuming undocumented
  implementation details; approving final findings; using model confidence as a substitute
  for evidence; treating repeated model claims as independent corroboration.
- The requirement to explain why evidence is direct, indirect, or contextual, matching the
  `EvidenceStrength` vocabulary at `docs/architecture/data-model.md` section 4.3.
- The instruction to recommend continuing, revising, or stopping a candidate conclusion,
  and to recommend downgrade to a question or documentation-gap treatment where the issue
  is inability to verify rather than a supported weakness.

**Code.** Add `src/trace_ai/agents/evidence_validation.py`. It assembles the payload
section 23 specifies for this agent — the specific conclusion being tested, relevant
evidence, contradictory evidence, and the evidence policy — rather than the whole
assessment. It calls the model through the M2 abstraction layer, parses into
`EvidenceAssessmentProposal`, and applies bounded retry per section 26. Section 14 lists
its retry conditions: schema failure, omitted evidence references, failure to distinguish
support from inference, and unaddressed contradictions. Generation uses low creativity per
section 29. The agent version is `evidence-validation-v1` per section 33. Emit an
`ExecutionRecord` per invocation.

Contradictory evidence is represented per DX-14. `docs/architecture/agent-design.md`
section 38 question 8 asks how contradictory evidence should be presented to agents, and
this agent is the one for which the answer matters most.

## Acceptance criteria

- [ ] The prompt file exists at the section 34 path and carries all thirteen section 24
      sections.
- [ ] The composed prompt includes `prompts/shared/evidence-policy-v1.md` exactly once and
      does not restate its content inline.
- [ ] Every emitted assessment cites at least one existing evidence reference, or carries
      `validation_status: not_evaluated` with a stated reason.
- [ ] An assessment whose rationale quotes evidence text that does not match the referenced
      `EvidenceReference.quoted_text` is rejected. Section 14 makes "The rationale
      misquotes or materially changes evidence" a failure condition, and this check is
      deterministic.
- [ ] Fixture, contradictory documentation: the ForgeFlow source-retention contradiction
      at `demo/forgeflow/forgeflow-scenario.md` section 16.1 produces a `contradicted`
      assessment and no silently chosen winner. Scenario section 16.1 states that Trace
      must not silently choose the safer statement.
- [ ] Fixture, missing documentation: a mapping resolving to `unverified` because the
      documentation is silent produces a recommendation of question or documentation-gap
      treatment, and never an `unsupported` classification that reads as a weakness.
- [ ] Fixture, repeated claims: two mappings asserting the same conclusion from the same
      single evidence reference do not raise the classification. Section 14 makes
      "Evidence quantity is mistaken for evidence quality" a failure condition.
- [ ] A test asserts the agent emits no `Finding` and approves nothing.
- [ ] Retry routing is tested for each of the four retry conditions section 14 names.
- [ ] No test under `tests/unit/` makes a live model call, and `uv run pytest` passes with
      no API key configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Deterministic validation and persistence of the agent's output, which is the next issue
  in this component.
- Finding consolidation and severity, both M4 or DX-11.
- Approving findings. Section 14 prohibits it and DEC-005 reserves approval for the human
  checkpoint.

## References

- `docs/architecture/agent-design.md` section 14 (Evidence Validation Agent — full
  contract, particularly Evidence hierarchy, Prohibited operations, Failure conditions,
  Retry behavior), section 3 (Workflow Overview — placement), section 23 (Retrieval Design
  — Evidence Validation Agent), section 24, section 26, section 29, section 33, section 34,
  section 35 (Phase 3), section 36 (MVP Agent Set), section 38 question 8
- `docs/architecture/data-model.md` section 20 (EvidenceAssessment), section 4.3
  (EvidenceStrength), section 4.7 (ValidationStatus), section 8 (EvidenceReference —
  Validation rules)
- `docs/architecture/current-architecture.md` section 5.9 (Evidence Validation)
- `docs/architecture/decision-log.md` DEC-005, DEC-009
- `demo/forgeflow/forgeflow-scenario.md` section 15 (Intentional Ambiguities), section 16
  (Intentional Contradictions)
