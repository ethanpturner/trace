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
produce an approved assessment (DEC-012, DEC-031). Three scenarios carry a recording and so an
ablation: contradictory-docs, unsigned-webhooks, and forgeflow.

**Interpretation.** This is an offline, deterministic corpus of three scenarios. It can show that a
component is load-bearing when its removal moves a metric; it cannot prove a component is idle from
a null result on three recordings. The bound is stated wherever a null appears below.

## Result one — evidence validation is load-bearing

**Measured.** Removing the evidence-validation node raises the false-negative rate from 0% to 100%
on both contradictory-docs and unsigned-webhooks: the pipeline stops producing the finding it
otherwise reports and matches. On forgeflow the false-negative rate is already 100% in the
authoritative run — the live capture found real weaknesses under different requirement
identifiers than the authored truth set names — so its removal moves nothing there. The numbers are the `no evidence validation` rows of the
[ablation table](../eval/ablation.md).

**Interpretation.** Evidence validation is the node that decides whether the support behind a
candidate finding actually holds. Without it, the finding does not survive to the report, and a
scenario whose one expected weakness is real comes back empty. This is the component the credibility
research names as the one to ablate, and on this corpus it is the one the pipeline cannot lose
without missing a true finding. It earns its place.

## Result two — the critic and the checkpoint move no metric here

**Measured.** Removing critical review, and removing context approval, changes no metric on any of
the three scenarios: every delta in those rows of the [ablation table](../eval/ablation.md) is
blank.

**Interpretation.** This is a null result, and it is reported rather than omitted — a table that
only showed the component that moved would be the selective reporting this project criticizes. It
does **not** mean the critic or the checkpoint is idle. Critical review's effect is to reject or
reframe a finding before a human sees it, and context approval's is to let a reviewer correct the
extracted model; neither shows up in a finding-accuracy metric on a small deterministic corpus
where the recorded critic happens to pass the finding and the recorded reviewer happens to approve
the context unchanged. Measuring their contribution needs scenarios authored to exercise them — a
recorded critic that rejects, a reviewer edit that changes an outcome — which the corpus does not
yet contain. The honest state is: on what has been measured, only evidence validation moves a
number, and the other two are unproven either way.

## Before and after — Trace against the baselines

**Measured.** The [comparison table](../eval/comparison.md) runs two single-prompt baselines over
the same documents and the same requirements catalog, scored by the same matcher. The generic
baseline produces five spurious findings across four scenarios; the structured baseline and Trace
produce none in the head-to-head scenarios. Trace links every approved finding to a resolvable,
hashed evidence excerpt; a baseline links none, because its output schema has no evidence field.

**Interpretation.** The generic baseline's spurious findings are the DEC-009 failure — silence read
as a weakness — the pipeline exists to prevent, and the comparison measures that the pipeline
prevents it where the generic prompt does not. Evidence linkage is the property no baseline can have
in principle, and it is the same property the ablation shows is load-bearing: the evidence chain is
both what a reviewer can check and what the pipeline depends on to keep a finding.

## Under attack — the two-axis adversarial result

**Measured.** The adversarial condition runs a poisoned document through the same pipeline. On
unsigned-webhooks under attack, the finding metrics are unchanged from the clean run — utility is
preserved — and the injected-instruction compliance rate is 0%: the injected objective is not
carried out (scorecard, adversarial row; DEC-075). Three of the five payload classes are refused by
construction rather than by detection (fence-delimiter escape, checkpoint bypass, verifier
sabotage).

**Interpretation.** The two axes are reported separately on purpose: a single "injection-resistant"
number is the anti-pattern the research names, and utility-under-attack and attack-success are
different questions. That three payload classes fail by construction is the structural argument —
the attack has nothing to act on because the fence and the checkpoints are not a filter a payload
can talk past — while the compliance rate measures the classes that are not structural. Zero is the
measured result on two adversarial scenarios, not a general claim.

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

**Measured.** On three deterministic offline scenarios: evidence validation is load-bearing (its
removal misses a true finding); the critic and the context checkpoint move no finding-accuracy
metric; Trace produces no spurious finding where a generic baseline produces five; every Trace
finding is evidence-linked and no baseline finding can be; and two adversarial scenarios show
preserved utility with 0% injected-instruction compliance.

**Interpretation.** These are the strongest claims the current corpus supports and no stronger. No
live-model run has been measured, so run-to-run stability is unmeasured and costs read zero; the
truth sets are a single annotator's, scored as self-agreement rather than an inter-annotator kappa;
and the null results for the critic and the checkpoint are an absence of measured effect, not
evidence of absence. The [limitations section](../../README.md#limitations-and-failure-modes)
carries the full account. The tables above regenerate from the recordings on every change, so the
next scenario or the first live run updates this narrative's numbers without a word of it being
rewritten by hand.
