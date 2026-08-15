# Security Architecture & Threat Modeling in the Age of AI Coding Agents

The talk, slide by slide: on-slide text first, speaker notes underneath. This is the repository's
authoritative copy of the deck's content; the slide file is regenerated from it. The demo segment
(slides 22–23) is resolved to the committed ForgeFlow walkthrough — the placeholders the draft
carried are filled from [`docs/product/demo-script.md`](../product/demo-script.md) and
[`demo/forgeflow/speaker-notes.md`](../../demo/forgeflow/speaker-notes.md). Claims are checked
against the repository in [traceability.md](traceability.md).

## Slide 1 — Title

> **Security Architecture & Threat Modeling in the Age of AI Coding Agents**
> How AI changes what we model, how we review it, and how we validate security decisions
> TRACE

Notes: AI coding agents have moved well beyond autocomplete. They can read repositories, execute
commands, call tools, modify files, and participate directly in delivery. Today I want to explore
two questions: how does security architecture change when an AI agent becomes an actor in the
system, and can we use AI itself to help threat modeling keep up? I'll also show TRACE, a project
I built to explore the second question.

## Slide 2 — $ whoami

> **Ethan Turner** — Security Architect / Engineer
> 13+ years in security. Product Security • Security Architecture • Threat Modeling.
> DevSecOps • AI / Agentic Security. MS Information Assurance • CISSP • 8× GIAC.
> Currently: building TRACE and exploring what security architecture looks like when developers
> aren't the only ones writing code.

Notes: Quick introduction — target 30–45 seconds. About 13 years in security across operations,
professional services, and security architecture, most recently product security and threat
modeling in a large financial environment. I've spent an unhealthy amount of time recently
experimenting with AI-assisted security architecture, which is where TRACE and this talk came
from. One bit of current context: I was recently impacted by a layoff, so I'm exploring what's
next — security architecture, product security, AI security. If you're working on interesting
problems in that space, I'd love to connect afterward. But that's enough about me. Let's talk
about agents. Delivery note: state the layoff matter-of-factly; don't linger.

## Slide 3 — Autocomplete suggests. Agents act.

> The important change isn't better code generation. It's **authority + action**.

Notes: The distinction I care about is action. Autocomplete proposes text. An agent can take a
goal, decide on intermediate steps, use tools, and change the environment. That moves this from a
pure AI-model problem into familiar security-architecture territory: identity, permissions, trust
boundaries, credentials, auditability, and blast radius.

## Slide 4 — We added a new actor.

> Users • Developers • Services • Administrators • Attackers • **AI Agent**

Notes: A useful threat-modeling move is simply to put the AI agent on the diagram as an actor.
But it is a strange actor: humans give it instructions; data can contain instructions that
influence it; it often borrows a human or service identity; it can use tools; its behavior can
vary between runs. That combination is what makes the architecture interesting.

## Slide 5 — An agent touches…

> MODEL • CONTEXT • MEMORY • REPOSITORY • TOOLS • CREDENTIALS • APIs • CI/CD • CLOUD

Notes: Don't threat-model only the chat window. Ask what the agent can actually reach: model,
context, memory, source code, local tools, MCP servers, credentials, APIs, pipelines, cloud
environments. The blast radius of the agent is determined much more by this surrounding
architecture than by the model name.

## Slide 6 — The trust boundaries changed.

> What information and authority cross the boundary **with the agent**?

Notes: Traditional trust-boundary thinking still works. The additional question is what travels
across the boundary with the agent: context, credentials, tool permissions, retrieved content,
generated code, authority. An agent may legitimately cross several boundaries in one task, so we
need to understand what authority follows it.

## Slide 7 — "Fix the deployment" is doing a lot of work here.

> Read repo → inspect logs → find credentials → modify infrastructure → deploy

Notes: A developer says "fix the deployment." That sounds scoped. But a capable agent might read
the repository, inspect CI logs, discover cloud configuration, find credentials, modify
infrastructure, and execute a deployment. There may be no attacker at all — the architecture may
simply have granted too much authority.

## Slide 8 — Four questions for every agent

> 1 What can influence it? 2 What can it access? 3 What can it do? 4 How do I know what happened?

Notes: My four practical architecture questions for an agent. The fourth is especially important —
hold onto it; we'll come back to it when we get to TRACE.

