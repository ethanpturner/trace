# Recorded run for the crypto-wallet scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-19 via `trace capture` under
the `openrouter-economy` profile (DEC-135, amended) — the third live-captured scenario and the
first on the gateway path, replacing the authored offline recording file for file. Version
pins: profile openrouter-economy, workflow 0.2 (the DEC-134 batched evidence shape, this
recording's registry pin), catalog per the registry entry, report template report-v1,
generation timestamp 2026-08-11T12:00:00+00:00 (the capture's pinned stamp). One JSON envelope
per consumed response, real usage on every envelope: 29 responses — one extraction, one threat
analysis, eleven mappings, six evidence-validation batches, nine critical reviews, one report —
$4.87 staged. The reason-and-report run's row total was $5.23 over 25 calls; the difference is
retried evidence-batch attempts that produced no consumable response (roughly forty minutes of
unstaged attempts between two batches), recorded here rather than rounded away. The capture
also rode through an external kill mid-mappings that orphaned its first run — the #613 shape,
with a new wrinkle recorded on that issue: SQLite journal recovery later rewound the run row to
the checkpoint-1 pause while nine threat rows survived. Recovery was the DEC-091 design's:
discard the data root, replay the staged prefix free (`extract --from-recorded`, then
`reason --from-recorded`), spend only on unanswered calls. The round trip verified
byte-for-byte against the pinned hash; `report-hash-offline.txt` pins the harness replay, which
stamps the offline profile.

## The batched evidence shape, live

This is the first recording whose evidence phase ran the DEC-134 batched shape live: six
batches, each named its subjects, none silently omitted. The batch responses ran 22–32k output
tokens and drew retries — the unstaged-attempt tax above — which is a datapoint for DEC-134's
"batch size forty is a constant, not a measurement" caveat, on a reasoning-heavy model.

## Reviewer decisions

Checkpoint 1 approved all 52 extracted objects — fifteen components, one actor, four assets,
nine flows, two boundaries, twenty-one claims, every one traceable to the source document —
with two edits: `internet_exposed` corrected to true on the daemon-to-ElectrumX and
module-to-blockchain flows, which cross into the internet zone to third-party endpoints. Both
blocking questions were answered without inventing facts: the TLS posture stands as documented
and not re-verified, and wallet-file encryption enforcement is undetermined; both gaps are
analysis input. Checkpoint 2 approved one of three candidates (fnd-001, medium — the wallet
file's encryption at rest positively documented as optional rather than enforced) and rejected
two on DEC-009 grounds with recorded rationales: one premised on a TLS misconfiguration no
evidence shows (the verification gap is qst-001's, which the run itself asked), one asserting
a requirement's applicability without any evidenced deficiency in the documented control.

## What this recording measures against the truth set

The truth set (`expected/`) was authored (#327) as the hedged-statement zero-finding path: the
correct outcome is a documentation gap and a question, no findings. This run's reviewer read
"encryption is a wallet option" as a positively documented unenforced control and approved
fnd-001, so the structural matcher scores one spurious finding beside a zero-finding
expectation — lens divergence on exactly the hedged statement the scenario was built around.
The score is the measurement, not a defect in the recording; whether the reviewer's reading or
the truth set's is the better DEC-009 discipline is #589's reconciliation territory, not this
recording's to settle. `evidence_assessment_coverage` under the batched shape is what the
replay's metrics report; the six batches covered every named subject.
