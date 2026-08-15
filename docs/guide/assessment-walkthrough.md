# Running an assessment on your own documents

This is the full path from a directory of design documents to a verified report: preparing the
input, creating the assessment, running the pipeline, working the two human checkpoints, and
signing off the result. The commands here are the same ones the [getting-started
guide](getting-started.md#your-first-assessment) exercises against the ForgeFlow demo; this
document is about running them on your own material, and about the judgement the two checkpoints
ask of you. Flag-by-flag detail lives in [the CLI reference](cli-reference.md).

Identifiers like `asm-001` are allocated in order from a fresh data root; on a reused data root
the next create mints `asm-002` and any transcript you compare against diverges. `uv run trace
reset --force` returns the data root to the fresh-clone state and is destructive.

## Preparing input documents

Trace accepts Markdown (`.md`, `.markdown`), plain text (`.txt`), JSON (`.json`), and YAML
(`.yaml`, `.yml`). Each file must be valid UTF-8 and at most 10 MB, and a JSON or YAML file must
parse. A structured file must also parse to a mapping or a sequence at the top level — evidence
cites structured documents by JSON Pointer, and a file that parses to a bare scalar has nothing to
point at, so it is refused at registration rather than discovered to be uncitable later. PDF,
Office formats, repository ingestion, and web ingestion are deferred; supplying one produces a
named error, not a conversion.

What makes a document set assessable is coverage, not volume. The pipeline reasons only over what
your documents state: an architecture overview naming the components and how they connect, a
security overview describing authentication, authorization, and data handling, and operational or
integration notes describing how the system is deployed and what it talks to. A Finding requires
evidence from these documents; where they are silent, the output is a question to answer or a
documentation gap, never a conclusion. A set that describes the system's structure but says
nothing about its controls will produce a context and a list of gaps — which is a correct result,
and a signal about the documentation rather than about the system.

Two kinds of structured file get special treatment on the way in:

- **A structured system summary.** You may include a YAML file that states the system's
  components, data assets, trust boundaries, and security posture as fields rather than prose. An
  example lives at `demo/forgeflow/input/structured-system-input.yaml` — it is an example, not a
  schema; there is no fixed shape to validate against. The ForgeFlow example carries system
  metadata, a component list, external services, data assets with classifications, trust
  boundaries, security-control booleans, and known assumptions, and it names which documents are
  primary. The value of such a file is precision: `mfa_required: true` is a single addressable
  field an evidence reference can cite exactly, where the same fact in prose has to be interpreted.
  It is registered, hashed, and treated exactly like every other document.
- **A compose manifest.** A file named `compose.yaml`, `compose.yml`, `docker-compose.yaml`, or
  `docker-compose.yml` is additionally parsed deterministically before the extraction agent runs
  (DEC-070). The services and dependencies it states become candidate components and data flows,
  each backed by an excerpt of the manifest's own text, at zero model cost. Parser output earns no
  bypass: it is validated and decided at checkpoint 1 like everything else.

Every source document is untrusted input end to end. Nothing inside a document under review can
redefine an agent's instructions: excerpts reach the model only inside a delimited fence that
carries each excerpt's evidence identifier and neutralises any fence delimiter found in the text,
document content is never quoted into log records, and an injection attempt found in a document is
reported to you at checkpoint 1 as an observation rather than acted on.

## Planning cost and time

The one measured live run, on ForgeFlow-sized input (eight documents) with `claude-opus-5`, cost
$6.92 ± $3.28 and took about 41 ± 15 minutes. A larger document set costs more; no figure has been
measured beyond that size. The wall-clock time is dominated by model calls, and the run spends
most of it between the two checkpoints — your own time at the checkpoints is additional and is
yours to control.

The profile decides the spend. `primary-development` (the default) uses `claude-opus-5`;
`economy` uses `claude-sonnet-5` and costs less per call; `offline-fake` calls no provider and
costs nothing, but substitutes deterministic output — it is for replays and rehearsal, not for
assessing your documents. See [Model profiles](getting-started.md#model-profiles) for
configuration.

`--max-cost` and `--max-model-calls` on `run`, `resume`, and `context extract` put a ceiling on a
run. Exceeding a ceiling stops the run with a classified error; it never skips a node or shrinks a
request to fit, because a report produced by a quietly degraded pipeline would look like a report.
A stopped run exits 1, the assessment stays in `draft`, and nothing already persisted is lost. See
[Cost and ceiling surprises](troubleshooting.md#cost-and-ceiling-surprises) for what to do next.

## Creating the assessment and registering sources

```
uv run trace assessment create --name "Payments platform" --description "Q3 review" --tag payments
```

`--name` is required; `--description` and `--tag` are optional, and `--tag` repeats. The command
prints the new assessment identifier — `asm-001` on a fresh data root — which every later command
takes as its first argument.

```
uv run trace source add asm-001 docs/architecture/
uv run trace source add asm-001 threat-notes.md
```

`source add` takes a file or a directory and registers, normalizes, and indexes what it finds.
Registration is idempotent: re-adding a path reports the already-registered documents by
identifier and registers nothing twice, so the counts a reviewer quotes do not move on a rerun.
`--no-index` registers without indexing; a later `source add` of the same path completes the
indexing.

`source list` shows what an assessment holds. Indexing produces evidence references — addressable
excerpts of your documents that every later conclusion must cite. `evidence list asm-001` lists
them (`--source` filters to one document), and `evidence show <evidence-id> --assessment asm-001`
prints one reference with its excerpt and hash. You rarely need these before the first checkpoint,
but they are how you follow any citation back to its text.

## Running to the first checkpoint

```
uv run trace run asm-001
```

Live runs use the default `primary-development` profile and require `ANTHROPIC_API_KEY` to be
configured. The run executes every phase the transition table names, in order — ingestion,
indexing, context extraction, context validation — and stops at the first checkpoint. The pause
output tells you four things: the workflow run identifier, the phase it paused at, how many
subjects await your decision (`awaiting: N subject(s)`), and the commands that come next —
`context show`, `context review`, `context approve`, then `resume`.

A pause is success. The process exits with code 0, the state is on disk, and there is no daemon
waiting behind it — resuming is a new process reading that state. An exit code of 1 is a failed
run, with the error named on stderr.

`context extract` is the extraction-only alternative: it runs extraction and validation and stops
at the same checkpoint, without starting a full pipeline run. Prefer it when the context baseline
is itself the thing you are iterating on — checking whether a document set supports extraction at
all, or re-running after you have revised the documents — and use `run` when you intend to carry
on into the analysis.

## Checkpoint 1: approving the context

Approving the context is an attestation: you are stating that this set of components, actors,
assets, data flows, boundaries, and claims is an accurate baseline for the system. Every later
step — the threats enumerated, the requirements mapped, the findings proposed — reasons from this
baseline and only this baseline. An error approved here does not get caught later; it gets built
on. This checkpoint deserves more of your time than checkpoint 2, because checkpoint 2 can only be
as good as what you approve here.

```
uv run trace context show asm-001
uv run trace context show asm-001 --evidence
uv run trace context show asm-001 --observations
```

`context show` prints the review package. `--evidence` adds the source excerpt behind each claim;
`--observations` prints only what the extraction observed about the documents themselves —
injection attempts and contradictions awaiting resolution. The package is derived from the run
each time you ask; it is not a stored artifact that can go stale.

Every claim carries a status, and the statuses are an epistemic ladder. Read them differently:

- **documented** — the documents say it, and the claim cites the text. Check the excerpt against
  the claim with `--evidence`: does the quoted text actually assert what the claim asserts, or
  something weaker? A `documented` claim resting on a stretch is the highest-value thing to catch
  here, because downstream reasoning treats it as fact.
- **inferred** — reasoned from evidence that does not say it outright, with a recorded rationale.
  Judge the inference, not just the excerpt.
- **assumed** — taken as true without support and labelled as such. Confirm the ones you know to
  be true (`--confirm` records them as `user_confirmed`, with you as the evidence); reject the
  ones you know to be false.
- **unknown** — the documentation does not settle it. This is the honest resting place for
  silence; do not expect the pipeline to have resolved it, and answer the related question if you
  can.

A **contradiction** observation means two sources disagree and the pipeline refused to pick a
winner — that resolution is yours, and it requires your reasoning on the record. An
**injection-attempt** observation means a document contained text that tried to instruct the
model; the text was contained and reported, and your judgement call is about the document's
trustworthiness, not about cleanup.

The validation node behind this checkpoint reports and routes; it never corrects. Duplicates,
missing fields, and unevidenced claims arrive labelled, not silently fixed — so what you see is
what was extracted.

Decisions are recorded with `context review`, one or many per invocation:

```
uv run trace context review asm-001 --approve cmp-001 --reject clm-014
uv run trace context review asm-001 --confirm clm-003
uv run trace context review asm-001 --answer qst-002="Sessions are stored server-side in Redis"
uv run trace context review asm-001 --attach clm-007=evd-041
uv run trace context review asm-001 --resolve obs-001=documented \
  --rationale "The architecture overview is current; the runbook predates the migration"
uv run trace context review asm-001 \
  --request-re-extraction "Components from the billing service are missing entirely"
```

`--resolve ID=VALUE` settles a contradiction and requires `--rationale`. `--request-re-extraction`
rejects the whole extraction with a stated reason; the reason is carried into the re-extraction
prompt, which is what makes the second attempt better than a reroll. `--reviewer` overrides the
recorded reviewer name, which defaults to your operating-system username.

With many subjects, use the file loop instead of flags:

```
uv run trace context review asm-001 --export review.yaml
# edit review.yaml in your editor
uv run trace context review asm-001 --apply review.yaml
```

The exported file is derived, not stored. Every action is expressed as a difference from what was
exported, so applying an unchanged export records zero decisions — by design. Editing a field,
filling in a `decision:`, or typing an `answer:` produces exactly the same decision records as the
equivalent flags.

```
uv run trace context approve asm-001 --note "Baseline verified against the platform team's diagrams"
```

`context approve` approves the baseline, or refuses. While anything blocking remains — an
unanswered blocking question or an outstanding validation error — the blockers are listed on
stderr and the command exits 3. That exit is an answer, not a crash: it names everything
outstanding, and a script can branch on it without parsing prose. See [the exit-code
table](cli-reference.md#exit-codes).

An undecided subject is not a blocker: `context approve` succeeds while claims and objects still
await decisions, and an exit-0 approve is not proof the run can continue. The checkpoint advances
only when every subject has a reviewer decision, so decide every subject with `context review`
before approving; otherwise `resume` pauses again at checkpoint 1, and its pause output names how
many subjects are still awaited.

## Resuming the analysis

```
uv run trace resume asm-001
```

Resuming is a new process: it loads the paused state, re-runs the checkpoint, and continues now
that every subject has a decision. The analysis phases run in order — threat analysis, threat
validation, requirement and control mapping, mapping validation, evidence validation, critical
review, and finding consolidation — and the run pauses again at the second checkpoint, with the
same shape of pause output and the same exit code 0. If subjects were still undecided, the run
pauses again immediately, which is partial progress rather than an error. `--run` selects a
specific paused run when more than one exists.

## Checkpoint 2: deciding the findings

```
uv run trace findings show asm-001
```

The package prints candidate findings first, each with its evidence excerpts labelled, alongside
documentation gaps and open questions. The distinction between the columns is the product's
thesis. A Finding means evidence supports a weakness; a DocumentationGap means it cannot be
determined whether a control exists. Missing documentation is never proof of a vulnerability — it
becomes a question to ask, never a finding. If a candidate finding in front of you rests on
silence rather than on evidence, rejecting it is not overriding the tool; it is the judgement the
tool is built to ask of you.

Severity is yours and it is mandatory. It is assigned by the human reviewer at this checkpoint; no
pipeline step proposes one, and a finding cannot be approved while its severity is `unassigned`
(DEC-030) — severity is a risk judgement in your business context, which the source documents do
not carry. The levels are `informational`, `low`, `medium`, `high`, and `critical`.

```
uv run trace findings review asm-001 --severity fnd-001=medium --approve fnd-001
uv run trace findings review asm-001 --edit fnd-002 description="..." \
  --note "Tightened to what the evidence supports"
uv run trace findings review asm-001 --severity fnd-003=low --treatment fnd-003=accept \
  --treatment-rationale "Internal-only surface; residual risk accepted" --approve fnd-003
uv run trace findings review asm-001 --reject fnd-004 \
  --note "Rests on the runbook's silence, not on evidence"
uv run trace findings review asm-001 --defer fnd-005
uv run trace findings review asm-001 --request-more-analysis fnd-006 \
  --note "No evidence excerpt covers the admin path"
```

The verbs, with flag-by-flag detail in [the CLI reference](cli-reference.md#findings):

- `--severity ID=LEVEL` assigns severity, recorded as a reviewer edit.
- `--edit ID FIELD=VALUE` changes one field; the object is re-validated in full and the delta is
  recorded (DEC-023).
- `--treatment ID=VALUE` assigns a risk treatment — `undecided`, `mitigate`, `accept`, `transfer`,
  or `avoid` (DEC-060). Approving a finding treated as `accept` requires `--treatment-rationale`,
  the residual-risk statement; `--treatment-review-by YYYY-MM-DD` optionally dates a revisit.
- `--approve ID` and `--reject ID`, with `--note` as the recorded rationale. Within one
  invocation, severity, treatment, and edits land before approvals are checked, so a single
  command can assign and approve.
- `--override-rationale` approves past the deterministic gate when the evidence validation status
  argues against approval, with the override on the record (DEC-055). Use it when you know
  something the documents do not; the rationale is the audit trail for that knowledge.
- `--defer ID` leaves the finding a candidate, with the deferral as the record.
  `--request-more-analysis ID` sends it back for another pass and requires `--note` saying what is
  missing.
- `--export` / `--apply` work the same file loop as checkpoint 1, and the file reaches every
  reviewer action.

```
uv run trace findings approve asm-001
```

`findings approve` concludes the checkpoint once every finding is decided, so the run can
continue; it refuses while any remain undecided, naming them. It is not the final sign-off —
`assessment approve` is a different command, and it comes after the report exists.

## Rendering and verifying the report

```
uv run trace resume asm-001
```

The remaining phases run — report generation, report rendering, completion — and the run
completes. Rendering uses no model: four prose sections come from the report-generation agent, and
the other twelve are rendered deterministically from the objects you approved; a finding's
description in the report is the text you approved, verbatim.

`report show asm-001` prints the report; `--manifest` prints its manifest, which records the hash
of every input the report was rendered from. The CLI never prints absolute paths; on disk the
report lives under `data/assessments/<id>/outputs/` next to its `.manifest.json`.

```
uv run trace verify asm-001
```

`verify` walks the whole evidence chain: every stored document against its recorded hash, every
evidence reference against its source, and the report manifest against the store. Exit 0 means
everything verifies. On drift it exits 3, naming each drifted item — identifier, expected hash,
found hash — and never the changed content.

```
uv run trace assessment approve asm-001
```

`assessment approve` is your statement that you have read the rendered report and stand behind it.
It is refused while no report exists, while the report's run is not completed, or when that run is
non-authoritative — approval is a sign-off, never a status setter.

## After the report

Read the report with [the report guide](reading-the-report.md#the-sixteen-sections) beside it.
Four commands remain useful once the deliverable exists:

- `uv run trace export tm-bom asm-001` exports the approved model as a TM-BOM document (DEC-072)
  for interoperability with other threat-modelling tooling.
- `uv run trace report rubric asm-001 --score context_accuracy=4 ...` records your rubric for the
  report: seven categories — `context_accuracy`, `threat_quality`, `finding_usefulness`,
  `false_positives`, `evidence_quality`, `report_quality`, `overall_confidence` — each scored one
  to five, all in one invocation or the command refuses, so a stored rubric is never partial.
  `--comments` records qualitative notes with every row.
- `uv run trace assessment archive asm-001` retires the assessment; archiving is a person's
  action, never automatic.
- `uv run trace assessment purge asm-001` deletes one assessment entirely — every row and its
  whole directory. Without `--force` it is a dry run that lists what would go and removes
  nothing; the dry run's non-zero exit is a refusal, not a failure.
