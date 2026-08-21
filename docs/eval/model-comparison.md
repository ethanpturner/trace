# Model comparison — three profiles, six arms bought, three dropped against the cap

*Recorded 2026-08-21. Issue #332. The comparison the evaluation plan's model-evaluation section
names, executed: the `openai/gpt-5.1` arm recorded from the #484 sweep at no new cost, and the
first completed live `claude-opus-5` and `claude-sonnet-5` pipeline runs. Three arms were
dropped against the spend cap and are named below — this table says what was bought and what
was not, and the 2026-08-20 attempt record is kept at the bottom because the two defects it
found (and the third one this completion found) are part of the comparison's story.*

## The table

Finding-layer outcomes are the per-item match sets against each scenario's truth set;
`coverage` is `evidence_assessment_coverage`, 1.0 on every arm. `defaulted` counts checkpoint
decisions that fell to the DEC-077 default policy because no recorded decision fingerprint
matched — the column that scopes what this table may claim (see the confound below). Run cost
is the completed run's ledger; arm total is every dollar the arm consumed across kills and
re-drives, interruption losses included, per the attempt record's accounting rule.

| Scenario | Model | matched / missed / spurious | coverage | defaulted | subjects | run cost | arm total |
|---|---|---|---|---|---|---|---|
| missing-docs | `openai/gpt-5.1` | 0 / 0 / 0 | 1.0 | 0 | 110 | $2.83 | (sweep's) |
| missing-docs | `claude-opus-5` | 0 / 0 / 0 | 1.0 | 28 | 176 | $4.67 | $13.27 |
| missing-docs | `claude-sonnet-5` | 0 / 0 / 1 | 1.0 | 11 | 53 | $2.36 | $7.49 |
| reply-tuner | `openai/gpt-5.1` | 1 / 0 / 0 | 1.0 | 0 | 117 | $2.97 | (sweep's) |
| reply-tuner | `claude-sonnet-5` | 0 / 1 / 5 | 1.0 | 24 | 52 | $4.73 | $16.32 |
| crypto-wallet | `openai/gpt-5.1` | 0 / 0 / 1 | 1.0 | 0 | 156 | $4.87 | (sweep's) |

**Dropped against the cap, named rather than truncated:** `claude-sonnet-5`/crypto-wallet
(projected $8–10 against $7.92 of remaining headroom), `claude-opus-5`/reply-tuner, and
`claude-opus-5`/crypto-wallet. The completion ran cheapest-first once measured arm costs came
in above their estimates, which is why the sonnet row is fuller than the opus row.

## The confound this comparison measured about itself

The reviewer variable was held constant by replaying the sweep's recorded checkpoint decisions
by content fingerprint. That instrument is exact for the model that produced the recordings —
the `openai/gpt-5.1` arms default zero decisions by construction — and coarse for every other
model: objects and claims minted in another model's words rarely fingerprint-match, and the
unmatched subjects fall to the default policy, a more lenient reviewer than the recorded one.
The opus and sonnet arms carry 11–28 defaulted decisions each. The sharpest case is
reply-tuner/`claude-sonnet-5`: five candidate findings, none matching a recorded fingerprint,
all five approved by default and all five scoring spurious — a row that measures the
default-policy reviewer at least as much as it measures the model. Cross-model rows in this
table are therefore **model + replay-fidelity**, never model alone. A future comparison wants
either a per-arm human pass or a fingerprint matcher robust to cross-model paraphrase — the
same string-identity boundary the #484 sweep recorded on translation-gateway (DEC-066), showing
up here as a measurement confound instead of a scoring miss.

## What can be said inside that limit

- **The zero-finding discipline held on every model.** All three profiles completed
  missing-docs' intended zero-finding path at the outcome layer; opus minted no candidate
  finding at all despite 28 defaulted decisions — the DEC-009 posture surviving the most
  lenient reviewer condition this harness can produce.
- **The matched finding stayed matched only on the sweep model.** reply-tuner's expected
  training-data finding was caught by `openai/gpt-5.1` (severity-concordant) and missed by
  `claude-sonnet-5`, whose five default-approved candidates circled adjacent ground.
- **The mapping fan-out is model-emergent, and it is the cost driver.** On the same scenario
  and inputs, opus minted 176 evidence subjects, gpt-5.1 110, sonnet 53 — a 3.3× spread in
  assessed workload that flows straight into evidence-validation batch count and dollars.
  Model choice sets not just answer quality but how much assessment the pipeline decides to do.
- **Cost per completed run:** sonnet $2.36–4.73, gpt-5.1 $2.83–4.87 (gateway rates), opus
  $4.67 for its one completed run — with the caveat that the interrupted arms' true single-pass
  costs are higher than their completed-run ledgers (the replayed prefixes were paid for in
  earlier runs; the arm-total column carries the honest number).

`duplicate_finding_rate` reported 0 with no evaluable pairs on every arm; no multi-finding run
produced a same-ground pair for #591's population (reply-tuner/sonnet's five spurious findings
sit on five distinct requirements).

## Operations: the fix chain, field-tested the night it landed

Three more harness-side process kills hit this completion — and this time each cost wall
clock, not money. DEC-142 held in the field: consolidated journals replayed 14 of 20, 14 of
17, and 13 of 13 entries free across both checkpoint applications, hashes matching across
processes. Total new spend for the completion was $24.08 against arms that would have cost
roughly $35 bought cold; the session's #332 total is $37.08 of the $45 cap ($67.53 across both
days, both attempts included).

The completion also found the journal machinery's third defect: **a re-drive's journal is not
continuous** — a call served from a replay journal is not re-journaled into the new run's
journal, so the new journal starts mid-run, and the replay queue is order-sensitive from entry
one: offered a journal whose first entry is not the run's first call, it skips every entry as
"a completed phase's entry" and buys the whole run. The workaround (manual consolidation of
served prefixes with fresh tails, renumbered) recovered every re-drive tonight; the fix —
copy served entries forward so every journal is complete from call one — is filed. A residual
divergence class also showed twice: an entry recorded from a *retry* call carries validation
feedback in its request that a fresh drive does not compose, so replay honestly diverges there
and buys the tail; that one is inherent to the retry design and is a caveat, not a defect.

## Caveats

n = 1 per arm per scenario — variance is DEC-077's instrument, not this page's. The defaulted
column must accompany any quotation of the cross-model rows. Costs are each provider's
published rates as the ledger recorded them; interruption losses are reported in the arm-total
column and the attempt record, never folded into run costs. Attribution per DEC-136 from the
feeds' `models` field.

---

# Appendix: the 2026-08-20 attempt record

*Kept verbatim in spirit, condensed in length: the first execution attempt completed zero live
arms and found the two defects that made this completion possible.*

The first attempt spent $30.45 across four runs (opus/missing-docs twice, sonnet/reply-tuner
twice), every one killed harness-side before completion. Attempt 1's $14.35 was unrecoverable
— the harness live path built its model bare, journaling nothing (#638, fixed: the path now
mounts DEC-139's journal and `--replay-journal` re-drives it). Attempt 2's journals survived
but would not replay past checkpoint 1 — a wall-clock field (`approved_at`) rendered into the
threat package made every re-drive's requests unmatchable (#639, fixed as DEC-142: no
model-facing package renders a wall clock; `scripts/replay_forgeflow.py` reproduces its pinned
hash under the fixed shape). The 61 preserved response envelopes under `journals/` were this
completion's replay prefixes; the `feeds/` directory carries all six arms' scored feeds.
