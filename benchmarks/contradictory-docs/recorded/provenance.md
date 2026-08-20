# Recorded run for the contradictory-docs scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), replacing the authored offline recording file for
file. Version pins: profile openrouter-economy, workflow 0.2 (the DEC-134 batched evidence
shape, this recording's registry pin), catalog per the registry entry, report template
report-v1. One JSON envelope per consumed response, real usage on every envelope: 19 responses
— one extraction, one threat analysis, six mappings, three evidence-validation batches, six
critical reviews, two report calls — $3.09 over 18 billed calls per the run rows (499.9k
tokens, 56 minutes of model time). `report-hash.txt` pins the live run's rendered bytes;
`report-hash-offline.txt` pins the harness replay, which stamps the offline profile.

## The capture rode through the key's monthly limit

The extract stage ran on 2026-08-20 at 04:09 UTC ($0.157). The reason stage's first attempt
died at its first live call: the OpenRouter key's monthly limit was exhausted overnight by the
parallel wave, and the gateway refused with 403 `Key limit exceeded` in 0.5 seconds, zero
tokens billed, leaving the run failed at threat_generation. Recovery after the limit was
raised was the DEC-091 path exactly: discard the data root, replay the staged prefix free
(`extract --from-recorded` re-served the recorded extraction with no spend), then run
`reason --from-recorded` live from threat analysis onward. The 403 window cost nothing and
appears in no envelope; the delay between the extract and reason envelopes' timestamps is
that window, recorded here rather than smoothed over.

## Reviewer decisions

Checkpoint 1 approved all 36 objects and claims — four components, two actors, two assets,
three flows, one boundary, twenty-four claims, every one traceable to the two source
documents. The contradiction the scenario is built around (obs-001, immediate deletion versus
30-day lifecycle retention) was resolved to the operations policy: a configured lifecycle
policy is a statement of what the system does; the architecture overview's immediate-deletion
sentence is a statement of intent, and where they disagree the configuration governs. Both
blocking questions were answered without inventing facts — effective retention is 30 days per
the resolution; the Export API's authentication mechanism is undetermined beyond the actor
description — and qst-002 (encryption at rest) was left open as analysis input.

Checkpoint 2 rejected the single candidate finding on DEC-009 grounds with a recorded
rationale: fnd-001 (req-DATA-001) established the requirement's applicability and asserted
bulk-compromise impact, but the store's encryption posture is undetermined — qst-002's and
gap-004/gap-007's territory, not a finding's. No finding was approved; the run's ten
documentation gaps and eighteen questions stand as the assessment's output.

## What this recording measures against the truth set

The truth set expects one finding (FND-CD-01, retention exceeds the documented temporary need,
req-DATA-002), one gap (GAP-CD-01, encryption at rest undetermined, req-DATA-001), and the
contradiction observation. This run resolved the contradiction correctly at checkpoint 1 and
still filed retention as a documentation gap (gap-003, "which behaviour is authoritative")
rather than proposing a finding from the resolved 30-day fact — the mapping and validation
stages asked "which statement is authoritative for req-DATA-002" three separate times
(qst-007, qst-014, qst-018) after the reviewer had answered exactly that question, so the
checkpoint-1 resolution demonstrably did not reach the downstream lenses. The structural
matcher therefore scores the expected finding missed (false_negative_rate 1) with zero
spurious findings, and the checkpoint-2 rejection is precision working (REJ-CD-02's shape
refused as the truth set prescribes). The repeated authoritative-statement questions and the
near-duplicate encryption gaps (gap-004/gap-007) are duplicate-instrument datapoints for
DEC-043's revisit. `evidence_assessment_coverage` is 1.0 — the miss is lens, not omission —
and the replay verifies byte-for-byte against the pinned hashes.

## Baselines

All three DEC-074 baselines ran live on the same model and gateway immediately after the
capture: baseline-generic matched 0, missed 1, spurious 1; baseline-structured 0/1/0;
baseline-single-pass 0/1/0. No baseline found the retention finding either, and generic added
a spurious one — the pipeline's zero-spurious result is the differential.
