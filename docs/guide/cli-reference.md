# CLI reference

Every Trace command is a subcommand of `trace`, run from a source checkout as `uv run trace`.
This page lists each command with its flags, argument shapes, and exit codes. It documents what
the tool does today; the output of `--help` for any command is the same surface.

## Exit codes

Exit codes are answers a script can branch on without parsing prose:

| Code | Meaning |
|------|---------|
| 0    | The command did what it was asked. A run pausing at a checkpoint is success, not a fault. |
| 1    | An error the operator can fix, named in one line on stderr, no traceback. |
| 2    | argparse rejected the arguments (the standard-library convention). |
| 3    | A stated refusal that is an answer, not a fault. |

Code 3 is kept distinct from code 1 so that "refused" and "crashed" are not the same signal. A
refusal answers a yes/no question: the context is not approvable yet, the evidence drifted, the
dry run would remove these files. Six commands emit it:

- `reset` without `--force` (a dry run: it lists what would go and removes nothing)
- `assessment purge` without `--force` (the same dry-run contract)
- `evidence verify` when any reference no longer matches its source
- `verify` when any document, evidence reference, or the report manifest drifted
- `context show` when the context cannot be approved yet (the blockers are listed)
- `context approve` when open blockers prevent approval (every blocker is named, not just the first)

One deliberate exception to the one-line rule for code 1: a pydantic `ValidationError` raised by
the pipeline keeps its full traceback, because a domain object failing validation is a bug in
Trace, not operator input, and hiding it would make the tool lie about what happened.

## Global behavior

**Bare invocation.** `uv run trace` with no arguments prints the environment, the log level, and
which credentials are configured — by name only, never a value.

**`--data-root DATA_ROOT`** is the one global flag, and it goes before the subcommand:
`uv run trace --data-root /path assessment list`. It names where assessments are stored; the
default is the repository's `data` directory.

**Clone-only.** Trace v0.1 runs from a source checkout (`git clone` plus `uv sync`), because
prompts, the requirements catalog, the report template, and the scenario registry are repository
files. From an installed wheel, `trace` and `trace --help` still work; every command past the
banner exits 1 with `SourceCheckoutRequiredError`.

**Shared model flags.** `run`, `resume`, and `context extract` take the same four flags:

- `--model-profile MODEL_PROFILE` — the provider, model, and settings bundle. Five profiles
  exist: `primary-development` (Anthropic, claude-opus-5, the default), `economy` (Anthropic,
  claude-sonnet-5), `economy-mapping` (claude-opus-5 with the mapping agent overlaid onto
  claude-sonnet-5, DEC-094), `openai-experimental` (OpenAI, gpt-5.1, DEC-095), and
  `offline-fake` (a deterministic substitute: no key, no network, zero cost — a first-class way
  to run, not a test hook).
- `--response PATH` — a recorded model response to replay. Repeatable; files are consumed in the
  order given, one per model call the run makes. A directory stands for its numbered recordings
  in sorted order, so `--response demo/forgeflow/recorded/extraction` replays that whole slice.
- `--max-model-calls N` — stop the run before exceeding this many model calls.
- `--max-cost COST` — stop the run before exceeding this estimated cost.

Exceeding a ceiling stops the run with a named error; it never skips a step or shrinks a request.

**JSON output.** Read commands take `--json` (DEC-096) and print one JSON object: a `kind`
naming what it is, `data_model_version` naming the schema generation, and the same information
the human view prints — no more. Quoted source content appears only where the human view prints
it (`evidence show`), so a script never puts document content on screen as a side effect of
listing what exists. Exit codes are unchanged: `context show --json` still exits 3 while the
context cannot be approved.

**Identifiers in examples.** Identifiers like `asm-001` are allocated in order from a fresh data
root; on a reused data root the next create mints `asm-002` and any transcript diverges.
`uv run trace reset --force` returns the data root to the fresh-clone state and is destructive.

**No absolute paths.** The CLI never prints an absolute path. On disk the rendered report lives
under `data/assessments/<id>/outputs/` next to its `.manifest.json`, but you read it with
`trace report show`.

## assessment

Create and inspect assessments.

### assessment create

```
trace assessment create --name NAME [--description DESCRIPTION] [--tag TAG]
                        [--catalog-version CATALOG_VERSION]
```

Creates an assessment and prints its identifier. `--name` is required; `--tag` is repeatable.
`--catalog-version` pins the requirements catalog version the assessment is assessed against
(DEC-010, DEC-098); the default is the loader's current version. Exits 0 on success, 1 on a
named error.

