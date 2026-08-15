# Troubleshooting

This page is organized by symptom. Each entry names the behavior as you see it, explains what
happened, and gives the fix. The deep explanation for each area lives in one owning document; the
entry links there rather than repeating it.

## Exit codes in practice

**`trace context approve` printed nothing and exited 3.**
It almost certainly printed the blockers — to stderr. Exit 3 is a stated refusal, not a failure:
the context has open blockers (an unanswered blocking question or an outstanding validation
error), and the command answered "no, and here is why". Run it again without piping and
read the stderr lines, or run `trace context show <id>` to see the blockers in the review package.
The full code table is in [the CLI reference](cli-reference.md#exit-codes).

**I piped `context show` through `less` and the blocker list disappeared.**
Blockers, drift lines, and dry-run warnings go to stderr; the review package goes to stdout. A pipe
through `less`, `head`, or a shell redirect of stdout alone hides exactly the part that explains
the exit code. Append `2>&1` before the pipe, or drop the pipe.

**`trace verify` exited 3 — did it crash?**
No. Exit 3 means the command completed and the answer is "something drifted": a stored document, an
evidence reference, or the report manifest no longer matches its recorded hash. Each drift is named
on stderr by identifier and hash, never by content. Exit 1 would mean the command itself hit an
operator-fixable error (an unknown assessment identifier, an unreadable data root). The distinction
is deliberate: a script can branch on "refused" versus "crashed" without parsing prose. See
[the CLI reference](cli-reference.md#exit-codes) for which commands can return 3.

**I approved the context but `resume` pauses again at checkpoint 1.**
Approval and per-subject decisions are different things. `context approve` succeeds while
subjects are still undecided — an undecided subject is not an approval blocker — but the
checkpoint advances only when every subject has a reviewer decision, so the resume pauses again
and its output says `awaiting: N subject(s)`. Decide the remaining subjects with `context review`
(flags or the `--export`/`--apply` file loop), then resume. See
[the walkthrough](assessment-walkthrough.md#checkpoint-1-approving-the-context).

**`trace reset` listed some entries and exited non-zero.**
That is the dry run. Without `--force`, `reset` lists what would be removed, removes nothing, and
exits 3 — a refusal that doubles as a preview. `trace assessment purge <id>` behaves the same way.
Pass `--force` when the list is what you meant.

## Where is my output

**The run finished but no report appeared on screen, and nothing printed a path.**
The CLI never prints absolute paths — a path describes the machine, not the assessment. The
rendered report is read with `trace report show <id>`; `--manifest` prints its manifest instead.
On disk it lives under `data/assessments/<id>/outputs/` next to its `.manifest.json`, but the
reader is the command, not the file. [Reading the report](reading-the-report.md) covers the
report's structure and how to trace a conclusion back to evidence.

**I want the raw files an assessment produced.**
Everything an assessment stores is under `data/assessments/<id>/` in the data root: `sources/`,
`normalized/`, `outputs/`, `traces/`, and `evaluation/`. Treat them as read-only; editing a stored
source breaks its hash and `trace verify` will say so.

## Rerun hygiene

**Every command in the walkthrough says `asm-001`, but my assessment is `asm-002`.**
Identifiers are allocated in order from a fresh data root. If the data root already held an
assessment — a rehearsal, an earlier attempt — the next `assessment create` mints `asm-002` and
every documented command diverges from what you have. Either substitute your identifier
throughout, or return to the fresh-clone state first:

```
uv run trace reset --force
```

`reset --force` is destructive: it removes the assessment store and every assessment directory
under the data root. Without `--force` it lists what would go and exits 3. To remove one
assessment and keep the rest, use `trace assessment purge <id> --force`, which deletes exactly
that assessment's rows and directory. [Getting started](getting-started.md) walks through the
fresh-root flow.

## Offline replay failures

**My offline run failed with `ResponsesExhaustedError`.**
The `offline-fake` profile replays recorded responses, consumed one per model call — retries
included. Running out means the run made more calls than the recordings you supplied, which
usually means the wrong `--response` directory for the phase: `demo/forgeflow/recorded/extraction`
feeds the extraction slice, `reasoning` feeds the analysis phases after checkpoint 1, and `report`
feeds report generation after checkpoint 2. Passing a directory means its numbered `NN-*.json`
files in sorted order. Pair the directory with the phase you are running; see
[model profiles](getting-started.md#model-profiles).

**Offline replay failed with a schema validation error mid-phase.**
The recording being replayed does not answer the question the current phase asked — the same
wrong-directory mistake, caught earlier when the recorded shape does not fit the phase's schema.
It also happens when recordings are replayed against a different scenario: a recording pairs only
with the input it was recorded against, because the pipeline's questions depend on the documents.
Recordings from `demo/forgeflow/recorded/` replay against the ForgeFlow input, not against yours.

## Cost and ceiling surprises

**My run stopped with a limit error instead of finishing under budget.**
`--max-cost` and `--max-model-calls` are stop conditions, not throttles. Exceeding a ceiling stops
the run with a classified error and exit 1 — the run never skips a node or shrinks a request to
squeeze under the limit, because a cheaper run that silently did less would look like a complete
one. The failed run leaves the assessment in `draft`, and nothing is lost: completed phases keep
their objects.

**A run failed — do I start over?**
No. `trace resume <id>` restarts a failed run from the phase it stopped in; phases that completed
are not re-run. Raise the ceiling on the resume if a limit caused the stop. Planning figures for a
live run are in [the walkthrough](assessment-walkthrough.md#planning-cost-and-time).

## Environment and configuration

**`run` failed with a message about `ANTHROPIC_API_KEY`.**
The key is missing or blank — a blank value in `.env` is treated as unset, so `cp .env.example
.env` alone configures nothing. Set the value in `.env`. The diagnostic is bare `uv run trace`
with no arguments: it prints the environment, the log level, and which credentials are configured,
by name only. Offline work needs no key: `--model-profile offline-fake` with `--response` runs the
pipeline without a provider. See [configuration](getting-started.md#configuration).

**`uv sync` failed complaining about the Python version.**
Trace requires Python 3.14 or newer. `uv python install 3.14` fetches one; `uv sync` then builds
the environment against it. See [prerequisites](getting-started.md#prerequisites).

**Every command past the banner exits 1 with `SourceCheckoutRequiredError`.**
Trace is running from an installed wheel. Prompts, the requirements catalog, the report template,
and the scenario registry are repository files, so v0.1 runs from a source checkout only:
`git clone`, then `uv sync`, then run commands from the repository. Installing the package
elsewhere is not a supported way to run it.

## Known sharp edges

**`trace evidence show asm-001 evd-...` exits 2.**
The argument order is reversed from most commands: `evidence show` takes the evidence identifier
first and the assessment as a flag — `trace evidence show evd-... --assessment asm-001`.

**I approved the findings but `assessment status` still is not `approved`.**
Two different commands. `findings approve` concludes checkpoint 2 so the run can continue to the
report; `assessment approve` is the final human sign-off after the report exists, and it is
refused while no report exists or while the report's run is not completed. Approving findings is
the middle of the process, not the end. See
[the walkthrough](assessment-walkthrough.md#checkpoint-2-deciding-the-findings).

**I applied my exported review file and it said "no decisions recorded".**
The export is derived from the current state, not stored; applying it back unchanged records zero
decisions by design. Edit the file — dispositions, answers, severities — and apply it again; the
file loop is described in
[the walkthrough](assessment-walkthrough.md#checkpoint-1-approving-the-context).

**The process exited at the checkpoint — did the run die?**
No. Pausing is stopping: the process exits 0 with the state on disk, and `trace resume <id>` is a
new process that reads it back. See
[the walkthrough](assessment-walkthrough.md#running-to-the-first-checkpoint).

**`trace report rubric` refused my scores.**
The rubric is recorded in one invocation, all seven categories, each scored one to five — a stored
rubric is never partial. Supply every category as a `--score CATEGORY=N` flag in a single command;
the seven names are listed in `trace report rubric --help`.

**`trace view` exited 1 saying the port is in use.**
Something already holds port 8765 — usually an earlier `trace view` still running. Pass `--port`
to choose another, or stop the other process. The view binds to 127.0.0.1 and serves GET only.

**`trace view` beside an active run printed a one-line SQLite error.**
Two processes on one store: a write lock held past the busy timeout surfaces as a one-line
`sqlite3` error, not a traceback. Retry once the run finishes its write, or run the view against a
quiet data root. Closing the view loses nothing; everything it shows comes from the store.

**A command crashed with a full pydantic `ValidationError` traceback.**
Deliberate. A domain object failing validation deep in the pipeline is a bug in Trace, not a
mistake in your input, so it keeps its traceback rather than being softened into a one-line
message that hides where it happened. Operator-fixable errors get the one-line treatment; this one
should be reported with the traceback intact.
