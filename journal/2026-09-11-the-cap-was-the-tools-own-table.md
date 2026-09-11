# 2026-09-11 — The cap was the tool's own table

`rag-support-bot` had no completed Codex Security run: its one attempt stopped at the tool's
`--max-cost 10` limit after 620 s with a partial written. This session repeated the scan with the
limit raised to $20. It finished in 672 s and cost $4.85 at the provider's list price, never
approaching either number.

## What that says

The limit that stopped run 4 was not a statement about the work. Codex Security estimates cost from
a bundled table, and for `gpt-5.6-sol` that table runs about a third above the provider's list
price, so a limit chosen from list-price expectations stops a scan that would have cost well under
it. The three earliest attempts on `unsigned-webhooks`, which died inside three minutes under a $3
limit, are the same effect at a smaller scale. Where the tool's own estimate is what enforces the
ceiling, the ceiling has to be set in the tool's units, not the provider's.

## What the run found

The same three claims as the capped partial, none sharing a signature with it: cross-workspace
retrieval at `index.py:60` (FND-RSB-01, matched), the repository-known development bearer credential
at `config.py:24`, and a quota race at `quota.py:24`. Two spurious, both naming a catalogue
requirement, no rejection breached, three of three locators resolving. At the code layer, one true
positive, two false positives, no trap hit — identical counts to run 4, from different findings.

Both Codex runs map to the same three requirements while sharing no signature, which is the pattern
Mantis showed at five runs a scenario: the tool's identity key measures wording. Two runs are not a
rate, and the page says so.

The development-credential claim now stands in every completed run of both tools on this scenario.
That remains a DEC-149 argument to make from the truth set's own inputs rather than from a count of
who said it.

## What landed

- `results/codex-security/rag-support-bot-run-5.yaml`, hand-mapped under DEC-056.
- `docs/eval/reviewer-arms.md`: the scenario's Codex rows, the run-to-run paragraph, and the program
  section — sixteen jobs, $51.66 of the $60 cap, 9,477 s, thirteen verifying manifests.
- The scorecard and comparison regenerated: the Codex arm is now 9 of 9 locators, 6 spurious over
  two scenarios, 0 of 6 rejections breached.

## Open

Four Codex Security runs of the planned twenty were never started. Nothing here measures
reproduction, chaining, or patching, none of which ran.