```console
$ uv run trace assessment create --name "ForgeFlow review" --tag demo
```

**assessment list** — `trace assessment list`. Lists every assessment in the data root. Exits 0.

**assessment status** — `trace assessment status <assessment_id>`. Reports the assessment's
state: the deliverable's lifecycle status, its workflow runs, and where a paused run is waiting.
Exits 0, or 1 for an unknown identifier.

**assessment candidates** — `trace assessment candidates <assessment_id>`. Lists catalog-gap
candidates for the catalog owner — requirements the analysis suggested the catalog is missing.
Exits 0, or 1 for an unknown identifier.

### assessment approve

```
trace assessment approve <assessment_id>
```

The final human sign-off: the statement that you have read the rendered report and stand behind
it. Refused (exit 1, with the reason named) while no report exists, while the report's run is not
completed, or when that run is non-authoritative. This is a different command from
`findings approve`, which concludes checkpoint 2 so the run can continue.

**assessment archive** — `trace assessment archive <assessment_id>`. Retires an assessment.
Exits 0, or 1 for an unknown identifier or a state that cannot be archived.

**assessment purge** — `trace assessment purge [--force] <assessment_id>`. Deletes one
assessment entirely: every stored object, its identifier counters, and its whole directory.
Without `--force` it prints what would go, removes nothing, and exits 3; with `--force` it
removes and exits 0. Unknown identifier: exit 1.

## source

Register and inspect source documents.

### source add

```
trace source add [--no-index] <assessment_id> <path>
```

Registers a file or a directory of files. Accepted formats are `.md`, `.markdown`, `.txt`,
`.json`, `.yaml`, and `.yml`, each at most 10 MB, valid UTF-8, and JSON/YAML must parse. PDF,
Office, repository, and web ingestion are deferred and refused with a named error (exit 1).
`--no-index` registers without normalizing and indexing. Exits 0 on success.

```console
$ uv run trace source add asm-001 demo/forgeflow/input
```

**source list** — `trace source list <assessment_id>`. Lists registered documents. Exits 0.

## evidence

Inspect evidence references — the excerpts every claim and finding points back to.

**evidence list** — `trace evidence list [--source SOURCE_DOCUMENT_ID] <assessment_id>`. Lists
evidence references, one line each with source, line range, and location. `--source` filters to
one document. Exits 0.

### evidence show

```
trace evidence show <evidence_id> --assessment <assessment_id>
```

Prints one evidence reference in full, including the quoted source text — the only command that
prints document content, because that is its purpose. Note the shape: the evidence identifier is
the positional argument and the assessment arrives as `--assessment`, inverted relative to every
other command. Exits 0, or 1 for an unknown identifier.

```console
$ uv run trace evidence show evd-001 --assessment asm-001
```

**evidence verify** — `trace evidence verify <assessment_id>`. Re-checks every evidence
reference against its stored source. Exits 0 when everything matches, 3 when any reference no
longer does — each failure named with its identifier and outcome.

## context

The checkpoint-1 interface: extract, review, and approve the context.

### context extract

```
trace context extract [model flags] <assessment_id>
```

Runs the extraction slice only — extract and validate a context, then stop at the review
checkpoint. Takes the four shared model flags described under Global behavior. Exits 0 when the
checkpoint is reached, 1 on a classified error.

```console
$ uv run trace context extract asm-001 --model-profile offline-fake \
    --response demo/forgeflow/recorded/extraction
```

### context show

```
trace context show [--evidence] [--observations] <assessment_id>
```

Prints the review package for the pending checkpoint: components, claims, open questions,
observations, human-review triggers, and any outstanding validation errors. `--evidence` adds the
source excerpt behind each claim. `--observations` prints only what the extraction observed about
the documents themselves — injection attempts and contradictions awaiting resolution. Exits 0
when the context is ready to approve, 3 when it is not, with every approval blocker listed.

### context review

```
trace context review [--reviewer REVIEWER] [--export PATH | --apply PATH]
                     [--approve ID] [--reject ID] [--confirm ID]
                     [--answer ID=TEXT] [--attach ID=EVD[,EVD...]]
                     [--resolve ID=VALUE --rationale RATIONALE]
                     [--request-re-extraction REASON]
                     <assessment_id>
```

Records reviewer decisions. Flags serve for a decision or two; `--export` writes an editable
review file for a real review, and `--apply` applies it back. Both paths write the same decision
rows.
The exported file is derived, not stored; applying an unchanged export records zero decisions, by
design.

