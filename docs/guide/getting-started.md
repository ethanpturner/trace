# Getting started

This guide takes you from a fresh clone to a completed assessment in one sitting, entirely
offline: no API key, no network, no cost. Everything here replays a committed recording of a real
run, so the commands are exact and the output is reproducible. When you are ready to assess your
own documents with a live model, [the assessment walkthrough](assessment-walkthrough.md) covers
the same pipeline with the judgement calls filled in.

## Prerequisites

You need three things:

- **Python 3.14 or later.**
- **[uv](https://docs.astral.sh/uv/)**, which manages the environment and runs every command.
- **A source checkout.** Trace runs from a clone, not from an installed wheel. The prompts, the
  requirements catalog, the report template, and the scenario registry are repository files, and
  a wheel install that tries to run anything past the banner exits 1 with
  `SourceCheckoutRequiredError`.

```bash
git clone https://github.com/ethanpturner/trace.git
cd trace
uv sync
```

`uv sync` installs the runtime and development dependencies from `uv.lock`. Every command in this
guide is run from the repository root with `uv run`.

## First touch: the offline replay

Before configuring anything, run the one-command demonstration:

```bash
uv run python scripts/replay_forgeflow.py
```

This replays a committed recording of a live run against ForgeFlow, the demo scenario, through
all fourteen pipeline phases: six model-assisted agents answered from recorded responses, both
human checkpoints answered from recorded reviewer decisions, and a deterministically rendered
report at the end. It takes about a minute and needs no key.

Exit 0 proves something specific: the report the replay produced matches the pinned content hash
of the recorded live run, byte for byte. If the pipeline, the prompts, or the rendering had
drifted since the recording was made, the script would exit non-zero and say so.

By default the replay writes to a temporary directory and cleans up. To keep the result and look
around in it, give it a data root:

```bash
uv run python scripts/replay_forgeflow.py --data-root demo-root
uv run trace --data-root demo-root context show asm-001 --evidence
uv run trace --data-root demo-root view
```

`trace view` serves a read-only rendering on `127.0.0.1:8765` — the overview, the context, the
findings, and the finding-lineage walk. It serves GET only and edits nothing; closing it loses
nothing.

## Configuration

Configuration lives in a `.env` file at the repository root:

```bash
cp .env.example .env
```

The file has two runtime settings, `APP_ENV` and `LOG_LEVEL`, and the provider keys. For live
runs, set `ANTHROPIC_API_KEY` — or `OPENAI_API_KEY` for the OpenAI profile (DEC-095); a blank
value is treated as unset. **Nothing in this guide needs a key** — every offline command works
with the file exactly as copied.

Bare `uv run trace` with no arguments shows what the process resolved:

```
trace: context-aware security architecture analysis
env: local  log level: INFO
credentials configured: anthropic
```

It names which credentials are configured and never prints key material.

## Model profiles

A model profile is a named bundle of provider, model, and settings. Five exist:

| Profile | Provider and model | When to use it |
| --- | --- | --- |
| `primary-development` | Anthropic, `claude-opus-5` | The default. Live assessments of real documents. |
| `economy` | Anthropic, `claude-sonnet-5` | Live runs where cost matters more than depth. |
| `economy-mapping` | Anthropic, `claude-opus-5` with the mapping agent on `claude-sonnet-5` | The DEC-094 overlay bundle; what the model comparison measures. |
| `openai-experimental` | OpenAI, `gpt-5.1` | The second provider (DEC-095). Needs `OPENAI_API_KEY`. |
| `offline-fake` | Deterministic substitute | No key, no network, zero cost. Replays and rehearsal. |

`offline-fake` is a first-class way to run, not a test hook. Paired with `--response`, it replays
recorded model output through the real pipeline:

- `--response PATH` is repeatable. Each file is one recorded model response, consumed in the
  order given, one per model call the run makes.
- A directory stands for its numbered recordings — the `NN-*.json` files inside it, in sorted
  order. `demo/forgeflow/recorded/extraction` is one file; `reasoning` is thirty-five.
- A recording only pairs with the scenario it was made for. Recorded responses replay the
  ForgeFlow input; pointing them at your own documents produces answers about ForgeFlow.

For a live run, drop `--model-profile offline-fake` and every `--response`: the same commands
make live calls through the same seam. Budget for that before starting — see
[Planning cost and time](assessment-walkthrough.md#planning-cost-and-time).

## Your first assessment

This is the full pipeline, one command at a time, against the ForgeFlow demo input. Every command
names `asm-001`, the identifier a fresh data root allocates first. On a reused data root the next
`create` mints `asm-002` and the transcript diverges, so a rerun starts with a reset —
`uv run trace reset --force` returns the data root to the fresh-clone state, and it is
destructive. (You just ran the replay, but it used a temporary directory or `demo-root`, so the
default data root is still fresh.)

Create the assessment and register the input documents:

```bash
uv run trace assessment create --name "ForgeFlow Security Review"
uv run trace source add asm-001 demo/forgeflow/input
```

`source add` registers every accepted file in the directory, normalizes it, and records a content
hash for each. Run the pipeline to the first checkpoint:

```bash
uv run trace run asm-001 --model-profile offline-fake \
    --response demo/forgeflow/recorded/extraction
```

The run extracts the system context and stops at checkpoint 1, exiting 0 — a pause at a
checkpoint is success, and the process has genuinely exited; resuming later is a new process
reading state from disk. Look at what was extracted:

```bash
uv run trace context show asm-001 --evidence
```

This prints every claim with the source passage behind it, each labelled as quoted untrusted
source content. Checkpoint 1 wants a decision on every claim and an answer to every open
question; the recorded reviewer decisions supply them:

```bash
uv run trace context review asm-001 --apply demo/forgeflow/recorded/decisions-context.yaml
uv run trace context approve asm-001
```

`approve` baselines the context. Had anything blocking still been open — an unanswered blocking
question or an outstanding validation error — it would have exited 3 and named it: a stated
refusal, not a fault (see [the exit codes](cli-reference.md#exit-codes)). The order matters:
approval does not stand in for the per-subject decisions, and a resume with subjects still
undecided pauses again — see
[the walkthrough](assessment-walkthrough.md#checkpoint-1-approving-the-context). Resume through
the analysis phases:

```bash
uv run trace resume asm-001 --model-profile offline-fake \
    --response demo/forgeflow/recorded/reasoning
```

Threat analysis, requirement mapping, evidence validation, and critical review run, and the
pipeline pauses again at checkpoint 2 with candidate findings. Severity is yours to assign here —
no pipeline step proposes one, and a finding cannot be approved while its severity is unassigned.
The recorded decisions carry the severities and approvals from the live run:

```bash
uv run trace findings show asm-001
uv run trace findings review asm-001 --apply demo/forgeflow/recorded/decisions-findings.yaml
uv run trace findings approve asm-001
```

`findings approve` concludes checkpoint 2 so the run can continue; it is not the final sign-off
on the deliverable, which is `assessment approve` and comes after the report exists. Resume one
last time to generate and render the report:

```bash
uv run trace resume asm-001 --model-profile offline-fake \
    --response demo/forgeflow/recorded/report
uv run trace report show asm-001
```

The report has sixteen sections. Four are model-written prose; twelve are rendered
deterministically from the objects you approved, so a finding's description is exactly what was
approved at checkpoint 2. On disk it lives under `data/assessments/asm-001/outputs/` next to its
`.manifest.json`. Finally, check the evidence chain:

```bash
uv run trace verify asm-001
```

`verify` re-hashes every stored document and evidence reference and checks the report manifest,
exiting 0 when everything holds; on drift it exits 3 and names exactly what drifted.

That is the whole pipeline. The recorded decision files did the reviewing for you here; on your
own documents, the two checkpoints are where your judgement enters, and
[the walkthrough](assessment-walkthrough.md#checkpoint-1-approving-the-context) covers how to
work them.

## Where to go next

- [The assessment walkthrough](assessment-walkthrough.md) runs the same pipeline on your own
  documents, with the reviewing done for real: preparing input, budgeting a live run, and working
  both checkpoints.
- [The CLI reference](cli-reference.md) documents every command, flag, and exit code.
- [Reading the report](reading-the-report.md) explains the sixteen sections, the difference
  between a finding and a documentation gap, and how to trace a conclusion back to its evidence.
- [Troubleshooting](troubleshooting.md) covers rerun hygiene, replay failures, and where output
  lands on disk.
- The README's [Running it today](../../README.md#running-it-today) section is the condensed
  version of this guide, kept to one screen.
