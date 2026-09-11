# Two code reviewers on the coded scenarios, scored as external arms

Google's Mantis and OpenAI's Codex Security reviewed `benchmarks/unsigned-webhooks/code/` and
`benchmarks/rag-support-bot/code/` at develop `c5b0590` (DEC-156), both driving `gpt-5.6-sol` through `api.openai.com`, and their findings were
hand-mapped and scored as non-authoritative arms under DEC-155. This page holds the per-run figures
behind the two external rows on the [comparison](comparison.md), one scenario per section; the feeds are committed under
`results/<arm>/`, the scored copies under the results tree, and every run is attested in the
attestrun repository's manifests. Captured 2026-09-11. Metrics and identifiers only (DEC-076).

## unsigned-webhooks

### What ran

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

### Requirement level, as emitted

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

### Requirement level, tool-validated

Under Mantis's own status vocabulary a finding is claimed when it is `VALID`. None was. In this view
Mantis claimed 0 findings in 5 of 5 runs: recall 0 of 5, spurious 0, breaches 0 of 10. Codex Security
carries no binary status; each of its three findings has a validation block with a stated method, so
its claimed set is the same three in both views.

### Code level, RealVuln-style

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

### Run-to-run agreement

Mantis's `signature` is a digest of normalised title, CWE, and primary path. Over the five runs the
19 distinct signatures each appear in exactly one run; pairwise Jaccard is 0.00 on signatures and on
signature-plus-status (attestrun `scripts/concordance.py`, over the five verified manifests). At the
requirement level the same runs agree: FND-UW-01 in 5 of 5, the replay claim in 3 of 5, the
request-buffering claim in 3 of 5, the outbox claim in 3 of 5. The tool finds the same things and
names them differently every time, so its own identity key measures wording, not findings.

### Against the reads the plan wrote down

The plan's negative read for Trace was that both reviewers would find FND-UW-01 in every run where
Trace's live recall on this scenario was 2 of 5, and that neither would breach above 6%. The first
half happened: 5 of 5 and 1 of 1 against 2 of 5. The second did not for Mantis: 3 of 10 breached,
every breach the replay rejection, which is the documentation-gap distinction this project exists
to keep. Neither tool breached the false-positive-class rejection, and Trace's figure there is 0 of
14. On precision, Mantis matched 5 of its 19 distinct claims and Codex Security 1 of 3; Trace's
spurious count on this scenario is on the [scorecard](scorecard.html). And under Mantis's own
validation vocabulary it claimed nothing at all, so the recall it earns here is recall the tool did
not stand behind.

What is not claimed here: anything about reproduction, chaining, or patching, which did not run; a cost
figure from a bill; or a property of either tool beyond these runs.

## rag-support-bot