- `--approve ID` / `--reject ID` decide an object or claim.
- `--confirm ID` records a claim as user-confirmed.
- `--answer ID=TEXT` answers an open question.
- `--attach ID=EVD[,EVD...]` links existing evidence references to an object or claim.
- `--resolve ID=VALUE` settles a contradiction observation with VALUE and requires `--rationale`.
- `--request-re-extraction REASON` rejects the extracted context and says what was wrong.
- `--reviewer` names who the decisions are attributed to; the default is the operating-system
  username.

Exits 0 on recorded decisions, 1 on a malformed pair, an unknown identifier, or an unreadable
file.

### context approve

```
trace context approve [--reviewer REVIEWER] [--note NOTE] <assessment_id>
```

Approves the context baseline. Exits 0 and prints the approved version; exits 3 while anything
blocking is open — an unanswered blocking question or an outstanding validation error — naming
every blocker rather than the first. An undecided subject is not a blocker: approval succeeds
with decisions still missing, but the checkpoint advances only when every subject has one, so
`resume` pauses again until `context review` has decided them. `--note` records why the baseline
was approved.

## run and resume

### run

```
trace run [model flags] <assessment_id>
```

Runs every phase the transition table names, in order, and stops where the table stops: at a
checkpoint (exit 0 — the run is paused and waiting for a person), at completion (exit 0), or at a
classified error (exit 1). Pausing is stopping: the process exits, and `trace resume` continues
in a new one. There is no daemon.

```console
$ uv run trace run asm-001 --model-profile offline-fake \
    --response demo/forgeflow/recorded/extraction
```

In live mode, drop the offline flags and let `--model-profile` default to `primary-development`;
an `ANTHROPIC_API_KEY` must be configured. `--max-cost` and `--max-model-calls` bound the spend.

### resume

```
trace resume [--run WORKFLOW_RUN_ID] [model flags] <assessment_id>
```

Loads the paused state, re-runs the checkpoint, and continues when every subject has a decision.
With subjects still undecided the run pauses again, which is partial progress rather than an
error — exit 0 either way; exit 1 on a classified error. `--run` names a specific paused run when
the assessment has more than one.

## findings

The checkpoint-2 interface: review and approve candidate findings.

**findings show** — `trace findings show <assessment_id>`. Prints the review package for the
finding checkpoint, findings first, evidence excerpts labelled. Exits 0.

### findings review

```
trace findings review [--reviewer REVIEWER] [--export PATH | --apply PATH]
                      [--severity ID=LEVEL] [--edit ID FIELD=VALUE]
                      [--treatment ID=VALUE] [--treatment-rationale TEXT]
                      [--treatment-review-by YYYY-MM-DD]
                      [--approve ID] [--reject ID] [--note NOTE]
                      [--override-rationale TEXT]
                      [--defer ID] [--request-more-analysis ID]
                      <assessment_id>
```

Records finding decisions. Within one invocation, severity, treatment, and edits land before
rejections and approvals, so `--severity fnd-001=medium --approve fnd-001` means what it reads
as.

- `--severity ID=LEVEL` assigns a severity. Severity is the reviewer's to give: no pipeline step
  proposes one, and a finding cannot be approved while its severity is unassigned.
- `--edit ID FIELD=VALUE` changes one field, validated in full and recorded with the delta.
- `--treatment ID=VALUE` assigns a risk treatment: `undecided`, `mitigate`, `accept`, `transfer`,
  or `avoid`. Approving a finding treated as `accept` requires `--treatment-rationale`, the
  residual-risk statement; `--treatment-review-by` optionally dates a revisit.
- `--override-rationale` approves past the deterministic gate, with the override recorded.
- `--defer ID` leaves the finding a candidate, with the deferral as the record.
- `--request-more-analysis ID` requires `--note` saying what is missing.
- `--export` / `--apply` work as in `context review`; the file reaches every reviewer action.

Exits 0 on recorded decisions, 1 on a malformed pair, an unknown identifier, or a decision the
gate refuses.

### findings approve

```
trace findings approve <assessment_id>
```

Concludes the finding review once every finding is decided, so the run can continue with
`trace resume`. Exits 0; with findings still undecided it exits 1 naming them. This is not the
final sign-off — that is `assessment approve`, after the report exists.

## report

### report show

```
trace report show [--manifest] [--json] <assessment_id>
```

Prints the rendered Markdown report, or with `--manifest` the report's manifest instead. Exits 1
while no report exists. `--json` wraps the same body — the report text, or the parsed manifest —
in the DEC-096 envelope.

### report rubric

