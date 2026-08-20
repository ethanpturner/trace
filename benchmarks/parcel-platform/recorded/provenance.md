# Recorded run for the parcel-platform scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), replacing the authored offline recording file for
file — the large-architecture scenario's first live capture. Version pins: profile
openrouter-economy, workflow 0.2 (the DEC-134 batched evidence shape, this recording's registry
pin), catalog per the registry entry, report template report-v1. One JSON envelope per staged
response, real usage on every envelope: 36 envelopes — one extraction, one threat analysis,
eleven mappings, twelve evidence-validation batches, ten critical reviews, one report. The final
run's ledger records 30 calls at $7.70 (extraction $0.26, threat analysis $0.21, mapping $2.38
over ten rows, evidence validation $3.51 over seven rows, critical review $1.28 over ten rows,
report $0.05); the envelope-versus-row difference is the DEC-091 recovery structure below, stated
here rather than smoothed over, as the crypto-wallet recording's provenance did for its own
delta. The three baseline calls are the only spend outside the run rows.

## Two local kills, recovered at zero re-spend

The capture rode through two local process kills — the coordinating harness stopping the
background stage, not a provider or account failure. The first caught the reason stage inside
evidence validation (17 envelopes staged, $3.70); the second caught it inside critical review
(26 envelopes, $7.24). Both recoveries were the DEC-091 design's: discard the data root, replay
the staged prefix free (`extract --from-recorded`, then `reason --from-recorded`), spend only on
calls that never returned. Nothing already paid for was re-bought; the 402 credit wall that
parked Wave A never touched this scenario. One authoring defect is also on the record: the first
checkpoint-1 decisions file was refused whole for an unknown `rationale` key on a component
edit — the review-file parser's strictness working as designed, refused before any spend.

## Reviewer decisions

Checkpoint 1 approved all 99 subjects — twenty-five components, seven actors, eight assets,
sixteen flows, three boundaries, forty claims — with two edits: `internet_accessible` corrected
to true on the Customer Portal and the Mobile Gateway, which the document describes as the
public web application and the driver application's HTTPS endpoint; the extraction had asserted
false, a negative the document contradicts. The reachability question (qst-006) was answered
from the document's own statements — the API Gateway is the single public entry point and
authenticates every request — and the five genuinely undocumented questions (warehouse
retention, log hosting and controls, admin role separation, photo retention, bus encryption)
were left open as analysis input.

Checkpoint 2 received three candidates, all mapped to req-ADMIN-001, and approved one:
fnd-001, the Admin Console's documented access path — the same SSO accounts and sign-in path
customers use, a single `is_admin` flag, read-and-edit reach over every customer account, order,
and address — at high severity per the reviewer notes' guidance, with a DEC-023 title edit: the
exported title asserted a compromise event no evidence establishes, and the approved title
claims only the evidenced deficiency. The other two candidates were rejected on DEC-009
grounds with recorded rationales: a Deploy Runner code-injection threat justified by the Admin
Console's existence (no evidenced pipeline deficiency; the open questions already carry it), and
a billing-tampering threat premised on attacker access rather than any documented weakness
against an affirmatively sound payment posture.

## What this recording measures against the truth set

The truth set (#328) expects two findings and two gaps, with the graded property that scale does
not change the rules. Measured: FND-PP-01 (the admin access path) matched fnd-001 with severity
concordance 1.0; FND-PP-02 (the notification templates' body-level logging) **missed** — the
affirmatively documented statement flowed into a claim (ctx-021), an asset, and questions, but
no candidate finding reached checkpoint 2, and the reviewer surface adds no findings, so the
miss is lens, not omission: `evidence_assessment_coverage` is 1.0 and zero spurious findings
were approved. The gap layer diverges harder: the run minted seventeen documentation gaps —
largely requirement-confirmation shapes from evidence validation — and neither expected gap
matched structurally (`documentation_gap_precision` 0), which is #589's reconciliation
territory, not this recording's to settle. Live baselines on the same day: generic 1/1/1,
structured 0/2/2, single-pass 1/1/1 — every baseline produced at least one spurious finding
on the nineteen-component surface; the pipeline produced none.

The live report hash is pinned in `report-hash.txt`
(`sha256:a95c2f22…8f88`); the offline replay is pinned in `report-hash-offline.txt`
(`sha256:43c1b69c…3a51`), identical across two consecutive fresh-root replays and verified by
the harness on a third.
