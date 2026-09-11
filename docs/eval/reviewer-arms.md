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

## The exchange into Mantis: Trace's approved outputs as inputs

Two of the plan's exchange steps feed Trace's approved outputs into Mantis. Both ran on
`unsigned-webhooks` at `c5b0590`, gpt-5.6-sol via `api.openai.com`, medium effort, the ADK reference
harness with `workflow.pilot.json`, on 2026-09-11. The five unseeded Mantis runs above are the
baseline. Every run here is attested (manifests `unsigned-webhooks-mantis-seeded-run-{1..5}.json` and
`unsigned-webhooks-mantis-sast-run-{1,2}.json` in the session's `exchange-b/manifests/`; all
`verified`).

### Seeded knowledge base: Trace's approved context before the architecture stage

Mantis's threat-model stage reads only `workspace/kb/`, which its architecture stage writes from
code. The harness stores that workspace in `knowledge.db`, keyed by a run identifier the harness
mints at start and reads back strictly, so seeding means pinning the identifier and writing the
files under it before launch. A wrapper did that (it pins the harness's own `uuid` reference, seeds
six files, then hands over to the unchanged launcher). The seed was Trace's approved system context
for this scenario, written in the knowledge base's own shape: `architecture.md`, `index.md`, and
four entity files for the Event Receiver, Chat Notifier, CI Platform, and Chat Platform. It carried
the approved components, actors, assets, three data flows, the one approved trust boundary, the
documented statement that the receiver checks no signature, and the approved documentation-gap
wording for replay: not described, recorded as a gap, no conclusion drawn from silence. It carried no
truth-set material: no finding, no rejection, no gap as an answer, and a test bans those tokens from
the seed. Five runs.

**What the pipeline did with the seed.** In every run the architecture stage read all six seeded
files (twelve `read_file` calls) and then rebuilt all six from code, as its skill instructs when no
snapshot is pinned. None of the seed's provenance or gap language survived into the rebuilt
`architecture.md` (0 of 5 runs mention a documentation gap, "not described", or the seed's
provenance line). What did survive is structure: all five rebuilt knowledge bases kept the CI Platform
and Chat Platform as entity files, which 0 of 5 unseeded runs had, and the rebuilt threat models
name the Chat Platform 3 to 6 times where the unseeded ones named it 0 to 1 times. The threat-model,
planner, and researcher stages read the rebuilt files, not the seed. So the experiment measures a
seed filtered through the architect, which is the only path this harness offers.

| Run | Emitted (distinct) | FND-UW-01 | Spurious | Named no requirement | Breached REJ-UW-01 (replay) | Breached REJ-UW-02 | Locators resolve | Cost (list) | Wall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seeded run 1 | 5 | matched | 4 | 2 | yes | no | 3 of 3 | $2.86 | 945 s |
| seeded run 2 | 3 | matched | 2 | 1 | yes | no | 2 of 2 | $2.45 | 868 s |
| seeded run 3 | 3 | matched | 2 | 1 | yes | no | 2 of 2 | $2.63 | 766 s |
| seeded run 4 | 3 | matched | 2 | 1 | yes | no | 2 of 2 | $2.65 | 748 s |
| seeded run 5 | 7 | matched | 6 | 2 | yes | no | 5 of 5 | $2.83 | 878 s |

| | Unseeded (5 runs) | Seeded knowledge base (5 runs) |
| --- | --- | --- |
| FND-UW-01 matched | 5 of 5 | 5 of 5 |
| Distinct claims | 19 | 21 |
| Spurious | 14 (5 naming no requirement) | 16 (7 naming no requirement) |
| REJ-UW-01 replay breached | 3 of 5 | 5 of 5 |
| REJ-UW-02 false-positive class breached | 0 of 5 | 0 of 5 |
| Locators resolve | 12 of 14 | 14 of 14 |
| Within-run duplicate rows collapsed | 13 of 32 | 9 of 30 |
| Code layer: true positives / trap hits | 4 of 5 runs, 0 traps | 5 of 5 runs, 0 traps |
| Cost, mean ± sd (list) | $2.62 ± 0.38 | $2.68 ± 0.17 |

**Reading.** Seeding Trace's approved context into the knowledge base did not reduce Mantis's
assertion of the replay documentation gap as a finding. Unseeded, it asserted an inadequate replay
ledger in 3 of 5 runs; seeded with the approved wording that replay is undetermined and recorded as
a gap, it asserted it in 5 of 5. The mechanism is visible in the transcripts: the architect
rebuilt the knowledge base from code and the sentence about the gap did not survive the rebuild, so
the threat-model and research stages never saw it. The seed changed what the knowledge base was
about (two external platforms became entities, the threat models say more about the outbound
boundary) and not what the reviewer concluded. The spurious count moved from 14 to 16 over five
runs, with the record-before-send reliability claim present in every seeded run as in the unseeded
ones, and the resource-exhaustion family (unbounded body buffering, unbounded outbox), which
appeared in 3 of 5 unseeded runs, appearing in 5I of 5 seeded runs. With five runs a side, none of
these differences is a claim about the tool; they are the counts observed.

