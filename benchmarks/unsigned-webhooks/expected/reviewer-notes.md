# Unsigned Webhooks reviewer notes

## Construction method

An original small architecture authored for this project (design-principles section 19), built
to exercise the DEC-009 line from the *other* side: a documented negative. The receiver "does
not check a signature" is an affirmative statement, so the missing verification is a finding,
while replay handling — which the document never mentions — is a gap. The truth set derives
from `input/system-overview.md` and nothing else.

Single annotator (the project author), with re-derivation after an interval: FND-UW-01,
GAP-UW-01, and both rejections reproduced identically. No count is declared (DEC-028).

## The finding-versus-gap boundary is the scenario's point

FND-UW-01 rests on "the receiver accepts and processes any well-formed delivery and does not
check a signature" — a documented absence of a control, which is evidence. GAP-UW-01 rests on
silence about replay — an undetermined control, which is not. The two requirements
(req-WEBHOOK-001 and req-WEBHOOK-002) are distinct, and the scenario keeps them apart so a run
that collapses "no signature" into "no webhook security at all" scores a spurious replay
finding against GAP-UW-01.

## Deliberately not authored

`expected-context.yaml`, `expected-control-mappings.yaml`, and `expected-threats.yaml` are not
authored for this scenario.