## Slide 9 — Does threat modeling still work?

> **YES.** The thing we're modeling changed.

Notes: We don't need to throw away threat modeling. Assets still matter, actors matter, trust
boundaries matter, least privilege matters; STRIDE and attack trees still work. The methodology
isn't obsolete. The architecture we're applying it to has changed.

## Slide 10 — Threat model the whole agent

> INPUTS → MODEL / CONTEXT / MEMORY → CAPABILITIES → OUTPUTS

Notes: Break an agentic system into four areas. Inputs: prompts, repositories, documentation,
retrieved content. Agent internals: model, context, memory. Capabilities: tools, APIs,
credentials. Outputs and actions: code, commands, infrastructure changes. That gives us something
concrete to model instead of treating "AI" as a mysterious box.

## Slide 11 — Prompt injection is not the whole story.

> INFLUENCE • AUTHORITY • OUTPUT • VISIBILITY

Notes: Prompt injection matters, but don't let it become synonymous with agent security. Think in
categories. Influence: what can manipulate behavior? Authority: what permissions and credentials
are available? Output: what can the agent create or change? Visibility: can we reconstruct what
happened? Authority and visibility are particularly natural territory for security architects.

## Slide 12 — Security architecture has a scaling problem.

> Code velocity ↑ Architecture change ↑ Review demand ↑ Security architects … not so much.

Notes: Now zoom out from one agent. AI increases code velocity and the rate of architecture
change. That increases security-review demand. Organizations are not going to increase security
architecture headcount at the same rate. Security architecture has a scaling problem — and that
motivates using AI on our side too.

## Slide 13 — The obvious idea

> Architecture + requirements + context → LLM → threats / findings

Notes: The obvious experiment is AI-assisted threat modeling. Give a model architecture
documentation, requirements, system context, maybe security standards, and ask it to identify
threats or findings. Conceptually this is extremely straightforward.

## Slide 14 — This is ridiculously easy to prototype.

> "Analyze this architecture and identify security threats."
> Seconds later: 20 plausible findings.

Notes: The first prototype is almost suspiciously easy. Paste architecture into a capable model
and ask for security threats; seconds later you get a polished list of plausible findings. The
first time you see it, it feels like we've solved something important. Then you try to use it
seriously.

## Slide 15 — Then reality shows up.

> False positives • missing context • implicit controls • conflicting evidence • hallucinated
> assumptions

Notes: Enterprise systems contain huge amounts of implicit context. Authentication may be
provided by a platform. Encryption may be inherited. Standard controls exist but are not repeated
in every application's documentation. Models also make assumptions, encounter conflicting
evidence, and produce inconsistent results. Plausible is not the same thing as correct.

## Slide 16 — Congratulations. We automated 500 things someone still has to review.

Notes: This is the failure mode I want to avoid. AI generates 500 findings and a security
architect manually investigates 500 findings — we automated the creation of work. The goal needs
to be increasing the leverage of the reviewer, not merely increasing finding throughput.

## Slide 17 — Why did the model generate this finding?

Notes: Pause here. This became the central question for me. Not "can it explain itself after the
fact?" — I wanted the actual workflow evidence: what information was available, what was
retrieved, what happened, and what supports the result.

## Slide 18 — So I did what any reasonable security engineer would do…

> I built another tool.

Notes: Transition slide; keep it quick. TRACE is the proof point for the talk, not the entire
talk.

## Slide 19 — TRACE

> Making AI-assisted threat modeling **observable**

Notes: TRACE is an experiment in making AI-assisted threat modeling observable. The goal isn't
replacing the security architect. The goal is to make the machine's work inspectable enough that
an architect can efficiently evaluate the resulting security decision.

## Slide 20 — Don't just save the answer.

> Preserve what happened between input and finding.

Notes: Instead of input → magic AI box → finding, preserve what happened between input and
output. What was retrieved? What context was supplied? What model calls happened? What evidence
corresponds to the finding? That changes the review experience.

## Slide 21 — From answer → evidence

> FINDING → EVIDENCE → SOURCE CONTEXT → EXECUTION TRACE

Notes: The conceptual shift is from answer to evidence. A finding by itself says "authentication
may be bypassed." A useful review artifact lets me move from finding to supporting evidence to
source context to execution trace. The architect can then decide whether the conclusion is
justified.