What this does not test: seeding in skills mode, where a human runs the architecture skill against
an existing knowledge base and can tell it to preserve entries; a seed placed after the architecture
stage, which would require a workflow that skips it; or Codex Security's `--knowledge-base` flag,
which its documentation describes for policy generation.

### SAST seed: Trace's approved finding and gap as Mantis candidates

Mantis documents an intake for external findings, the SAST-seed JSONL intermediate representation
(`mantis-pipeline-adapter/references/mantis-sast-seed.md`): candidates enter as `PROVISIONALLY_VALID`
and "must earn their verdict through unchanged downstream gates". The ADK reference harness does not
consume that file. Nothing under `reference/` reads `workspace/sast_findings.jsonl`; the only trace
is a `sast_provenance` field on the finding schema. So the two candidates were converted to the IR
(three fields per candidate: `rule_id`, `severity`, `code_paths`, plus `message`, `rule_name`, `cwe`, under a provenance header; the file is in the session's `exchange-b/sast-seed/`), then written into the harness's finding
store under the run's identifier with status `PROVISIONALLY_VALID`, and a review-only workflow ran:
reviewer, its classifier, critic, its classifier, calibrator, reporter. The threat model those stages
read was the one unseeded run 1 produced. Two runs, gpt-5.6-sol via api.openai.com, medium effort.

The two candidates were Trace's approved finding FND-UW-01 (inbound deliveries processed without
verifying authenticity, `req-WEBHOOK-001`, severity guidance medium, CWE-345) and the approved
documentation gap GAP-UW-01 (replay handling not described, `req-WEBHOOK-002`), the latter seeded as
a LOW candidate whose message says it is a gap, not a finding, and should not be confirmed unless the
code shows replay unhandled. Both carried `code_paths: deploy_notifier/main.py`, mapped from the
component the documentation names to the module that implements it.

| Run | Reviewer route | Critic route | FND-UW-01 candidate | GAP-UW-01 candidate | Cost (list) | Wall |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `confirmed` | `viable` | `PROVISIONALLY_VALID`, priority LOW, risk 2.0 of 10 (impact 4, likelihood 3) | `PROVISIONALLY_VALID`, priority LOW, risk 1.4 of 10 (impact 1, likelihood 1) | $0.64 | 169 s |
| 2 | `confirmed` | `viable` | `PROVISIONALLY_VALID`, priority LOW, risk 2.0 of 10 (impact 4, likelihood 3) | `PROVISIONALLY_VALID`, priority LOW, risk 2.0 of 10 (impact 2, likelihood 1) | $0.66 | 162 s |

What the gates did with each candidate, in both runs:

- **The authenticity finding.** The reviewer read `main.py`, `replay.py`, `events.py`, `config.py`
  and routed `confirmed`; its one-sentence reason names the unused `CI_SIGNING_SECRET` and the
  unauthenticated `POST /events` handler. The critic read `signing.py` as well and routed `viable`.
  The calibrator then scored it 2.0 of 10, priority LOW, because no reproduction was attempted, and
  the report lists it under "calibration-only records, not verified", with "if confirmed dynamically"
  in its impact sentence. Trace's approved severity guidance for the same finding is medium.
- **The replay gap.** Neither the reviewer's nor the critic's reason mentions it as a weakness. Run 1's
  calibration note reads the ledger as blocking reuse of a captured identifier and folds the record
  into the authenticity finding "rather than a distinct replay weakness"; run 2's says the record "is
  an unproven documentation/code-review candidate" that "must not be confirmed" without evidence of
  a missing timestamp or nonce check. Both kept it at LOW and neither promoted it. That is the
  disposition the seed asked for, and it is also the disposition Mantis's own unseeded runs did not
  reach: three of five unseeded runs asserted inadequate replay protection as a finding.

What did not happen: no candidate reached `VALID`. The harness has no tool by which the reviewer or
critic writes a per-finding status; their verdicts are one route per run, and the status column
stays whatever the finding entered with. "Which candidates survive `VALID`" therefore has no answer
in this harness, and the per-finding signal is the calibration record and the prose that names it.
The two review-only runs are attested (manifests `unsigned-webhooks-mantis-sast-run-{1,2}.json`
in the session's `exchange-b/manifests/`; both `verified`). They are not committed as a DEC-155 arm:
scoring Trace's own findings against Trace's truth set would measure nothing.
