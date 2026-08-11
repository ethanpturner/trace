# OIDC Portal reviewer notes

## Construction method

An original small architecture authored for this project (design-principles section 19), built
to exercise one mechanism cleanly: delegated authentication that a generic review turns into
local-credential findings. The truth set derives from `input/system-overview.md` and nothing
else; every rejection cites a `common_false_positives` or `non_applicable_conditions` entry
that exists in catalog 0.1, checked against the catalog file.

Single annotator (the project author). In place of inter-annotator agreement, the set was
re-derived from the input after an interval without consulting the first pass; the three
rejections and the empty finding set were reproduced identically, and GAP-OP-01 was reproduced
with the same requirement and a reworded question. No count is declared (DEC-028).

## Why zero findings is the correct output

The portal holds no credential store and delegates authentication and factor policy to the
enterprise identity provider, both stated affirmatively. Every authentication weakness a
generic review reaches — password policy, lockout, application MFA — asserts a local surface
the document denies. A successful assessment here produces no findings (DEC-013); the negative
cases are the graded content, and GAP-OP-01 is the one genuinely undetermined item.

## Deliberately not authored

`expected-context.yaml`, `expected-control-mappings.yaml`, and `expected-threats.yaml` are not
authored for this scenario. The harness scores findings, gaps, and — through the regression
suite — rejections; those are authored here. Stating the omission keeps it a decision.
