# Recorded run for the reply-tuner scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture`
under the `openrouter-economy` profile (DEC-135), replacing the authored DEC-114 recording
file for file — the fine-tuning pack's scenario, captured in the #484 sweep's third wave.
Version pins: profile openrouter-economy, workflow 0.2 (the DEC-134 batched evidence shape,
this recording's registry pin), catalog 0.3 per the registry entry, report template
report-v1. One JSON envelope per consumed response, real usage on every envelope:
19 envelopes — one extraction, one threat analysis, seven mappings, evidence-validation
batches, critical reviews, and the report sections — $3.27 over 16 calls by the run rows,
with zero unstaged attempts and zero retries: a single uninterrupted pass. The three
baselines are single calls at economy rates in `baselines/`.

## Reviewer decisions

Checkpoint 1 approved all seven components, three actors, four assets, five flows, and
seventeen claims, with one flow edit and one addition (DEC-023): the extractor drew the
helpdesk writing directly to the training store, and the document's write path is the
Transcript Exporter's — its job identity the only principal with write access, granted
through the platform's access policy — so df-001 was re-drawn as exporter-to-store with the
documented job-identity authentication, and a helpdesk-to-exporter read flow was added. The
blocking question (training-store read access) was answered as undocumented and
undetermined; artifact retention and the operating actor were held undetermined on the
document's silence; external reachability was answered from the document's internal-pipeline
description.

Checkpoint 2 approved fnd-001 at high severity with a DEC-023 title edit — the exported
"poisons fine-tuning" framing asserts adversarial manipulation no evidence establishes, and
the approved title claims only the evidenced deficiency: the model is fine-tuned on full,
unminimized customer transcripts with no redaction step and no stated justification, unmet
req-TRAIN-002 on the document's own affirmative text. The affected components were narrowed
from the exported seven to the data path (Tuning Job, Training Store, Transcript Exporter).
fnd-002 was rejected on DEC-009 grounds: premised on a compromised exporter identity no
evidence shows, attacking the document's own governed write path — REJ-RT-01's suppression
mechanism — with the credential-handling verification gap already held by the run's open
secret-handling questions.

## What this recording measures against the truth set

The finding layer met the truth set exactly: FND-RT-01 matched (fnd-001,
req-TRAIN-002, severity concordance 1), zero missed, zero spurious.
`evidence_assessment_coverage` is 1.0 under the batched shape. The gap layer diverged and is
recorded, not smoothed: eight documentation gaps were minted and none matched the expected
req-TRAIN-003 lineage gap — `documentation_gap_precision` 0, the same over-minting signature
nightly-reconciler and order-notifier recorded, #589's reconciliation territory. The mapper
also re-asked requirement definitions as open questions (qst-005 through qst-014), the
meta-documentation signature the sweep has recorded on other scenarios.

## Baselines, scored as measured

All three live baselines raised the substantively correct unminimized-training finding on
req-TRAIN-002 and scored **1 missed + 1 spurious** each: the structural matcher requires
`affected_component` equality with "Tuning Job", and every baseline emitted a compound
component string ("Training Store and Tuning Job", "Training Store / Tuning Job",
"Training Store"). The score is the measurement and the matcher's granularity is part of
what it measures; whether component-string matching under-credits one-call baselines is
#589 reconciliation territory, recorded here rather than adjusted here.

## Hashes

Live report `sha256:80b9427e94086fdcbd0666b5f2f8b1ede826efe97befee2386bd6655479a6c6a`
(`report-hash.txt`, the capture's pinned stamp). Offline replay pin
`sha256:1c4d680ea2759d0384cc7d7a0d85d91b6070432f8f05a52181628ee119e97f8d`
(`report-hash-offline.txt`), verified against the scenario's recorded pin on two
consecutive replays.
