# ForgeFlow demonstration script

A five-to-ten-minute walkthrough of the whole pipeline, offline, from the committed ForgeFlow
recording. It runs on a fresh clone with no provider key and no network: every model response and
every reviewer decision is replayed from `demo/forgeflow/recorded/`, so the demonstration is the
same path the test suite runs on every commit, not a staged one. The recording itself was captured
from a live `claude-opus-5` run (`recorded/provenance.md`), so what replays is what the model
actually said — including the four retried calls, replayed in position.

It is the source for the roadmap Stage 6 presentation's demo segment as well as the live
walkthrough. The live-model variant is the same commands with a live `--model-profile` and every
`--response` dropped; it is an option, never a dependency, and nothing below needs it.

## Before the room

```bash
uv sync                       # once, on the demo machine
uv run trace reset --force    # returns the data root to the fresh-clone state
```

Every command names `asm-001`, the identifier a fresh data root allocates first. Reset before the
talk, or a leftover `asm-001` makes the next `assessment create` mint `asm-002` and the transcript
diverges from this script. `uv run trace` with no arguments prints the resolved environment and
confirms no provider credential is needed — a good thing to show first if the audience is
skeptical about the offline claim.

The prefix `uv run trace` is written in full below. Aliasing `trace() { uv run trace "$@"; }` for
the session is fine and is what the recording does.

## The ten beats

Timings are the target for a seven-minute run with room to talk; the whole sequence executes in
seconds, so the clock is the narration, not the machine. Each beat names the committed artifact to
fall back to if a live command misbehaves — see the recovery plan for what each one is.

| # | Beat | Command | Say | ≈ | Fallback |
|---|---|---|---|---|---|
| 1 | Input documentation | `uv run trace assessment create --name "ForgeFlow Security Review"`<br>`uv run trace source add asm-001 demo/forgeflow/input` | Eight untrusted documents describe an AI code-review product. Trace reads documents, not diagrams — and one of these documents carries a deliberate prompt-injection payload, which we will meet again. | 0:45 | `demo/forgeflow/input/` |
| 2 | Extracted context, and the injection caught | `uv run trace run asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/extraction`<br>`uv run trace context show asm-001 \| head -40`<br>`uv run trace context show asm-001 --observations` | The run paused itself: checkpoint 1 is a phase in the transition table, not an option a flag can skip. Sixteen components, sixty-three claims — fourteen of them honestly `unknown` — each showing the passage it rests on, labelled quoted untrusted source content. Then the observation view: the model flagged the scratch-notes injection attempt, named the four claims it tried to poison, and surfaced both planted contradictions with the identifiers a `--resolve` needs. | 1:45 | `recorded/extraction/01-context-extraction.json` |
| 3 | Human correction | `uv run trace context review asm-001 --apply demo/forgeflow/recorded/decisions-context.yaml`<br>`uv run trace context approve asm-001` | A person decides each subject — 131 of them here. The applied file is a recorded review; interactively it is `--export`, edit, `--apply`. The checkpoint advances only once every subject has a decision. | 0:45 | `recorded/decisions-context.yaml` |
| 4 | Reasoning | `uv run trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/reasoning` | Thirty-five model calls replay in order: fifteen threats, two hundred twenty-five requirement mappings, seventy-four evidence assessments, sixty-three critiques — then the run pauses again at checkpoint 2. | 0:45 | `recorded/reasoning/` |
| 5 | Quality over volume | `uv run trace findings show asm-001 \| head -30` | All of that reasoning collapsed to five provisional findings, not a wall of them. Requirements the documents satisfy through inherited controls never became findings; the false-positive classes the catalog names were addressed by name in the mappings. | 0:45 | `demo/forgeflow/assets/forgeflow-report.md` §8 |
| 6 | Silence becomes questions | `uv run trace context show asm-001 \| grep -A3 "questions"` | Where the documents are silent, Trace does not guess a weakness. Silence becomes a question — twenty-six of them in the final report — never a finding (DEC-009). | 0:30 | `demo/forgeflow/expected/expected-questions.yaml` |
| 7 | The reviewer's verbs | `uv run trace findings review asm-001 --severity fnd-001=high --severity fnd-002=high --severity fnd-004=medium --severity fnd-005=medium --approve fnd-001 --approve fnd-002 --approve fnd-004 --approve fnd-005`<br>`uv run trace findings review asm-001 --reject fnd-003 --note "inability to verify enforcement is a gap with a question, not a finding"` | Severity is the reviewer's to assign; no node proposes one (DEC-030). Four findings approved on their evidence — and one rejected, because it rested on silence rather than evidence. That rejection is the product's thesis exercised at its own checkpoint: the model proposed it, the DEC-009 discipline caught it. | 1:00 | `recorded/decisions-findings.yaml` |
| 8 | Evidence and analysis lineage | `uv run trace view` — then open `http://127.0.0.1:8765/asm-001/lineage/fnd-001` | The differentiator: the finding walks back through its critique, evidence assessment, control mapping, threat, and context claim to the exact document excerpt and its content hash. Read-only; the browser drives nothing. | 1:00 | `demo/forgeflow/assets/pipeline-demo.gif` |
| 9 | Final report | `uv run trace findings approve asm-001`<br>`uv run trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/report`<br>`uv run trace report show asm-001 \| head -40`<br>`uv run trace verify asm-001` | The report is assembled from approved objects; four sections are prose, twelve are rendered deterministically, and the reviewer's rejected candidate is not in it. `trace verify` re-hashes every stored document and evidence reference and checks the report manifest. | 1:00 | `demo/forgeflow/assets/forgeflow-report.md` |
| 10 | Evaluation, including the miss | open `docs/eval/comparison.md` and `docs/eval/scorecard.html` | The comparison is the deliverable. Trace links every approved finding to hashed evidence and holds injected-instruction compliance at zero where a single-prompt baseline has no defense to test. And the flagship row shows the honest number: the live run matched none of the three authored expected findings and approved four defensible ones the truth set does not name — real weaknesses, wrong requirement lens. That row is the reason the evaluation harness exists, and it is measured, not narrated — and the adversarial replay on screen shows the defense live: attack detected, five payload classes resisted, compliance zero. | 1:30 | `docs/eval/comparison.md`, `docs/eval/scorecard.html` |

