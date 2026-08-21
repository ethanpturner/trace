# The overnight chain: two fixes proving themselves on the run that needed them, and the comparison bought

One directive drove the night: run the chain — #639, #638, then #332's completion — end to end.
It ran, and the middle of it demonstrated the project's own reliability story in miniature: the
fixes landed first, then the paid run that had been impossible without them completed *because*
of them, surviving three process kills and a machine-sleep at zero re-spend.

## The fixes

- **DEC-142 (#639, PR #642):** the replay divergence had a one-field root cause — the threat
  package rendered `approved_at`, a wall clock re-minted on every checkpoint application, so two
  identical re-drives could never compose the same request. The field is removed, not
  stabilized: the approval fact is structural, the instant is audit provenance. The DEC's rule
  is general — no model-facing package renders a wall clock — and the survey behind it covered
  every composition point. The issue body's suspect (DEC-141's settlements) was exonerated; the
  field predates it. ForgeFlow's pinned hash reproduces byte-for-byte post-fix.
- **#638 (PR #643):** the harness live path now mounts the DEC-139 journal exactly as the CLI
  does, with explicit `--replay-journal` re-drive. No DEC — a decided mechanism mounted on a
  path that should always have carried it. #633's stability runs inherit the protection for
  free.
- Also out of #639's diagnosis: #641, the mid-phase-kill orphan class neither `resume` nor
  `runs repair` reaches.

## The comparison, bought inside its limits

PR #644 finishes #332. The estimate said the old journals would complete the arms for $3–5;
DEC-142's own tradeoff killed that — removing the field invalidated the preserved post-extraction
hashes — and the corrected figure ($30–40) was put in front of the operator before a cent moved.
Spend: $24.08 on the night, $37.08 of the $45 completion cap, $67.53 program total across both
attempts, itemized. Three arms were dropped at the cap and are named in the record, cheapest-first
once sonnet arms measured $6–7.50 against the $2.50–4 estimate.

What the table says, inside its stated limit: all three profiles held the zero-finding path;
the matched finding stayed matched only on the sweep model; and the cross-model rows are
confounded by decision-replay fidelity — fingerprint replay of recorded decisions defaults 0
subjects on the model that recorded them and 11–28 on the others, so a foreign model's spurious
findings measure the lenient default reviewer as much as the model. The unconfounded number is
the workload one: the mapping fan-out is model-emergent, 176/110/53 subjects on identical
inputs, a 3.3× spread that is the real cost driver between profiles.

The reliability half of the record is the quieter headline: three harness kills and one machine
sleep during the completion, every one recovered at $0 — consolidated journals replayed
14/20, 14/17, and 13/13 entries across both checkpoints. DEC-142 was field-verified the night it
merged. One continuity defect surfaced and is filed (#645: served entries are not copied forward,
so second-generation re-drives need manual consolidation); the retry-feedback divergence class is
documented as inherent.

## Open next

- #645 (journal continuity) and #641 (the orphan class) — the remaining reliability seams.
- #633's stability protocol, now journal-protected end to end; needs its spend go-ahead.
- #601 scorecard v3, whose stratified readout the comparison's confound argument now strengthens:
  pooled cross-model numbers mislead in a measured, documented way.
- The decision-replay fidelity confound itself is #589-adjacent evidence: cross-model comparison
  needs either model-agnostic decision matching or the honest label the record gave it.
- The human items stand: #565's second annotator, #353's demo video.
