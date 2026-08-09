## Context

`docs/architecture/evaluation-plan.md` section 11 requires every important bug to become a permanent
regression test and names three specific historical failures: password-policy findings generated
under delegated authentication, ignored inherited encryption, and hallucinated missing MFA. The
ForgeFlow scenario already describes all three as intentional non-findings
(`demo/forgeflow/forgeflow-scenario.md` sections 14.1, 14.2 and 14.3). These are the exact failures
DEC-009 exists to prevent, and they are the ones most likely to reappear quietly after a prompt
change.

## Scope

- Regression fixtures and tests for the three named false positives, each a small architecture
  example rather than the full ForgeFlow corpus, so a failure names one behaviour:
  - Delegated authentication through an external identity provider does not produce a local
    password-policy finding.
  - A managed database whose encryption is inherited from the platform does not produce an
    unencrypted-storage finding. Inherited-control scope follows the representation fixed in DX-15.
  - Absence of an application-managed MFA setting does not produce a missing-MFA finding where
    MFA is governed by the external identity provider.
- Two further fixtures drawn from the same section of the scenario, because they exercise the same
  boundary: a component mentioned without its network controls does not produce an exposure finding,
  and the absence of custom cryptography does not produce a finding.
- Each fixture asserts the positive outcome as well as the negative one: the correct output is a
  recognised inherited control, a question, or no output, and the test states which.
- Tests run against consolidation output rather than against agent output, so they hold regardless of
  which prompt version produced the candidate.
- Fixtures live under `benchmarks/` in the layout fixed by DX-18 and are exercised by unit tests that
  need no provider credential. Where a fixture requires a model in the loop, that variant is marked
  `evaluation` and is deselected by default.
- Each test carries a comment naming the failure it prevents and the decision it defends, so a future
  reader deleting it has to do so deliberately.

## Acceptance criteria

- [ ] A regression test exists for each of the three failures named in evaluation-plan section 11.
- [ ] Each test asserts both that the false positive is absent and that the correct output is
      present.
- [ ] The inherited-encryption fixture asserts that the inherited control is recognised, not merely
      that no finding was produced.
- [ ] The delegated-authentication fixture asserts that the external identity provider is identified
      as the control provider.
- [ ] Two additional fixtures cover the network-placement and custom-cryptography non-findings from
      `forgeflow-scenario.md` sections 14.4 and 14.5.
- [ ] Tests run against consolidation output, not against raw agent output.
- [ ] Each test names, in a comment, the failure it prevents and the decision it defends.
- [ ] `uv run pytest` passes with no provider credential configured; any model-in-the-loop variant is
      marked `evaluation` and stays deselected.
- [ ] `uv run mypy` passes in strict mode over the new test modules.

## Out of scope

- The full ForgeFlow assessment run, which the expected-output fixtures cover.
- New regression cases discovered later, which are added as they occur per
  `docs/product/roadmap.md` section 4 ("Evaluation").
- Prompt-version comparison, evaluation-plan section 12.

## References

- `docs/architecture/evaluation-plan.md` — section 10, section 11, section 12
- `demo/forgeflow/forgeflow-scenario.md` — section 12, sections 14.1 through 14.5, section 22
- `docs/architecture/agent-design.md` — section 31 ("Fixture tests", "Regression tests")
- `docs/architecture/decision-log.md` — DEC-009, DEC-011
- `docs/product/design-principles.md` — section 3, section 9, section 10
- `docs/product/roadmap.md` — Stage 3 ("Exit criteria"), Stage 4, section 4 ("Evaluation")
