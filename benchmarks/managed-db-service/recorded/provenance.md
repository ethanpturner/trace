# Recorded run for the managed-db-service scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), replacing the authored offline recording (#326)
file for file — the sweep's sixth live-captured scenario. Version pins: profile
openrouter-economy, workflow 0.2 (the DEC-134 batched evidence shape, this recording's registry
pin), catalog 0.1 per the registry entry, report template report-v1, generation timestamp the
capture's pinned stamp. One JSON envelope per consumed response, real usage on every envelope:
16 responses — one extraction, one threat analysis, six mappings, two evidence-validation
batches, five critical reviews, one report — $2.61 staged. The run rows total $3.04 over 16
counted calls; the difference is attempts that produced no consumable response, recorded here
rather than rounded away. The three baseline envelopes record findings, not usage, per their
schema; their three calls are the capture's only spend outside the run rows.

## The credit-wall park

This capture spans the key's credit wall. The extract stage ran on 2026-08-19 evening
($0.23 staged); the reason stage then failed at threat_generation with OpenRouter 402 —
`limit_source: openrouter_key_limit`, the monthly limit affording ~28k tokens against a
64k-token request — which is account state, not a provider window, so no retry could succeed.
The run row held the classified failure overnight (~9 hours). After the limit was raised, the
recovery was the DEC-091 design's: `reason --from-recorded` replayed the staged extraction
free and spent only from the threat-generation call forward. Nothing already captured was
re-bought.

## Reviewer decisions

Checkpoint 1 approved 26 objects with one added data flow and answered four blocking questions
without inventing facts; four questions were left open (tenancy isolation, retention
enforcement, network reachability, API-to-database credentials) and carry into the report.
Checkpoint 2 rejected the run's single candidate finding (fnd-001, interception of metrics
over internal HTTP flows) on recorded rationale: the API-to-database leg is documented as
platform-encrypted — the `common_false_positives` entry req-DATA-001 names for managed
services — and the service-to-API legs are silent rather than affirmatively unencrypted, which
under DEC-009 is a question, never a finding; the open network and credential questions hold
that substance.

## What this recording measures against the truth set

The truth set expects zero findings: req-DATA-001 satisfied by the inherited platform control,
with the graded content in `expected-rejections.yaml`. This run's reviewer rejected the one
candidate on exactly the grounds REJ-MD-01 and REJ-MD-03 describe, so the structural matcher
scores 0 matched, 0 missed, 0 spurious — the inherited-control path measured live. The
baseline contrast on the same day's calls: baseline-generic produced 2 spurious findings (the
encryption false-positive class this scenario was built around), baseline-structured and
baseline-single-pass 0. `evidence_assessment_coverage` is 1.0 under the batched shape; both
evidence batches named every subject. The round trip verified byte-for-byte against
`report-hash.txt`; `report-hash-offline.txt` pins the harness replay, which stamps the
offline profile, verified on two consecutive replays.