## Slide 22 — Demo scenario

> SYSTEM: ForgeFlow — a fictional AI code-review platform, described by eight documents
> QUESTION: does the evidence actually support each candidate finding?
> FINDING: fnd-003 — the one the machine proposed and the reviewer threw out

Notes: Explain only three things before the demo. The system: ForgeFlow, an original fictional
AI code-review product described by eight untrusted documents — one of which carries a deliberate
prompt-injection payload. The question: every conclusion must trace to a specific passage in a
specific document, so does the evidence support each candidate finding? The finding we will
investigate: fnd-003, which rests on silence rather than evidence — the documents describe a
separation mechanism but never state that its enforcement is verified. Do not explain every
feature before showing the demo.

## Slide 23 — Enough slides. Let's inspect something.

Notes: Demo — target 7–9 minutes, the committed walkthrough runs about 8:30 with the closer.
Every command replays offline from committed fixtures; no provider key on stage. The full
runthrough is inlined below so this document carries the talk end to end; the sources remain
authoritative — the eight steps are [`demo/forgeflow/speaker-notes.md`](../../demo/forgeflow/speaker-notes.md)
and the beat table, timings, and recovery plan are
[`docs/product/demo-script.md`](../product/demo-script.md). If those files change, this section
is regenerated from them.

### Before the room

- `uv sync`, then `uv run trace reset --force`. Reset is what guarantees `asm-001`: a stale data
  root makes the next `assessment create` mint `asm-002`, and every identifier, URL, and decision
  reference below shifts with it. Re-run reset before the talk and before any rehearsal.
- Alias to keep the transcript short: `trace() { uv run trace "$@"; }`
- Start `trace view` in a second terminal before step 5 so it is live when the browser opens.
- Recovery if a live command misbehaves: pre-run the whole thing into its own root with
  `uv run python scripts/replay_forgeflow.py --data-root demo-root`, then add
  `--data-root demo-root` to every command. Or play `demo/forgeflow/assets/pipeline-demo.gif`
  and open `demo/forgeflow/assets/forgeflow-report.md`.

### The eight steps

**Step 1 — Input: "the material under review" (about 0:45)**

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
documents, not diagrams — and treats every one as untrusted data. One of these files deliberately
contains a prompt-injection payload. We will see it framed as data, not followed as an
instruction."

Reminders: name the injection fixture (`sample-repository-notes.md`) here so step 2's handling
lands. The empty credential line is the punchline of the offline claim; pause on it.

**Step 2 — Run the analysis: "the model works, a person decides" (about 2:15)**

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

Reminders: the pause is the point; say it twice, because audiences assume a checkpoint is
cosmetic. `--response` takes a directory here and expands to its numbered recordings in order.
Severity is untouched in this run: no node proposes one, and nothing has been decided yet.

**Step 3 — Show the findings (about 0:30)**

```bash
uv run trace findings show asm-001 | head -30
```

Say: "Five candidate findings, not a wall. Each carries the passages it rests on. The point of
this system is not finding count — it is that every conclusion can be defended, and I will show
you one that could not be."

Reminders: pipe through `head` — the full package runs to thousands of lines because every
finding embeds its quoted evidence, critiques, and questions verbatim; unpiped, it scrolls the
room while the line above says "not a wall". `grep '^## fnd-'` prints exactly the five titles if
that is the shot wanted instead. The severities read blank here; assigning them is the reviewer's
job at this checkpoint, which is the step 8 closer.

**Step 4 — Pick the finding (about 0:15)**

Do: nothing; name it.

Say: "This one, fnd-003. The machine proposed it. When you see the evidence it stands on, you
will see why the reviewer threw it out."

Reminder: this framing is the spine of the demo — "I do not trust this one, so let us do the
work."

**Step 5 — Open the view (about 0:15)**

```bash
uv run trace view
```

Run it in the second terminal, then open `http://127.0.0.1:8765/asm-001/`.

Say: "This is a read-only rendering of the same store the command line reads. It changes nothing
— GET only — it just renders persisted state."

Reminders: port 8765 by default; if occupied, `--port 8766`. The read-only discipline is the
security boundary here; do not imply the review has moved to a browser.

**Step 6 — Walk backward through the lineage (about 1:30)**

