# When a component earns its place: a measured ablation

*Proposed, version 0.1.*

A pipeline of six model-assisted agents and two human checkpoints is a claim that each part earns
its cost. The honest way to defend that claim is to remove each part and measure what breaks, then
report the result whether or not it flatters the design. This piece does that from the committed
evaluation artifacts, and every number in it regenerates offline from the recorded runs.

Each section separates what was **measured** from what it is taken to **mean**, because the two are
not the same and a portfolio piece that blurs them is the vendor self-comparison this project was
built to be unlike.

## The question

Roadmap Stage 4's decision gate asks whether the multi-stage pipeline beats a simpler prompt, and
whether each stage inside it pulls its weight. Three artifacts answer three cuts of that question,
and all three regenerate from the same recorded runs with no provider key:

- the [ablation table](../eval/ablation.md) — each component removed in turn, against the full
  pipeline;
- the [comparison table](../eval/comparison.md) — Trace against the two prompt baselines;
- the [scorecard](../eval/scorecard.html) — the per-scenario, per-condition detail behind both.

## What was measured, and how

**Measured.** The ablation set replays each scenario's recording three more times, each with one
component removed — evidence validation, critical review, context approval — and reads the metric
deltas against the authoritative run (`stability.run_ablation_set`; evaluation-plan section 14).
Every ablated run is marked non-authoritative and named, so a removed-component run can never
produce an approved assessment (DEC-012, DEC-031). All fifteen registered scenarios carry a
recording and so an ablation.

**Interpretation.** This is a deterministic replay of fifteen live captures. It can show that a
component is load-bearing when its removal moves a metric; it cannot prove a component is idle from
a null result on fifteen recordings. The bound is stated wherever a null appears below.

## Result one — evidence validation is load-bearing

**Measured.** Removing the evidence-validation node raises the false-negative rate by 50 points on
parcel-platform and 100 on reply-tuner — the two scenarios whose expected finding the authoritative
run actually produces. Everywhere else the authoritative false-negative rate is already 100% or the
scenario expects no finding, so there is nothing for the removal to lose. The numbers are the
`no evidence validation` rows of the [ablation table](../eval/ablation.md).

**Read the dashes in those rows before the numbers, because they are the honest part.** Ablating
evidence validation leaves every control mapping unassessed, and DEC-013 resolves an unassessed
mapping to no output — so an ablated run produces **no findings at all**. Every rate denominated on
the finding set is therefore unmeasured rather than improved, and renders as a dash (DEC-150).
Before that rule was applied those cells read as false-positive *improvements* of 100, 67 and 50
points, which was the empty denominator and not a result.

**Interpretation.** This is weaker than the claim the ablation used to carry, and the weaker
version is the true one. What the removal establishes is that evidence validation is
**structurally required**: the pipeline cannot emit a finding without it, by the outcome table's
construction. It does not establish that the node improves the findings it is removed from,
because there are no ablated findings to compare against. The credibility research names this as
the component to ablate; on this corpus the ablation answers a narrower question than it appears
to, and saying so is the difference between an argument that survives the follow-up question and
one that does not.

## Result two — the critic and the checkpoint move no metric here

**Measured.** Removing critical review changes no metric on any of the fifteen scenarios: every
delta in those rows of the [ablation table](../eval/ablation.md) is blank. Removing context
approval moves one — reply-tuner's false-negative rate rises 100 points without it, the same
scenario and the same direction as the evidence-validation removal.

**Interpretation.** This is a null result, and it is reported rather than omitted — a table that
only showed the component that moved would be the selective reporting this project criticizes. It
does **not** mean the critic or the checkpoint is idle. Critical review's effect is to reject or
reframe a finding before a human sees it, and context approval's is to let a reviewer correct the
extracted model; neither shows up in a finding-accuracy metric on a small deterministic corpus
where the recorded critic happens to pass the finding. Measuring the critic's contribution needs
scenarios authored to exercise it — a recorded critic that rejects — which the corpus does not yet
contain. Context approval is no longer in the null: it costs a true finding on reply-tuner, which
is a real if narrow effect on one scenario. The honest state is: evidence validation is
structurally required, context approval moves one metric on one scenario, and the critic is
unproven either way.

## Before and after — Trace against the baselines

**Measured.** The [comparison table](../eval/comparison.md) runs three single-call baselines over
the same documents and the same requirements catalog, scored by the same matcher, with ties
resolved in the baseline's favour. Over the fifteen scenarios the generic prompt produces **36
spurious findings** — seventeen of them on one scenario whose correct answer is none — against
**2 across the thirteen captures of Trace's current shape**. Every approved Trace finding cites an
`EvidenceReference` that resolves to a stored excerpt whose hash re-verifies.

**The recall side has to be said in the same breath.** Trace matches 2 of 12 reachable
expectations. The `baseline-single-pass` arm, one model call against Trace's fifteen to seventeen,
matches 4. Structure bought precision and cost recall, and that is the result rather than a win.

