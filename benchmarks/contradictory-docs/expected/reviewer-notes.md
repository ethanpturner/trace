# Contradictory Docs reviewer notes

## Construction method

An original small architecture authored for this project (design-principles section 19), built
to exercise contradiction handling: two supplied documents that disagree about export
retention. The truth set derives from `input/architecture-overview.md` and
`input/operations-guide.md` and nothing else.

Single annotator (the project author), with re-derivation after an interval: OBS-CD-01,
FND-CD-01, GAP-CD-01, and both rejections reproduced identically; the contradiction's
resolution to the operations policy was reached the same way both times. No count is declared
(DEC-028).

## Why the contradiction resolves to the operations policy

The architecture document asserts intent ("temporary working data, deleted immediately"); the
operations guide states a configured lifecycle policy ("retains for 30 days"). A configuration
is a stronger statement of what the system does than an assertion of what it is meant to do, so
the contradiction resolves to 30-day retention, which drives FND-CD-01 on req-DATA-002 — the
same shape as ForgeFlow FND-003. The reviewer confirms the resolution at checkpoint 2;
OBS-CD-01 is an observation about the documents, not a finding on its own (agent-design section
25). REJ-CD-01 records the wrong resolution.

## Deliberately not authored

`expected-context.yaml`, `expected-control-mappings.yaml`, and `expected-threats.yaml` are not
authored for this scenario.