Open: `http://127.0.0.1:8765/asm-001/lineage/fnd-003`

Say: "Every finding has a lineage — the ordered chain of objects that produced it. Top to bottom:
the requirement and the threat it mapped to, the control mapping, the evidence assessments, the
critiques, the context claims — and at the bottom, the evidence, quoted, with the content hash of
the source document it came from. Follow fnd-003 down and read what the separation mechanism
actually is."

Reminders: scroll slowly and pause on the context claims before reaching the excerpts. The
verdict belongs to step 8; only the facts are visible here.

**Step 7 — Identify the source evidence (about 1:00)**

```bash
uv run trace evidence show --assessment asm-001 EVD-ID
uv run trace context show asm-001 --evidence
uv run trace verify asm-001
```

`EVD-ID` stands for the evidence identifier shown on the lineage page.

Say: "The excerpts cite the architecture's own Known Documentation Gaps list. The documents
describe a separation mechanism as documented behaviour; what they never state is that its
enforcement is verified — and that is the whole story. The mechanism exists; only proof of
enforcement is silent. `trace verify` re-hashes every stored document and evidence reference and
says which identifier drifted if any did."

Reminders: read the excerpt aloud; the sentence about the known-gaps list is the pivot into step
8. The evidence id in the first command is whatever the lineage page labels beside the excerpt;
there is no need to memorise it.

**Step 8 — Evaluate the verdict (about 1:30)**

```bash
uv run trace findings review asm-001 --reviewer recorded-reviewer --apply demo/forgeflow/recorded/decisions-findings.yaml
uv run trace findings show asm-001 | head -5
```

Say: "Here is the recorded decision. Rejected — and the rationale is the heart of the project:
the separation mechanism is documented and only its enforcement is undocumented. Inability to
verify is a documentation gap with a question, not evidence that scoping is absent. That is the
DEC-009 line this project exists to hold. The machine drew a conclusion from silence, and the
person at the checkpoint read the evidence and stopped it. The same run raised that gap and that
question instead. The other four candidates were approved, each with the severity the reviewer
assigned."

Reminders: the verdicts are on screen twice — the review command prints the decision table
(nine rows, `reject fnd-003` among them) and the piped summary confirms every proposed finding
now carries a reviewer decision; keep the `head`. The rejection rationale is the strongest
sentence in the demo; let it land before moving on. If the deck has the scorecard, `docs/eval/comparison.md` is the cross-scenario version
of the same claim: the generic baseline invents this class of false positive; no Trace run has.

**Optional closer (about 0:30)**

```bash
uv run trace findings approve asm-001
uv run trace resume asm-001 --model-profile offline-fake --response demo/forgeflow/recorded/report
uv run trace report show asm-001
uv run trace verify asm-001
```

Say: "The report assembles from approved objects only — four sections prose, twelve rendered
deterministically — and the whole chain re-verifies: every stored document, every evidence
reference, the report manifest."

Total: about 8:30 with the closer, 7:30 without steps 6–7's command-line asides.

### The ten beats, condensed

The demo script's beat table, commands and fallbacks only — the narration above covers what to
say. Each fallback is a committed artifact; the full table with per-beat narration is
[`docs/product/demo-script.md`](../product/demo-script.md).

| # | Beat | Command | ≈ | Fallback |
|---|---|---|---|---|
| 1 | Input documentation | `assessment create`, `source add asm-001 demo/forgeflow/input` | 0:45 | `demo/forgeflow/input/` |
| 2 | Extracted context, injection caught | `run … --response recorded/extraction`, `context show` (`--observations`) | 1:45 | `recorded/extraction/01-context-extraction.json` |
| 3 | Human correction | `context review --apply recorded/decisions-context.yaml`, `context approve` | 0:45 | `recorded/decisions-context.yaml` |
| 4 | Reasoning | `resume … --response recorded/reasoning` | 0:45 | `recorded/reasoning/` |
| 5 | Quality over volume | `findings show` | 0:45 | `demo/forgeflow/assets/forgeflow-report.md` §8 |
| 6 | Silence becomes questions | `context show \| grep -A3 "questions"` | 0:30 | `demo/forgeflow/expected/expected-questions.yaml` |
| 7 | The reviewer's verbs | `findings review --severity … --approve …` / `--reject fnd-003` | 1:00 | `recorded/decisions-findings.yaml` |
| 8 | Evidence and analysis lineage | `trace view` → `/asm-001/lineage/fnd-001` | 1:00 | `demo/forgeflow/assets/pipeline-demo.gif` |
| 9 | Final report | `findings approve`, `resume … --response recorded/report`, `report show`, `verify` | 1:00 | `demo/forgeflow/assets/forgeflow-report.md` |
| 10 | Evaluation, including the miss | open `docs/eval/comparison.md` and `docs/eval/scorecard.html` | 1:30 | committed results |

