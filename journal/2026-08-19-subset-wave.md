# The subset wave: four captures promoted, coverage 1.0 across the board, and two defects the wave caught

The evening's second act: the #484 subset the operator chose — four scenarios plus live
baselines, stability parked — executed in parallel and promoted. Five of fifteen scenarios now
carry live gateway captures (crypto-wallet at midday, then unsigned-webhooks, oidc-portal,
rag-support-bot, and missing-docs in one wave), all on `openai/gpt-5.1` under
`openrouter-economy`, all replaying at `evidence_assessment_coverage` 1.0 — the DEC-134 shape
measured working on every live run it has ever had.

## What the wave measured

Two scenarios met their truth sets exactly: oidc-portal and missing-docs completed their
intended zero-finding paths (0 matched, 0 missed, 0 spurious) — the DEC-009 thesis case now
live-captured for cents. Two missed one expected finding each with zero spurious:
unsigned-webhooks' model judged the documented missing signature check a documentation gap
rather than an unmet control, and rag-support-bot's reviewer rejected all four
applicability-shaped candidates. Precision is perfect across the wave; recall is the measured
weakness, and with coverage at 1.0 the omission excuse is gone — what remains is lens, which
is #589's reconciliation and the scorecard's to show. Wave spend: ~$11.60; the day's total
with probes and pilots: ~$24.

## Two defects the wave caught, both now fixed

- **The zero-finding completion path rendered with a wall-clock stamp** — three of four
  captures completed zero-finding and none could round-trip until `stage_reason`'s resume
  pinned `GENERATED_AT` like the report stage does. Their promoted hashes are pinned from the
  deterministic double replay; each provenance says so.
- **The per-entry workflow pin re-shaped condition replays** — promoting a 0.2 clean capture
  beside an authored 0.1 adversarial recording would have broken the adversarial replays of
  unsigned-webhooks and rag-support-bot. The registry gained `condition_workflow_versions`
  (DEC-134 amendment): the pin belongs to the recording, and a condition carries its own. Both
  adversarial replays verified under their own pins.

Also proven again: the wedge playbook (one validation refusal at checkpoint 1 — the node
demanding `unknown` over a false-like `none`, exactly its job — recovered by rebuild-from-
staging at zero re-spend), and the round-trip tooling hardened twice (the replay scenario must
clone the registry entry: the name is in the report bytes, the catalog version is in the
mapping validation).

## Open next

Eight scenarios remain (~$5.25 each measured), the DEC-077 stability protocol on the new
model, live baselines for the remaining scenarios, then the history snapshot and scorecard
readout (#601 unblocks). The four tests that pinned the old unsigned-webhooks and oidc-portal
recordings were retargeted to untouched authored scenarios — the tests pin harness behaviour,
not one recording's outcome, and the retargets keep that true.
