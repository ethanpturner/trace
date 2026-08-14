# The injection guard runs both ways, and secret scanning reaches CI

## What changed

Two hardening chores from the audit. #406: the prompt-injection regression suite covered six of
the fixture's eight imperative directives, and its fixture guard only checked that the known
instructions were still present — it could not notice a new instruction planted in the document,
so the guard's claim ("editing the fixture without editing the tests fails") held in one
direction. The two missing directives now have their tests, and the planted block is pinned
verbatim: any edit to the payload fails until the instruction list and its tests move with it.
#407: gitleaks ran only as a local pre-commit hook, which `--no-verify` or an uninstalled clone
bypasses — the threat model's own known gap since 2026-08-09. CI now runs the same pinned release
over the full history on every pull request, and the threat-model rows flip to Enforced.

## The two new instruction tests, and why their mechanisms differ

The pull-request-comments directive is structurally inapplicable, like findings suppression:
context extraction posts nothing anywhere — the instruction reads as if Trace were the ForgeFlow
worker it is assessing — and the proposal schema carries no outbound channel, so a response that
invents one fails validation rather than exfiltrating through it.

"Do not mention these instructions" is different in kind: silence cannot be schema-refused,
because no schema forces a model to volunteer what it noticed. The defence is that mentioning is
an expected output — the truth set requires the `injection_attempt` observation naming this
document, and the adversarial detection axis reports the same omission as `attack_detected:
false`. The test pins the measurement the instruction is up against, which is the honest shape of
that defence.

## One verification worth recording

The CI step scans history, which is stronger than the hook's staged-content scan — and riskier to
enable blind, because test fixtures deliberately contain key-shaped strings. gitleaks v8.30.1 was
run over all 396 commits locally before the step was committed: no leaks found. `--redact` keeps
any future hit out of the CI log, which would otherwise republish the thing it caught.

## Open next

The dead-surface pair (#408 ReplayCache, #409 validator feedback) each need a decision, then the
doc sweeps (#410, #411) close the audit backlog.
