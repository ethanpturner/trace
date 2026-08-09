## Context

`docs/architecture/agent-design.md` section 12 defines the agent that determines which
security requirements apply to each threat and how documented or inherited controls affect
satisfaction. It is the core false-positive-reduction mechanism named in
`docs/product/roadmap.md` Stage 3, and section 35 Phase 3 sets its success condition:
"Trace distinguishes among satisfied, unverified, and unmet requirements without treating
missing documentation as proof of weakness."

Under DX-10 this is the single model-assisted agent for the mapping step. The requirement
matcher supplies a deterministic candidate set and an assembled payload; this agent judges
applicability and satisfaction. That split keeps the agent count at the six fixed by
section 36.

## Scope

**Prompt artifact.** Add `prompts/controls/map-requirements-controls-v1.md`, following the
thirteen sections of `docs/architecture/agent-design.md` section 24 and composing the
three shared prompts created with the threat agent.

**Four constraints the prompt must encode explicitly.** Each is a stated failure condition
rather than a stylistic preference.

1. `acceptable_implementations` is non-exhaustive by construction. It lists mechanism
   classes, not approved products, and an implementation absent from the list is not
   thereby wrong. Section 12 makes "Treat one implementation example as the only valid
   control" a prohibited operation and "Requirement examples are treated as mandatory
   implementations" a failure condition; section 13 requires the validation node to catch
   it. The prompt states this in its own words and demonstrates it with a worked
   counter-example: a control that satisfies `req-AUTH-001` through a mechanism the
   requirement's list does not name.
2. Missing documentation is never proof of absence, per DEC-009. Silence resolves to
   `unverified`, a Question, or a DocumentationGap, and never to `unmet`. The prompt
   carries the section 12 vocabulary for insufficient evidence: `unverified`, `unknown`,
   `conditionally_applicable`, `requires_confirmation`.
3. `common_false_positives` is not `non_applicable_conditions`, per DEC-011. The prompt
   distinguishes them by name: the latter means the requirement does not apply at all; the
   former means the requirement applies, the documentation is silent, and a specific
   conclusion is still wrong. The prompt instructs the agent to check
   `common_false_positives` before proposing any negative conclusion and to state which
   entry it matched when it declines to conclude, so the suppression is recorded per DX-09
   rather than discarded.
4. Requirements are applied selectively. The prompt forbids applying every candidate
   requirement to every component and requires a distinct `applicability_reason` per
   mapping that refers to the requirement's `applicable_conditions` or
   `non_applicable_conditions`.

**Code.** Add `src/trace_ai/agents/requirement_control_mapping.py` covering the model call
through the M2 abstraction layer, a structured parse into `ControlMappingProposal`,
`ControlProposal`, and `DocumentationGapProposal`, and bounded retry per section 26.
Retry never fires because a requirement remains unverified, which section 12 states
directly. Generation uses low creativity per section 29. The agent version is
`control-mapping-v1` per section 33. Emit an `ExecutionRecord` per invocation.

## Acceptance criteria

- [ ] The prompt file exists at the section 34 path and carries all thirteen section 24
      sections.
- [ ] The prompt states the non-exhaustiveness of `acceptable_implementations` and carries
      the worked counter-example.
- [ ] The prompt distinguishes `common_false_positives` from `non_applicable_conditions`
      by name, and a test asserts both terms appear in the composed prompt.
- [ ] Every proposed mapping carries a non-empty `applicability_reason`. A proposal
      without one fails validation and triggers a retry, per section 12 Retry behavior.
- [ ] Fixture, delegated authentication: against the ForgeFlow inputs, `req-AUTH-001` is
      applicable and no mapping proposes a missing local password policy.
      `docs/architecture/evaluation-plan.md` section 6 Scenario 2 and section 11 name this
      as a permanent regression case.
- [ ] Fixture, managed database encryption: `req-DATA-001` does not resolve to `unmet`
      because the application document does not describe encryption internals. Inherited
      encryption is recognised, or a confirmation question is raised, per
      `demo/forgeflow/forgeflow-scenario.md` section 14.2.
- [ ] Fixture, webhook authenticity ambiguity: documentation saying only that requests are
      "validated" produces a question rather than a finding. `req-WEBHOOK-001` records
      that exact phrasing under `common_false_positives`.
- [ ] Fixture, non-exhaustive implementations: a control using a mechanism absent from a
      requirement's `acceptable_implementations` is not marked unsatisfied for that reason.
      The test asserts on the rationale text, not only on the status value.
- [ ] Fixture, selectivity: for a given threat, not every candidate requirement is marked
      `applicable`, and at least one `not_applicable` mapping carries a reason referring to
      a `non_applicable_conditions` entry.
- [ ] Fixture, prompt injection: the `sample-repository-notes.md` block marks no control
      implemented and requests no secret, per scenario section 17.
- [ ] A test asserts that a mapping run producing zero `unmet` statuses is a success and
      not a failure. `docs/architecture/evaluation-plan.md` section 20 and `CLAUDE.md`
      both state that a successful assessment may produce no findings.
- [ ] A suppression driven by `common_false_positives` is recorded in the DX-09
      representation rather than discarded, and a test asserts the record exists.
- [ ] No test under `tests/unit/` makes a live model call, and `uv run pytest` passes with
      no API key configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Evidence Validation, Critical Review, and Finding Consolidation.
- Severity assignment. Section 12 prohibits it and DX-11 owns severity.
- Compliance-framework mapping. `source_frameworks` is provenance per
  `requirements/README.md`, and broad mapping is deferred by
  `docs/architecture/current-architecture.md` section 17.
- Any seventh agent.

## References

- `docs/architecture/agent-design.md` section 12 (Requirement and Control Mapping Agent —
  full contract, particularly Prohibited operations and Failure conditions), section 13
  (Mapping Validation Node), section 23 (Retrieval Design — Mapping Agent), section 24
  (Prompt Structure), section 25 (Prompt Injection Handling), section 26 (Retry Policy),
  section 29, section 33, section 34, section 35 (Phase 3), section 36 (MVP Agent Set)
- `docs/architecture/data-model.md` section 17 (Requirement; Note on
  common_false_positives), section 18 (Control), section 19 (ControlMapping — Important
  rule), section 23 (DocumentationGap)
- `docs/architecture/decision-log.md` DEC-009, DEC-011
- `requirements/README.md` — *How to read a requirement*
- `requirements/0.1/authentication.yaml`, `requirements/0.1/webhook-validation.yaml`,
  `requirements/0.1/data-protection.yaml`
- `demo/forgeflow/forgeflow-scenario.md` sections 12, 13, 14, 15, 17, 22
- `docs/architecture/evaluation-plan.md` section 6 Scenarios 2, 3, 4, 6, 7; section 11;
  section 20
- `docs/product/roadmap.md` Stage 3 (Exit criteria)
