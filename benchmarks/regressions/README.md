# False-positive regression fixtures

`evaluation-plan.md` section 11 requires every important bug to become a permanent regression
test, and names three historical failures: password-policy findings under delegated
authentication, ignored inherited encryption, and hallucinated missing MFA. The ForgeFlow
scenario describes all five of the behaviours here as intentional non-findings
(`forgeflow-scenario.md` sections 14.1 through 14.5). These are the failures DEC-009 exists to
prevent, and the ones most likely to reappear quietly after a prompt change.

Each fixture is a small architecture example — one threat, one mapping, and what the evidence
step concluded — rather than the full ForgeFlow corpus, so a failure names one behaviour.
`tests/unit/test_false_positive_regressions.py` runs each through the Finding Consolidation
node's `consolidate` and asserts **both halves**: the false positive is absent, and the correct
output — a recognised inherited control, a question, or no output — is present. Running against
consolidation output rather than agent output is deliberate: the assertion holds regardless of
which prompt version produced the candidate.

This directory is not a benchmark scenario. It holds single-behaviour fixtures consumed by unit
tests, has no `input/`/`expected/` split, and is exempted by name in
`tests/unit/test_benchmark_layout.py` — the registry in `../scenarios.yaml` governs scenarios
and does not list it.

| Fixture | Prevents | Defends |
| --- | --- | --- |
| `delegated-authentication.yaml` | a local password-policy finding under delegated authentication | DEC-009, DEC-011 (scenario 14.1) |
| `inherited-encryption.yaml` | an unencrypted-storage finding over a platform-encrypted database | DEC-009, DEC-026 (scenario 14.2) |
| `missing-mfa.yaml` | a missing-MFA finding where MFA is the identity provider's | DEC-009 (scenario 14.3) |
| `redis-network-placement.yaml` | an invented public-exposure finding for an internal component | DEC-009, DEC-013 (scenario 14.4) |
| `custom-cryptography.yaml` | a finding for not implementing custom cryptography | DEC-009 (scenario 14.5) |
