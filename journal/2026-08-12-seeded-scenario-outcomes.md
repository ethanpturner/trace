# 2026-08-12 — husky-ai and crypto-wallet reach full outcome truth (#327)

Fourth M11 delivery of the day. The two OWASP-seeded scenarios carried threat truth only —
contributing seeds and nothing to the scorecard. Both now have full outcome truth sets in the
DEC-027 layout and offline recordings, replay through `trace evaluate`, and score exactly:
husky-ai matches its two expected findings and two gaps with nothing spurious, and
crypto-wallet is the third zero-finding scenario, producing one gap and one question and not
a single finding. Every registered scenario is now fully authored and none is skipped.

## The authoring judgments

The truth sets were the real work; the recordings follow the #326 pattern (evidence
identifiers minted for real from a scratch ingest, DEC-025's false-positive field addressed
by name on every unmet mapping, generated context decisions).

**husky-ai** — the source threat list stays threat truth; the findings rest on the input
documents' own affirmative statements:

- *FND-HA-01 (req-AUTH-002)*: the experimental environment — which trains and ships the
  model production serves — sits behind password authentication alone, while production is
  SSO. The documented-negative reading rests on the security notes' own completeness
  statement ("records what is implemented; does not list planned work"), so the recording
  extracts that statement as a claim: it is load-bearing, and a run that dropped it would
  have no honest route to the finding.
- *FND-HA-02 (req-SECRET-001)*: the image-service API keys are documented as living in a
  blob storage account, not a secret store. A stated mechanism falling short of the
  requirement, not an absence.
- The silences the threat-truth header itself names — supply-chain verification, volume
  bounding — resolve to the two gaps (req-CICD-001, req-TPI-002), and the documented
  controls (blob ACLs, in-memory uploads, Bastion logging) become rejections. Six of the
  nine recorded threats map to no requirement and produce nothing, which is the honest
  shape: most of the source's entries rest on preconditions the documents leave open.

**crypto-wallet** — the scenario's point is its two hedged statements, and the truth set
keeps them hedged: zero findings by design. Wallet-file encryption ("encryption is a wallet
option") surfaces as a consolidation question via `downgrade_to_question` — the answer is
obtainable, which is section 16's own test — while the exchange-store silence becomes the one
gap, whose requested evidence carries the TLS re-verification the document itself marks
outstanding. Treating either hedge as a fact, in either direction, is the graded failure and
the rejections say so.

## Fallout

- The registry advances both to `status: authored`; the trailing comment now states the
  whole register replays, with only #328's categories missing.
- The `evaluate --all` test now asserts no scenario is skipped, and the no-recording refusal
  test fabricates a registry-scoped scenario, since no real one lacks a recording anymore.
- The evaluation pages regenerate with the two new rows, and a third DEC-081 snapshot is
  retained — three in one day, each keyed to the ref its sweep ran on, which is the history
  mechanism doing its job across a fast-moving scenario set.

## Open next

Five M11 issues remain: #328 (the missing scenario categories — third-party integrations,
duplicate threats, large architecture input, explicit missing documentation), #329 (reserved
metrics; the question and threat truth authored today and in #326 gives it truth sources to
compute against), and the live-run trio #330/#331/#332.