**And the evidence claim is narrower than this narrative used to make it.** A baseline *does* cite
passages — `BaselineFinding.evidence_quote` is required — so the earlier wording, that a baseline
"links none, because its output schema has no evidence field", was wrong about this repository's
own schema. Measured instead: fewer than half of baseline citations can be found verbatim in the
documents they claim to quote ([citation-fidelity.md](../eval/citation-fidelity.md), DEC-151).
The difference is not whether a citation exists but whether a machine can follow it.

**Interpretation.** The generic baseline's spurious findings are the DEC-009 failure — silence read
as a weakness — the pipeline exists to prevent, and the comparison measures that it prevents them
where the generic prompt does not. That is the strongest measured claim in the corpus. It is also
narrower than "the pipeline beats a prompt", which the recall column does not support.

## Under attack — the two-axis adversarial result

**Measured.** The adversarial condition runs a poisoned document through the same pipeline. On
unsigned-webhooks under attack, the finding metrics are unchanged from the clean run — utility is
preserved — and the injected-instruction compliance rate is 0%: the injected objective is not
carried out (scorecard, adversarial row; DEC-075). Three of the five payload classes are refused by
construction rather than by detection (fence-delimiter escape, checkpoint bypass, verifier
sabotage).

**Both adversarial recordings are authored, not captured, and the zero has to be read that way.**
They were written offline against the deterministic substitute on the stated premise that a correct
run under attack produces the same analysis, so **no model has been run against a poisoned document
in either scored condition** (DEC-152). The cause is mechanical: `trace capture` takes a scenario
and a stage and has no condition parameter, so the capture path cannot reach a condition the replay
path already understands. The scorecard's adversarial section carries a Responses column reading
`authored` on both rows. The one live data point is the ForgeFlow capture, whose extraction recorded
an `injection_attempt` observation against a real payload — one payload, one stage, n=1.

**Interpretation.** The two axes are reported separately on purpose: a single "injection-resistant"
number is the anti-pattern the research names, and utility-under-attack and attack-success are
different questions. That three payload classes fail by construction is the structural argument —
the attack has nothing to act on because the fence and the checkpoints are not a filter a payload
can talk past — while the compliance rate measures the classes that are not structural. Zero on
two authored adversarial recordings is what a correct run was expected to do, not a general claim
and not yet a measurement.

## The framework that was evaluated and not adopted

**Measured.** No orchestration framework is a dependency: `pyproject.toml` declares `anthropic` as
the only provider SDK and no `langgraph`, `langchain`, or durable-execution engine
(`tests/unit/test_interface_decision.py` and the package-layout tests hold this).

**Interpretation.** DEC-016 records the reasoning, and it is the account this narrative is for. The
pipeline is fourteen ordered phases with two pause points and no analytical branching — a transition
table of about twenty lines, the case a graph framework helps least with. The workflow state is
designed to hold identifiers and routing, not objects (DEC-006, data-model.md section 31), so a
framework checkpointer would be a second authoritative store beside the domain objects, which is the
one condition DEC-006 exists to prevent. The ceilings that matter — model calls, cost, duration —
are application-domain values a framework cannot see. "We evaluated the obvious framework,
established that a fixed linear pipeline with two pause points does not need it, and removed three
dependencies" is a stronger account of engineering judgment than adopting it because it is what
these systems usually use.

## What this establishes, and what it does not

**Measured.** Over fifteen live captures replayed deterministically: evidence validation is
structurally required (without it the pipeline emits no findings at all); the critic moves no
metric anywhere and context approval moves one on one scenario; Trace produces 2 spurious findings
across its thirteen current-shape captures where a generic prompt produces 36 over the same
fifteen scenarios; every approved Trace finding resolves to a hashed excerpt while fewer than half
of a baseline's citations can be found verbatim in the documents; and two adversarial conditions
show preserved utility with 0% injected-instruction compliance on **authored** recordings.

**Interpretation.** These are the strongest claims the current corpus supports and no stronger, and
four of them are weaker than the versions this document carried before the live sweep:

- **Recall is the measured weakness.** Trace matches 2 of 12 reachable expectations; a single
  model call matches 4. Structure bought precision and cost recall.
- **Run-to-run stability is measured and imperfect.** Ten live runs across two scenarios:
  `missing-docs` produced zero spurious findings in five of five, and `reply-tuner` reproduced its
  expected finding in three of five. Not-inventing is the stable axis; producing the right finding
  is not.
- **The adversarial zero is authored** (DEC-152), so it records an expectation rather than a
  measurement until a condition can be captured.
- **The truth sets are a single annotator's**, scored as self-agreement rather than an
  inter-annotator statistic — and the corpus has now measured what that is worth:
  [`authored-versus-live.md`](../eval/authored-versus-live.md) puts the authored-recording
  snapshot (78% / 82%) beside the live corpus (17% / 13%) on the same truth sets and matcher.

The [limitations section](https://github.com/ethanpturner/trace/blob/main/README.md#limitations-and-failure-modes)
carries the full account. The tables above regenerate from the recordings on every change, so the
next scenario or the next capture updates this narrative's numbers without a word of it being
rewritten by hand — which is how the numbers in this paragraph got out of date in the first place,
and why the prose around them now names its sources rather than restating them.