```
trace report rubric [--score CATEGORY=N]... [--comments COMMENTS]
                    [--reviewer REVIEWER] <assessment_id>
```

Records the reviewer rubric: seven categories, each scored one to five by a person, all required
in one invocation so a stored rubric is never partial. The categories are `context_accuracy`,
`threat_quality`, `finding_usefulness`, `false_positives`, `evidence_quality`, `report_quality`,
and `overall_confidence`. Exits 0 when all seven are scored, 1 otherwise.

## verify

```
trace verify [--json] <assessment_id>
```

Walks the whole evidence chain: every stored document against its recorded hash, every evidence
reference against its source, and the report manifest against the store. Exits 0 when everything
verifies. Exits 3 on any drift, with each drift named — identifier, expected hash, found hash —
and never the content that changed. `--json` carries the walk's counts and the same drift
entries in the DEC-096 envelope; the exit codes are unchanged by the flag.

## export

**export tm-bom** — `trace export tm-bom <assessment_id>`. Exports the approved model as a
TM-BOM document, written to the assessment's outputs area. Exits 0, or 1 when the export is
refused (for example, with no approved context).

**export mermaid** — `trace export mermaid <assessment_id>`. Exports the approved architecture
as a deterministic Mermaid flowchart source (`.mmd`) in the assessment's outputs area:
components as nodes, actors as external entities, data flows as labelled edges (an unknown
direction renders undirected), trust boundaries as subgraphs. Never model-drawn, never embedded
in the report. Exits 0, or 1 when refused.

**export sarif** — `trace export sarif <assessment_id>`. Exports the approved findings as a
SARIF 2.1.0 log, written to the assessment's outputs area. A finding's level follows the
reviewer-assigned severity; a documentation gap exports as kind `review` at level `none` — it
asserts nothing about the implementation, so it is never an error or a warning. Cited
requirements become rules, titled from the assessment's pinned catalog version where they
resolve. Exits 0, or 1 when the export is refused.

## evaluate

```
trace evaluate [scenario] [--all] [--condition CONDITION]
               [--baseline {generic,structured}] [--ablation-set]
               [--stability N] [--model-profile MODEL_PROFILE]
               [--ablate NAME] [--label LABEL] [--work-root WORK_ROOT]
               [--diff-against LABEL] [--results-root RESULTS_ROOT]
               [--report {scorecard,comparison,ablation}] [--out OUT] [--json]
```

Replays a registered benchmark scenario through the ordinary pipeline, offline, from its
committed recording. Metrics persist with the replayed assessment; a derived feed lands under
`benchmarks/results/`, keyed by scenario, condition, and label. A scenario without a recording is
refused by name.

- `--all` runs every registered scenario that has a recording, naming the ones skipped.
- `--baseline {generic,structured}` scores a single-pass baseline instead of the pipeline.
- `--ablation-set` runs the authoritative pipeline and each ablation for one scenario.
- `--ablate NAME` (repeatable) applies an ablation; the run is marked non-authoritative.
- `--stability N` runs one scenario N times live; it refuses the offline profile, which would
  measure nothing.
- `--label`, `--condition`, `--work-root`, `--results-root`, and `--diff-against` control where
  the feed lands and what it is compared against.
- `--report scorecard|comparison|ablation` runs the offline sweep and renders one evaluation
  page to stdout or `--out`; the committed pages under `docs/eval/` remain the build scripts'
  deliberate step.
- `--json` prints one envelope with the per-run metrics, statuses, adversarial block, feed
  path, and the replay pin's verdict.

A scenario carrying `recorded/report-hash-offline.txt` has its replayed report verified against
that pin: verified prints as such, and drift exits 3 — the same answer `verify` gives a drifted
report. Otherwise exits 0 on a scored run, 1 on a refusal or error.

## capture

```
trace capture scenario {extract,reason,report,baseline-generic,baseline-structured}
              [--from-recorded] [--model-profile MODEL_PROFILE]
              [--rehearse] [--response PATH]...
```

Captures a registered scenario's recording from a live model run (DEC-091). Every response the
run consumes is recorded into the scenario's `capture/` staging directory, shaped exactly as the
replayer reads it back; promotion into `recorded/` is a deliberate copy after the replay
round-trip is verified. This command spends real provider calls.

The three stages pause where a person authors checkpoint decisions:

- `extract` runs to checkpoint 1 and exports `review-export.yaml`; author
  `decisions-context.yaml` in the staging directory from it.
- `reason` applies the authored context decisions, approves the context, runs to checkpoint 2,
  and exports `findings-export.yaml`; author `decisions-findings.yaml` from it.