## Slide 24 — The finding isn't the product.

> **THE EVIDENCE IS.**

Notes: Probably the biggest lesson from the project. The finding isn't necessarily the valuable
artifact; the evidence that lets a human evaluate the finding is. Generating findings is cheap.
Generating trustworthy, reviewable security decisions is the harder problem.

## Slide 25 — Humans should review decisions.

> They shouldn't have to reconstruct them.

Notes: The goal is not eliminating human judgement. A better division of labor: AI does
information gathering, correlation, first-pass analysis, and evidence collection; humans evaluate
ambiguity, business context, risk, and the final decision. Humans should review decisions — not
reconstruct the machine's entire investigation.

## Slide 26 — Our inputs are part of the problem.

> Docs • wikis • diagrams • tribal knowledge ↓ Structured architecture • controls • evidence

Notes: There's also a data problem. Security architecture often lives in documents, wikis,
diagrams, tickets, and people's heads. Better models alone won't fix that. If we want machines to
reason reliably about architecture, we need more structured architecture, structured controls,
structured findings, and explicit assumptions.

## Slide 27 — A threat is also a hypothesis.

> Threat: agent can invoke privileged tool without authorization.
> Hypothesis: untrusted input cannot cause invocation of privileged tool X.

Notes: Here's where this can go beyond generating threat models. A threat is often an implicit
hypothesis about system behavior. Turn the threat around and you have a security hypothesis —
something potentially testable.

## Slide 28 — Sometimes you have to poke it with a stick.

> THREAT MODEL → HYPOTHESIS → EXPERIMENT → TRACE → EVIDENCE → DECISION

Notes: This connects threat modeling to security chaos engineering and continuous validation. At
some point, asking "could this happen?" isn't enough — sometimes you have to poke the system with
a stick, carefully. Important: present this as future direction, not something TRACE already
implements.

## Slide 29 — Three things to take home

> 1 Model agents as actors 2 Design for least agency 3 Require evidence from AI security decisions

Notes: Three practical takeaways. Model agents as actors — put them on the architecture diagram.
Design for least agency, not just least privilege — minimize the tools, context, and authority
available for the task. Require evidence when AI participates in security decisions. Those are
useful today regardless of tooling.

## Slide 30 — The bigger shift

> TODAY: humans model systems.
> FUTURE?: humans define security intent → machines continuously model + test → humans adjudicate

Notes: The future I find interesting isn't "LLM replaces security architect." It's a change in
where the architect spends time: humans define security intent and constraints, machines
continuously analyze and potentially test systems against that intent, humans adjudicate
ambiguity and risk. That is a much higher-leverage role for the architect.

## Slide 31 — If software can change continuously…

> …why shouldn't its threat model?

Notes: Closing thought. Software changes continuously; AI coding agents accelerate that. But many
threat models are still snapshots: create, review, store, eventually go stale. AI's biggest
opportunity for threat modeling may not be automatically writing the document — it may be making
threat modeling continuous, observable, and eventually testable. Pause before the final question.

## Slide 32 — Questions? Objections? Horrifying agent stories?

> Let's connect — Security Architecture • Product Security • AI Security.
> Currently exploring my next security challenge. linkedin.com/in/ethanpturner

Notes: Q&A. As mentioned at the beginning, I'm currently figuring out what's next professionally;
if your organization is dealing with security architecture, product security, or AI security,
I'd genuinely enjoy talking. Prompts if the room is quiet: who is already allowing coding agents
to execute tools? Has anyone tried LLMs for architecture review or threat modeling? What evidence
would you need before trusting an AI-generated finding? What's the scariest agent permission
you've seen? Leave this slide visible through Q&A so people can scan the QR code.