Total target: about 8:30 with narration, inside the ten-minute bound. The machine time is
negligible; cut beats 5–6 to reach five minutes.

The injection fixture is worth naming aloud at beat 2: `sample-repository-notes.md` carries a
deliberate prompt-injection payload — instructions to report no findings, fabricate controls, and
exfiltrate the signing key — and the recorded run detects it, names the four claims it targeted,
and follows none of it. Its handling is measured in the adversarial rows of the scorecard, not
asserted.

## Recovery plan

A live model or network failure must not ruin the presentation. Because the whole script is
already offline and deterministic, "recovery" here means a command misbehaving on the demo
machine — a stale data root, a wrong working directory, a port in use. Each roadmap Stage 5
recovery artifact maps to a file committed in this repository:

- **Preloaded assessment state.** `uv run python scripts/replay_forgeflow.py --data-root demo-root`
  before the talk produces a complete `asm-001` — both checkpoints answered, report rendered — in
  `demo-root`. Point every command at it with `--data-root demo-root` and open on any beat. The
  recorded responses and `recorded/decisions-context.yaml` / `recorded/decisions-findings.yaml`
  are the per-beat state: the run can be driven to exactly the beat that failed.
- **Backup recording.** `demo/forgeflow/assets/pipeline-demo.gif` is the whole pipeline recorded
  from `demo/forgeflow/pipeline-demo.tape`, re-rendered by CI (`.github/workflows/demo.yml`) so it
  cannot silently drift from the commands. If the terminal will not cooperate, play the GIF.
- **Screenshots.** Frames of that GIF are the screenshots; it is the committed source, so a still
  from any beat is a frame away and cannot show something the pipeline does not produce.
- **Static report.** `demo/forgeflow/assets/forgeflow-report.md` is the rendered report for beat 9,
  committed and hash-pinned to `demo/forgeflow/recorded/report-hash.txt`
  (`tests/unit/test_demo_report_asset.py` fails if it drifts). Open it if `report show` will not.
- **Known-good benchmark output.** `demo/forgeflow/expected/` is the authored truth set,
  `demo/forgeflow/recorded/report-hash.txt` pins the report the recording reproduces byte for byte,
  and `docs/eval/scorecard.html` and `docs/eval/comparison.md` are the committed results for
  beat 10. All regenerate offline.

The single hardest failure to recover from is the wrong directory: every path above is relative to
the repository root, so the first recovery step is always `cd` to the clone and re-run.