The second coded scenario: thirteen Python files, one expected finding (FND-RSB-01, retrieval
unfiltered by the requester's workspace, `req-RAG-002`, component Retrieval index), one documentation
gap (deletion propagation, `req-RAG-003`), and two `no_evidence` rejections (`REJ-RSB-01`, ticket-borne
prompt injection is unmitigated, `req-AI-001`; `REJ-RSB-02`, the corpus write path is ungoverned,
`req-RAG-001`). The code layer carries one vulnerable entry at `index.py:search` and six traps, one
`non_scoring`.

### What ran

| Arm | Completed runs | Cost per run (list price) | Wall per run |
| --- | --- | --- | --- |
| mantis | 5 of 5 | $3.02, $2.52, $3.52, $2.76, $3.53 — mean $3.07 ± 0.44 | 847, 666, 710, 691, 769 s |
| codex-security | 0 of 1 completed; 1 capped partial | $7.11 list ($10.03 by the tool's table, its `--max-cost 10` limit) | 620 s |

Codex Security stopped at its own limit with `findings.json`, the SARIF export, and a checkpoint
written, so its three findings are scored below as a **capped partial**, labelled as such in the
feed. Every Mantis row was again `PROVISIONALLY_VALID`.

### Requirement level, as emitted

Mantis emitted 40 rows, 18 of them byte-identical within-run duplicates, leaving 22 distinct findings.
Codex Security's partial holds 3.

| Run | Emitted (distinct) | FND-RSB-01 | Spurious | Breached REJ-RSB-01 (`no_evidence`, prompt injection) | Breached REJ-RSB-02 (`no_evidence`, write path) | Locators resolve |
| --- | --- | --- | --- | --- | --- | --- |
| mantis run 1 | 7 | matched | 6 | yes | no | 7 of 7 |
| mantis run 2 | 4 | matched | 3 | no | no | 4 of 4 |
| mantis run 3 | 3 | matched | 2 | no | no | 0 of 3 |
| mantis run 4 | 3 | matched | 2 | no | no | 3 of 3 |
| mantis run 5 | 5 | matched | 4 | no | no | 0 of 5 |
| codex-security run 4 (capped partial) | 3 | matched | 2 | no | no | 3 of 3 |

Pooled: Mantis matched the expected finding in 5 of 5 runs, produced 17 spurious findings, every one
mapped to a catalogue requirement, and breached 1 of 10 scoreable rejections (run 1 asserted that
ticket-borne prompt injection reaches answers unmitigated, the claim `REJ-RSB-01` records the documents
answer). Locators: 14 of 22 resolve; in runs 3 and 5 Mantis again cited the target root and no file.
Codex Security's partial matched in 1 of 1 with 2 spurious and 0 of 2 breached.

The spurious findings fall into five claims. A repository-known development bearer credential is
accepted when production token configuration is absent (`req-SECRET-001`), in 5 of 5 Mantis runs and
in the Codex Security partial. Source identifiers are not qualified by workspace, so one tenant's
ingestion can replace another's chunks (`req-DATA-003`), in 5 of 5. Deleted or omitted tickets stay
retrievable (`req-RAG-003`), in 3 of 5, which is the gap the truth set records as undetermined and
which no rejection covers, so it is spurious and breaches nothing. Data leaving to the model provider
is not minimised or its destination is unrestricted (`req-AI-003`), in 2 of 5. And a quota race and an
unbounded request body (`req-TPI-002`), once each. The development-credential claim is made by both
tools in every completed run and names a fact the code layer's truth does not list; under DEC-149 that
is an argument about the truth set to be made from its inputs, recorded here and not acted on.

### Requirement level, tool-validated

Mantis claimed 0 findings in 5 of 5 runs. Codex Security's partial claims its 3.

### Code level, RealVuln-style

| Run | Distinct findings | True positives | False positives | Trap hits (of 5 scoring traps) | Non-scoring | No file cited | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mantis run 1 | 7 | 0 | 7 | 1 | 0 | 0 | 0 of 7 | 0 of 1 |
| mantis run 2 | 4 | 1 | 2 | 0 | 1 | 0 | 1 of 3 | 1 of 1 |
| mantis run 3 | 3 | 0 | 0 | 0 | 0 | 3 | 0 of 0 | 0 of 1 |
| mantis run 4 | 3 | 1 | 2 | 0 | 0 | 0 | 1 of 3 | 1 of 1 |
| mantis run 5 | 5 | 0 | 0 | 0 | 0 | 5 | 0 of 0 | 0 of 1 |
| codex-security run 4 (capped partial) | 3 | 1 | 2 | 0 | 0 | 0 | 1 of 3 | 1 of 1 |

Two rows show where the file rule and the requirement rule part. In run 1 Mantis located the
cross-workspace disclosure at the answer endpoint in `main.py` rather than at `index.py:search`, so
the requirement matcher credits it and the file rule does not; the same run's provider-exfiltration
claim lands on the `provider.py` trap (CWE-200 on `strip_identifiers`), the one trap hit in the
program. In run 2 the credited true positive is the source-replacement claim at `index.py:44`, which
shares the file and the CWE family with the vulnerable entry but concerns `replace_source`, while the
run's actual retrieval finding sits at `main.py` and is counted a false positive; RealVuln's rule
matches on file and CWE, and the page reports the rule's answer rather than adjusting it.

### Run-to-run agreement

Twenty-two distinct signatures, each seen in exactly one run; Jaccard 0.00 on both keys over the five
verified manifests. At the requirement level: FND-RSB-01 in 5 of 5, the development-credential claim
in 5 of 5, the tenant-separation claim in 5 of 5, deletion propagation in 3 of 5, provider
minimisation in 2 of 5, prompt injection in 1 of 5, the quota race in 1 of 5.

## The program

Twenty jobs were planned: two scenarios, two arms, five runs each. Fifteen ran. All ten Mantis runs
completed. Of Codex Security's attempts, three stopped at the tool's $3 limit inside three minutes
with nothing written, one completed under a $10 limit, and one stopped at the $10 limit with a
partial written; the remaining five Codex Security runs were not started once the cap behaviour was
known. List-price cost of the fifteen: $46.81 ($40.36 for the twelve runs the orchestrator finished
or capped, plus $6.45 for the three early capped attempts), against the program's $60 cap. Job time
summed: 8,805 s, about 2 h 27 min, with up to five jobs concurrent. Every completed run and both
capped partials are attested in attestrun manifests, twelve of which verify; the three early capped
attempts wrote no findings and have no manifest.

Across both scenarios the picture is the same. Both reviewers find the documented weakness in every
completed run where Trace's live recall was 2 of 5 and 3 of 5 on comparable findings. Mantis breaches
a rejection in 4 of 20 scoreable cases, three of them the replay gap and one the prompt-injection
`no_evidence` case, and never the false-positive-class rejection; Codex Security breaches none of 4.
Precision as emitted is 10 matched of 41 distinct Mantis claims and 2 of 6 for Codex Security. And
under Mantis's own validation vocabulary it claimed nothing in any of ten runs.

What is not claimed: anything about reproduction, chaining, or patching, which did not run; a cost
figure from a bill; or a property of either tool beyond these fifteen runs.
