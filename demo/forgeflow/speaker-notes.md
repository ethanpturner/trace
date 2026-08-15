# ForgeFlow demonstration — speaker notes

The narration script for the eight-step walkthrough, staged on top of the offline ForgeFlow
replay. Machine time is seconds; the eight minutes are the talk. This is the spoken companion to
[`docs/product/demo-script.md`](../../docs/product/demo-script.md), which holds the beat table and
the recovery plan; every fallback cited here is a committed artifact there.

Every command is offline: recorded `claude-opus-5` responses replay through the deterministic
seam, so nothing needs a provider key or a network.

## Before the room

- `uv sync`, then `uv run trace reset --force`. Reset is what guarantees `asm-001`: a stale data
  root makes the next `assessment create` mint `asm-002`, and every identifier, URL, and decision
  reference below shifts with it. Re-run reset before the talk and before any rehearsal.
- Alias to keep the transcript short: `trace() { uv run trace "$@"; }`
- Start `trace view` in a second terminal before beat 5 so it is live when the browser opens.
- Recovery if a live command misbehaves: pre-run the whole thing into its own root with
  `uv run python scripts/replay_forgeflow.py --data-root demo-root`, then add
  `--data-root demo-root` to every command. Or play `demo/forgeflow/assets/pipeline-demo.gif`
  and open `demo/forgeflow/assets/forgeflow-report.md`.

## Beat 1 — Input: "the material under review" (about 0:45)

Do:

```bash
uv run trace
uv run trace assessment create --name "ForgeFlow Security Review"
uv run trace source add asm-001 demo/forgeflow/input
uv run trace source list asm-001
```

Say: "`uv run trace` prints the environment — no provider credential configured, so everything
you will see replays a recorded run offline. Eight documents describe an AI code-review product:
architecture, security overview, the GitHub integration, an operations guide. Trace reads
documents, not diagrams — and treats every one as untrusted data. One of these files
deliberately contains a prompt-injection payload. We will see it framed as data, not followed as
an instruction."

Reminders:

- Name the injection fixture (`sample-repository-notes.md`) here so beat 2's handling lands.
- The empty credential line is the punchline of the offline claim; pause on it.

## Beat 2 — Run the analysis: "the model works, a person decides" (about 2:15)

Do:

```bash
uv run trace run asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/extraction
uv run trace context show asm-001 --evidence
uv run trace context review asm-001 --apply demo/forgeflow/recorded/decisions-context.yaml
uv run trace context approve asm-001
uv run trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/reasoning
```

Say: "The run paused itself — checkpoint 1 is a phase in the transition table, not something a
flag can skip. The extraction agent turned the documents into evidence-linked context claims;
every claim shows the passage it rests on, labelled quoted untrusted source content. A person
reviewed that context and approved it. Then the run advanced through threat analysis, control
mapping, evidence validation, and critical review — one mapping call per threat, the whole
requirements catalog every call — and paused again at checkpoint 2."

Reminders:

- The pause is the point; say it twice, because audiences assume a checkpoint is cosmetic.
- `--response` takes a directory here and expands to its numbered recordings in order.
- Severity is untouched in this run: no node proposes one, and nothing has been decided yet.

## Beat 3 — Show the findings (about 0:30)

```bash
uv run trace findings show asm-001
```

Say: "Five candidate findings, not a wall. Each carries the passages it rests on. The point of
this system is not finding count — it is that every conclusion can be defended, and I will show
you one that could not be."

Reminder: the severities read blank here; assigning them is the reviewer's job at this
checkpoint, which is the beat 9 closer.

## Beat 4 — Pick the finding (about 0:15)

Do: nothing; name it.

Say: "This one, fnd-003. The machine proposed it. When you see the evidence it stands on, you
will see why the reviewer threw it out."

Reminder: this framing is the spine of the demo — "I do not trust this one, so let us do the
work."

## Beat 5 — Open the view (about 0:15)

```bash
uv run trace view  # second terminal; open http://127.0.0.1:8765/asm-001/
```

Say: "This is a read-only rendering of the same store the command line reads. It changes nothing
— GET only — it just renders persisted state."

Reminders:

- Port 8765 by default; if occupied, `--port 8766`.
- The read-only discipline is the security boundary here; do not imply the review has moved to a
  browser.

## Beat 6 — Walk backward through the lineage (about 1:30)

Open: `http://127.0.0.1:8765/asm-001/lineage/fnd-003`

Say: "Every finding has a lineage — the ordered chain of objects that produced it. Top to
bottom: the requirement and the threat it mapped to, the control mapping, the evidence
assessments, the critiques, the context claims — and at the bottom, the evidence, quoted, with
the content hash of the source document it came from. Follow fnd-003 down and read what the
separation mechanism actually is."

Reminders:

- Scroll slowly and pause on the context claims before reaching the excerpts.
- The verdict belongs to beat 8; only the facts are visible here.

## Beat 7 — Identify the source evidence (about 1:00)

```bash
uv run trace evidence show --assessment asm-001 <evd-id>   # the id on the lineage page
uv run trace context show asm-001 --evidence
uv run trace verify asm-001
```

Say: "The excerpts cite the architecture's own Known Documentation Gaps list. The documents
describe a separation mechanism as documented behaviour; what they never state is that its
enforcement is verified — and that is the whole story. The mechanism exists; only proof of
enforcement is silent. `trace verify` re-hashes every stored document and evidence reference and
says which identifier drifted if any did."

Reminders:

- Read the excerpt aloud; the sentence about the known-gaps list is the pivot into beat 8.
- The evidence id in the first command is whatever the lineage page labels beside the excerpt;
  there is no need to memorise it.

## Beat 8 — Evaluate the verdict (about 1:30)

```bash
uv run trace findings review asm-001 --reviewer recorded-reviewer --apply demo/forgeflow/recorded/decisions-findings.yaml
uv run trace findings show asm-001
```

Say: "Here is the recorded decision. Rejected — and the rationale is the heart of the project:
the separation mechanism is documented and only its enforcement is undocumented. Inability to
verify is a documentation gap with a question, not evidence that scoping is absent. That is the
DEC-009 line this project exists to hold. The machine drew a conclusion from silence, and the
person at the checkpoint read the evidence and stopped it. The same run raised that gap and that
question instead. The other four candidates were approved, each with the severity the reviewer
assigned."

Reminders:

- The rejection rationale is the strongest sentence in the demo; let it land before moving on.
- If the deck has the scorecard, `docs/eval/comparison.md` is the cross-scenario version of the
  same claim: the generic baseline invents this class of false positive; no Trace run has.

Optional closer (about 0:30):

```bash
uv run trace findings approve asm-001
uv run trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/report
uv run trace report show asm-001
uv run trace verify asm-001
```

Say: "The report assembles from approved objects only — four sections prose, twelve rendered
deterministically — and the whole chain re-verifies: every stored document, every evidence
reference, the report manifest."

Total: about 8:30 with the closer, 7:30 without beats 6–7's command-line asides.
