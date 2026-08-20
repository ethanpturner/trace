# Recorded run for the nightly-reconciler scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), in the #484 sweep's second wave, replacing the
authored offline recording file for file. Version pins: profile openrouter-economy, workflow
0.2 (the DEC-134 batched evidence shape, this recording's registry pin), catalog 0.3 per the
registry entry, report template report-v1, generation timestamp 2026-08-14T12:00:00+00:00 (the
capture's pinned stamp). One JSON envelope per consumed response, real usage on every envelope:
18 responses — one extraction, one threat analysis, seven mappings, two evidence-validation
batches, six critical reviews, one report — $2.42 staged, and the run rows total the same
$2.42 over 17 calls: no unstaged attempts, no retries, roughly 50 minutes of model wall clock
in a single uninterrupted pass. `evidence_assessment_coverage` 1.0 across both batches. The
round trip verified `true` against `report-hash-offline.txt` on two consecutive replays;
`report-hash.txt` pins the live render.

## Reviewer decisions

Checkpoint 1 approved all thirteen objects and fifteen claims — every one traceable to the
overview or the workspace assertion — including the two parser-seeded organizational-control
claims (ctx-001 secrets-vault, ctx-002 managed-db-encryption), each approved and confirmed
with a rationale naming its `applies_when` condition in the overview's own words. Two
questions were answered from documented facts alone: credential custody (answered from the
asserted secrets-vault control, the suppression mechanism doing its work) and external
reachability (answered from the overview's no-inbound-interface statement, with the
enforcement of the database restriction explicitly left undetermined). Four questions were
left open, the reachability-enforcement gap territory among them. Checkpoint 2 rejected the
single candidate finding (in-transit interception on the internal database flows) on DEC-009
grounds: the connection's authentication and encryption are undetermined — the run's own open
qst-002 — and no evidence shows the traffic unprotected. Zero approved findings.

## What this recording measures against the truth set

The truth set (#568, DEC-122) is the org-controls zero-finding path, and the outcome layer met
it exactly: zero findings approved, zero spurious, zero missed, with the one candidate stopped
at checkpoint 2. The layer beneath diverged, and the scores record it rather than smooth it:
`requirement_mapping_accuracy` 0.0 — the mapper scored req-SECRET-001 `unverified` where the
truth expects `satisfied` on the strength of the asserted org-control, so the suppression
carried through reviewer judgment rather than through the mapping verdict — and
`documentation_gap_precision` 0.0, the run minting eleven gaps against the one expected
(GAP-NR-01's reachability enforcement among the misses at matcher granularity). Whether the
mapping lens or the truth set's is the better DEC-122 reading is #589's reconciliation
territory, not this recording's to settle. The headline suppression claim — approved
organizational context prevents a false conclusion — held where the report is written: the
credential-custody and at-rest-encryption conclusions a generic review reaches were not
reached.

## The baselines, live

All three baselines ran live on the same day, model, and gateway, and all three scored
0 matched, 0 missed, 0 spurious: on this scenario `openai/gpt-5.1` declines the two generic
false positives even without the org-controls assertion, so the head-to-head shows no
precision differential here — recorded as the measurement it is. The differential this
scenario was built to demonstrate rests with models that do raise the false conclusions, and
with the earlier scenarios where this model's generic baseline did (managed-db-service:
two spurious encryption findings the same day).
