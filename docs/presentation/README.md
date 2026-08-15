# The ISC2 presentation folder

The speaking folder for the roadmap Stage 6 presentation: *Security Architecture & Threat
Modeling in the Age of AI Coding Agents*. Trace remains the source of truth — every asset here is
derived from committed repository material, and nothing in this folder asserts a number the
repository does not carry.

## What is here

| File | What it is |
|---|---|
| [deck.md](deck.md) | The talk, slide by slide: on-slide text and speaker notes, with the demo segment carrying the full eight-step runthrough and the condensed beat table inline |
| [traceability.md](traceability.md) | Every checkable slide claim mapped to the repository artifact or measured number that backs it, and the rhetorical slides classified as such |
| [handout.md](handout.md) | The one-page handout: the four questions, the three takeaways, and the measured Trace numbers with their sources |

## The assets the presentation consumes

Each is committed elsewhere in the repository and referenced rather than duplicated:

- **Demo script and recovery plan** — [`docs/product/demo-script.md`](../product/demo-script.md),
  the ten-beat offline walkthrough. The spoken narration for the presentation's eight-step
  variant is [`demo/forgeflow/speaker-notes.md`](../../demo/forgeflow/speaker-notes.md).
- **Demo recording** — [`demo/forgeflow/assets/pipeline-demo.gif`](../../demo/forgeflow/assets/pipeline-demo.gif),
  rendered by CI from `pipeline-demo.tape` so it cannot drift from the command surface. This is
  the silent fallback; the narrated video is issue #353 and is not yet recorded.
- **Screenshots** — frames of that GIF, derived on demand rather than committed, because CI
  re-renders the GIF and committed stills would drift:
  `ffmpeg -i demo/forgeflow/assets/pipeline-demo.gif -vf "select=eq(n\,FRAME)" -vframes 1 still.png`.
  The committed source guarantees a still cannot show something the pipeline does not produce.
- **Rendered report** — [`demo/forgeflow/assets/forgeflow-report.md`](../../demo/forgeflow/assets/forgeflow-report.md),
  hash-pinned to `demo/forgeflow/recorded/report-hash.txt`.
- **Scorecard and comparison** — [`docs/eval/scorecard.html`](../eval/scorecard.html) and
  [`docs/eval/comparison.md`](../eval/comparison.md), regenerated offline from recorded runs.
- **Architecture image** — [`docs/assets/architecture.svg`](../assets/architecture.svg).

## Before the room

The demo machine preparation is the demo script's "Before the room" section, unchanged:
`uv sync`, then `uv run trace reset --force`. A stale data root is the hardest live failure to
recover from — an old `asm-001` desynchronizes every identifier in the walkthrough, and a data
root written by an older schema version refuses under the current one.

## What is not here

The narrated demo video (#353) and the exported slide file. The deck is authored in an external
slide editor; [deck.md](deck.md) is the repository's authoritative copy of its content, and the
exported file is regenerated from it for the talk rather than version-controlled as a binary.