- `report` applies the authored finding decisions, runs to completion, and writes
  `report-hash.txt` — the value the replay must reproduce before the capture is promoted.
- `baseline-generic` and `baseline-structured` each make the one DEC-074 baseline call, stage
  its recording under `capture/baselines/`, and score it against the truth set immediately.
  Promotion is a copy into `recorded/baselines/`.

Decisions are authored per capture, against the run's own objects; a previous capture's committed
decision files answer its replay, not a new live run. `--from-recorded` resumes an interrupted
capture: staged recordings answer the calls they cover, and only unanswered calls go live.

Each stage refuses to run twice — a re-run would re-spend it — and the refusal exits 3. The
offline profile is refused (exit 1) before any side effect. The capture uses its own data root,
`data/capture-<slug>`, apart from your assessments.

`--rehearse` runs a pipeline stage offline (#534): the deterministic substitute serves the
`--response` recordings you supply, staging goes to `capture-rehearsal/` beside the real staging
directory with a `REHEARSAL` marker, and the data root is `data/capture-rehearsal-<slug>`. A
rehearsal validates the capture mechanics for a new scenario — inputs load, the checkpoints
pause, the decision files apply — before a dollar is spent. Nothing a rehearsal stages can be
promoted: every rehearsal envelope is marked, and every reader of a recording refuses the mark.
Baseline stages take no `--rehearse`; one call has no mechanics to rehearse.

## ledger

```
trace ledger assessment_id [--json]
```

Prints what the execution ledger recorded for each workflow run: one line per model-assisted
node with its calls, the four token spans kept disjoint (uncached input, cache reads, cache
writes, output), local duration, and estimated cost, plus a total line per run (DEC-092).

Absent prints as a dash, never zero: an offline replay of a recording that captured no usage
measured nothing. A recording that carries captured usage (a live capture wrote it) replays it,
and the ledger then shows the real numbers. Exits 0; an unknown assessment identifier exits 1.

## threats

```
trace threats assessment_id [--json]
```

Lists the threats the analysis proposed and validation accepted: identifier, categories, title,
and the components and assets each is grounded in. Threats were previously visible only through
the report or the read-only view.

## questions

```
trace questions assessment_id [--json]
```

Lists every question the assessment holds — open and answered, blocking and not — with its
status and priority.

## catalog

```
trace catalog show [--catalog-version CATALOG_VERSION] [--json]
trace catalog validate [--catalog-version CATALOG_VERSION]
```

Reads the requirements catalog through the one loader that may (DEC-010): the manifest and the
files checked against each other in both directions, every requirement validated, the content
hash recomputed. `show` lists the requirements; `validate` loads and reports the count and the
hash, exiting 1 with the loader's reason when the catalog does not verify — a moved content
hash, a manifest mismatch, an unknown version.

## diff

```
trace diff before after [--report] [--json]
```

Compares two assessments' approved models (DEC-097): what was added, removed, or changed, per
object family, with identity matched by content fingerprint rather than per-assessment
identifiers — the same component under different allocated identifiers is the same component. A
changed object names the fields that moved. Threats and documentation gaps are compared by
ground (their affected components and assets) and never force-paired: a guessed pairing would
report an edit nobody made. Both sides must hold an approved context; a side without one is
refused (exit 1). Exits 0 whether or not differences exist — the diff is a report, not a gate.

`--report` writes the comparison as a Markdown artifact to the later assessment's outputs area
(DEC-103) — findings and questions first, context after — instead of printing the structural
diff.

## reset

```
trace reset [--force]
```

Returns the data root to the fresh-clone state: removes the assessment store and every assessment
directory. Without `--force` it lists what would go, removes nothing, and exits 3. A directory
that does not look like a Trace data root is refused outright (exit 1). An already-fresh root
exits 0 with nothing to do. Destructive with `--force`; it exists for the rerun problem, where a
second run against a used root mints `asm-002` while a documented transcript names `asm-001`.

## view

```
trace view [--port PORT]
```

Serves a read-only rendering of the persisted assessments on `127.0.0.1`, default port 8765,
including per-assessment Threats and Ledger pages and a `/diff/<before>/<after>` comparison of
two assessments' approved models (DEC-097); all read-only GET (DEC-078):
overview, context, workflow, questions, findings, the finding-lineage walk, and the evaluation
scorecard. It serves GET only, drives nothing, and edits nothing — review stays on the command
line. Closing it loses nothing; everything it shows comes from the store. If the port is already
in use (the likeliest slip is running it twice), it exits 1 suggesting `--port`, not a traceback.
