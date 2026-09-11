# Two code reviewers on a coded scenario, scored as external arms

Google's Mantis and OpenAI's Codex Security reviewed `benchmarks/unsigned-webhooks/code/` at develop
`c5b0590` (DEC-156), both driving `gpt-5.6-sol` through `api.openai.com`, and their findings were
hand-mapped and scored as non-authoritative arms under DEC-155. This page holds the per-run figures
behind the two external rows on the [comparison](comparison.md); the feeds are committed under
`results/<arm>/`, the scored copies under the results tree, and every run is attested in the
attestrun repository's manifests. Captured 2026-09-11. Metrics and identifiers only (DEC-076).

## What ran

| Arm | Tool | Harness | Effort | Completed runs | Cost per completed run (list price) | Wall per run |
| --- | --- | --- | --- | --- | --- | --- |
| mantis | google/mantis @ `d13c93f` | the ADK reference harness, `workflow.pilot.json` (history through report; no reproduce, chain, or patch), sandbox static-only | medium | 5 of 5 | $2.42, $2.91, $2.59, $2.11, $3.09 — mean $2.62 ± 0.38 | 713, 748, 680, 614, 702 s |
| codex-security | openai/codex-security 0.1.26 | its own CLI, `--mode standard --headless` | high | 1 of 4 attempts | $4.81 (the tool's own estimate: $6.76) | 602 s |

The three Codex Security attempts that did not complete ran under the tool's own `--max-cost 3` and
stopped at its limit after 135, 137, and 171 seconds, spending $2.14, $2.16, and $2.15 at list price
($3.10, $3.13, $3.10 by the tool's stricter table) and writing no findings. The completed run had the
limit raised to $10. Both figures are estimates from token counts; no provider bill was read.

Mantis's ADK harness has no snapshot mode, so the reviewed SHA is recorded by the run script and the
attestation, not by the tool. Its review and critic stages left every finding `PROVISIONALLY_VALID`
in every run: under the tool's own gates, Mantis confirmed nothing. The figures below therefore come
in two views, and each table says which it uses.

## Requirement level, as emitted

Every emitted finding was mapped by hand to a catalogue requirement and a component under the
DEC-056 rule, or recorded as naming no requirement. Mantis emitted 32 rows over five runs, 13 of
them byte-identical duplicates within a run (run 2 emitted every finding twice), leaving 19 distinct
findings. Codex Security emitted 3.

| Run | Emitted (distinct) | FND-UW-01 | Spurious | Named no requirement | Breached REJ-UW-01 (replay, `documentation_gap`) | Breached REJ-UW-02 (`common_false_positives`) | Locators resolve |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mantis run 1 | 4 | matched | 3 | 1 | no | no | 3 of 3 |
| mantis run 2 | 6 | matched | 5 | 1 | yes | no | 5 of 5 |
| mantis run 3 | 3 | matched | 2 | 1 | yes | no | 0 of 2 |
| mantis run 4 | 2 | matched | 1 | 1 | no | no | 1 of 1 |
| mantis run 5 | 4 | matched | 3 | 1 | yes | no | 3 of 3 |
| codex-security run 4 | 3 | matched | 2 | 0 | no | no | 3 of 3 |

Pooled: Mantis matched the one expected finding in 5 of 5 runs and produced 14 spurious findings, 5
of them naming no catalogue requirement; it breached 3 of 10 scoreable rejections, all three the
replay rejection, none the false-positive-class rejection. Codex Security matched in 1 of 1 and
produced 2 spurious findings with 0 of 2 rejections breached. In run 3 Mantis cited the target's
root directory and no file for every finding, so 0 of its 2 mapped locators resolve; the other four
runs cite `path:line` that resolves at the snapshot in every case.

The spurious findings are of three kinds. Unbounded request buffering and an unbounded tokenless
outbox, mapped to `req-TPI-002` (work triggered by an external event is bounded), which the truth set
does not carry for this scenario. A record-before-send ordering that suppresses retries after a
failed post, which names no security requirement in catalog 0.1. And in three runs a claim that the
in-memory delivery ledger is inadequate replay protection, mapped to `req-WEBHOOK-002`, which is the
claim `REJ-UW-01` says a correct assessment does not make: the documentation is silent on replay and
the truth records a gap, not a finding.

## Requirement level, tool-validated

Under Mantis's own status vocabulary a finding is claimed when it is `VALID`. None was. In this view
Mantis claimed 0 findings in 5 of 5 runs: recall 0 of 5, spurious 0, breaches 0 of 10. Codex Security
carries no binary status; each of its three findings has a validation block with a stated method, so
its claimed set is the same three in both views.

## Code level, RealVuln-style

`expected/code-ground-truth.yaml` lists one vulnerable entry and five traps, one of them
`non_scoring`. A finding matches an entry by cited file and a CWE in the entry's acceptable set;
the two `main.py` entries sharing CWE-306 are separated by the cited line against the function
span. `scripts/score_code_layer.py` computes the table.

| Run | Distinct findings | True positives | False positives | Trap hits (of 4 scoring traps) | Non-scoring | No file cited | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mantis run 1 | 4 | 1 | 3 | 0 | 0 | 0 | 1 of 4 | 1 of 1 |
| mantis run 2 | 6 | 1 | 4 | 0 | 1 | 0 | 1 of 5 | 1 of 1 |
| mantis run 3 | 3 | 0 | 0 | 0 | 0 | 3 | 0 of 0 | 0 of 1 |
| mantis run 4 | 2 | 1 | 1 | 0 | 0 | 0 | 1 of 2 | 1 of 1 |
| mantis run 5 | 4 | 1 | 2 | 0 | 1 | 0 | 1 of 3 | 1 of 1 |
| codex-security run 4 | 3 | 1 | 2 | 0 | 0 | 0 | 1 of 3 | 1 of 1 |

No run flagged a trap: the unused HMAC helper, the environment-read bearer token, the plain-text
message formatter, and the liveness probe drew no finding from either tool. Codex Security's
validation block for the authentication finding names the unused helper as the expected control,
which is the reading the trap was written to test.

## Run-to-run agreement

Mantis's `signature` is a digest of normalised title, CWE, and primary path. Over the five runs the
19 distinct signatures each appear in exactly one run; pairwise Jaccard is 0.00 on signatures and on
signature-plus-status (attestrun `scripts/concordance.py`, over the five verified manifests). At the
requirement level the same runs agree: FND-UW-01 in 5 of 5, the replay claim in 3 of 5, the
request-buffering claim in 3 of 5, the outbox claim in 3 of 5. The tool finds the same things and
names them differently every time, so its own identity key measures wording, not findings.

## Against the reads the plan wrote down

The plan's negative read for Trace was that both reviewers would find FND-UW-01 in every run where
Trace's live recall on this scenario was 2 of 5, and that neither would breach above 6%. The first
half happened: 5 of 5 and 1 of 1 against 2 of 5. The second did not for Mantis: 3 of 10 breached,
every breach the replay rejection, which is the documentation-gap distinction this project exists
to keep. Neither tool breached the false-positive-class rejection, and Trace's figure there is 0 of
14. On precision, Mantis matched 5 of its 19 distinct claims and Codex Security 1 of 3; Trace's
spurious count on this scenario is on the [scorecard](scorecard.html). And under Mantis's own
validation vocabulary it claimed nothing at all, so the recall it earns here is recall the tool did
not stand behind.

What is not claimed: anything about `rag-support-bot`, whose runs are pending; anything about
reproduction, chaining, or patching, which did not run; a cost figure from a bill; or a property of
either tool beyond these six runs.
