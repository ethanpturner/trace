# Recorded run for the translation-gateway scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), in the #484 sweep's third wave, replacing the
authored offline recording (#328) file for file. Version pins: profile openrouter-economy,
workflow 0.2 (the DEC-134 batched evidence shape, this recording's registry pin), catalog per
the registry entry, report template report-v1, generation timestamp pinned to the capture's
deterministic stamp. One JSON envelope per consumed response, real usage on every envelope:
16 responses — one extraction, one threat analysis, five mappings, three evidence-validation
batches, five critical reviews, one report — $2.57 by the run rows, $2.57 staged, **zero
unstaged attempts and zero retries**: a single uninterrupted pass, roughly forty minutes of
model wall clock. The three baseline calls are the only spend outside the run rows
(findings-only envelopes at economy rates). The live report hash is pinned in
`report-hash.txt`; `report-hash-offline.txt` pins the harness replay, identical across two
independent replays and verified `true` on a third.

## Reviewer decisions

Checkpoint 1 approved all 33 subjects as extracted — three components, one actor, three
assets, three flows, one boundary, twenty-two claims, every one traceable to the source
document — with the five load-bearing claims confirmed (full body sent; token grants full
workspace access; effective use is read-tickets-write-notes; no retention agreement
established; standard terms unreviewed). Both answerable questions were answered from
documented facts only: what the provider's terms permit is undetermined and that
indeterminacy is itself the documented fact, and the token's scope is documented as a
convenience choice with no documented technical constraint. Three questions were left open.

Checkpoint 2 approved one of two candidates and rejected one. fnd-002 (req-TPI-001, the
missing retention and secondary-use agreement) was approved at high per the reviewer
guidance — the evidenced deficiency is the one the document itself states, and the approval
asserts the missing agreement, never anything about what the provider actually does with the
text. The capture's decision writer supports severity, approve, and reject with rationale;
the minted title's breach framing was therefore not edited, and the approval rationale
records the reviewer's reading of it as the consequence scenario. fnd-001 (req-DATA-001
encryption) was rejected on DEC-009 grounds: transit encryption is documented, and the
provider's at-rest handling is exactly the unknown REJ-TG-01 names for this scenario.

## What this recording measures against the truth set

The truth set expects two findings. The structural score is **0 matched, 2 missed, 1
spurious** — and both halves of that score are lens divergences, recorded rather than
smoothed:

- **FND-TG-01 scores missed and the approved fnd-002 scores spurious, and they are the same
  real-world finding.** The DEC-066 fingerprint matches on requirement ids plus normalized
  affected-component *names*. The truth set names one component, `Translation Connector`; the
  live extraction named it `Helpdesk Translate connector service` and the live finding
  attributed all three components. Same requirement (req-TPI-001), same evidence (the
  documented absent agreement), no fingerprint match. Whether the matcher, the truth set's
  naming, or the finding's component breadth should move is #589's reconciliation territory,
  not this recording's to settle.
- **FND-TG-02 (the over-scoped token) is a genuine recall miss.** No candidate finding was
  minted for it: the pipeline carried the documented over-grant into questions (qst-012,
  qst-013) rather than a finding. `evidence_assessment_coverage` is 1.0, so the miss is lens,
  not omission — the unsigned-webhooks signature again.

`documentation_gap_precision` is 0.08: thirteen gaps minted against the one expected custody
gap, the same over-minting pattern nightly-reconciler recorded the same day. All three live
baselines missed both expected findings with spurious findings besides — generic 0/2/4,
structured 0/2/2, single-pass 0/2/3 — so on this scenario the pipeline's substance (one
evidenced finding approved, the provider-behaviour class kept out) beats every baseline on
both axes even though the instrument's fingerprint scores it 0-for-2.

The authored recording this capture replaced is frozen at
`tests/fixtures/helpdesk-translate-authored/` as the harness tests' stable probe fixture; see
its README.
