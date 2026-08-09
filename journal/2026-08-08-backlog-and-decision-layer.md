# 2026-08-08 — Deriving the backlog, and what the corpus turned out not to say

## What this session did

Turned the design corpus into an initial backlog: 94 issues across five milestones, held as
a version-controlled manifest under `scripts/` rather than typed into GitHub by hand, plus
issue and pull-request templates carrying the binding constraints.

Nothing has been created on GitHub yet. The manifest, the bodies, and the seeding script
are committed first so they are reviewable in a diff.

## The finding that reshaped the plan

The intended order was twelve components across four milestones: Assessment object,
document loader, evidence model, context objects, context extractor, context review, threat
engine, requirement matcher, control mapper, critic, findings, report.

Six independent passes over the corpus — one per milestone, one on GitHub mechanics, one
cross-cutting — converged on something that was not the expected answer. **The first slice
of this backlog is not implementation work.** It is decision work that implementation is
silently blocked on, and the blockers are concentrated under exactly the first four
components anyone would build.

The corpus is unusually complete. That is precisely why the gaps are hard to see: every
document reads as settled, and the contradictions only appear when two of them are held
against each other, or against the data.

Eight places where the corpus states two different things:

- **The human checkpoints.** `CLAUDE.md`, `README.md`, and DEC-005 say structural and not
  configurable. `data-model.md` section 6 makes `require_context_review` and
  `require_finding_review` required booleans, which is the off switch. `evaluation-plan.md`
  section 14 then proposes a "checkpoint vs no checkpoint" ablation that needs the off
  switch to exist. Four of the six passes reached this independently, from four directions.
- **Severity ownership.** `current-architecture.md` section 5.11 gives it to a deterministic
  node, `agent-design.md` section 17 to a Severity Support Agent, section 36 makes that
  agent optional and suggests the reviewer does it. `Finding.severity` is required. Shipping
  the agent makes a seventh model-assisted component against a cap of six — which would
  breach a binding constraint by default, because the agent is fully specified and someone
  will build it.
- **The report shape.** Section 5.13 specifies fifteen sections; `agent-design.md` section
  19 shows the agent returning four. No template artifact exists though section 19 lists it
  as an agent input, and the "output manifest" is required by section 20 and defined nowhere.
- **Interface first.** Section 5.1 prefers a local web application; the roadmap says the
  opposite four times, including "do not begin with the web interface."
- **Identifier scheme.** Section 2.1 offers readable sequential prefixes and internal UUIDs
  in adjacent sentences. They are not interchangeable: sequential implies a counter, and
  therefore a persistence dependency and an ordering guarantee.
- **Prompt file naming.** `agent-design.md` section 34 uses hyphens with a `shared/` tree;
  `current-architecture.md` section 10 uses underscores without one. `prompts/` is empty, so
  whoever writes first sets the convention by accident.
- **Benchmark layout**, specified twice with different file sets and two spellings of the
  same file.
- **ForgeFlow expected counts.** The fixture declares three findings; the scenario document
  lists four. Five questions declared, ten listed.

## The defect

`demo/forgeflow/input/structured-system-input.yaml` — a document supplied to Trace as
material under review — ends with an `evaluation:` block declaring the expected finding,
question, gap, and contradiction counts. `forgeflow-scenario.md` section 25 says expected
files must not be supplied to Trace during an assessment.

So the benchmark contract sits inside the input. Every measurement against this scenario is
contaminated, and the pipeline is handed a finding quota — which `design-principles.md`
section 9 rejects outright and `CLAUDE.md` lists as a binding constraint. `README.md`
currently quotes the block approvingly.

This is the failure mode the project exists to criticize, committed by the project, in its
own fixture. It became `m0-fixture-leak`, and it needs no decision — only removal.

## What only showed up by reading the code and data together

These are not in any document and could not have been found by reading the design corpus
alone. They are the argument for having the research read the repository rather than the
specification.

- **`applicable_technologies` is populated on zero of the 23 requirements.** It is the only
  structured filter field in the section 17 schema. Any retrieval design that assumes it
  will find nothing. `applicable_conditions` and `non_applicable_conditions` are free text —
  45 and 44 distinct strings — model-readable but not filterable. Vector infrastructure is
  deferred. `category` is the only usable structured axis that exists today.
- **A requirement can only ever be evaluated through a threat.** `data-model.md` section 19
  makes `threat_id` required on `ControlMapping`. A requirement that applies to the system
  but that no threat reaches is never evaluated and appears nowhere. The corpus never says
  whether that is by design or by omission, and it decides whether the requirement matcher
  is a per-threat or a per-system function.
- **A closed `component_type` enum would reject the project's own fixture.** Section 11
  lists thirteen examples; `structured-system-input.yaml` uses six types, of which only
  `service` appears in that list.
- **`Actor` is orphaned.** Required by `agent-design.md` section 7 and roadmap Stages 1 and
  2, but `SystemContext` has no `actor_ids`, section 40 omits it from the implementation
  priority, open question 4 asks whether it should be first-class at all, and it uniquely
  lacks a `status` field. It would be built and then be unreferenceable.
- **`ContextClaim.value` is typed `any`**, which cannot pass this repository's
  `mypy --strict`. Choosing a concrete type partially pre-answers open question 1.
- **`SystemContext` has no `id` and no `status`**, so it is implicitly keyed by
  `(assessment_id, version)` — which nothing states, and which the persistence layer needs.
- **`EvidenceStrength` is defined and carried by no field on any object.**
- **`ReviewDisposition` has no value for `merge` or for "request re-extraction,"** both of
  which are listed as reviewer actions elsewhere.
- **`.gitignore` has no `data/` entry**, so a first run would offer the eight demo
  documents — including the injection fixture — to the next commit.

## Three things the pipeline cannot run without, absent from all twelve components

1. **The model abstraction layer and the execution ledger.** `current-architecture.md`
   section 9 requires the first; `agent-design.md` section 6 requires every model result to
   link to an `ExecutionRecord`. Every cost, token, retry, and failure metric reads from the
   second. Both are now M1 and M2 issues.
2. **The Evidence Validation Agent.** One of the six capped agents. Both `agent-design.md`
   section 35 and roadmap Stage 4 place it before Critical Review. It owns the
   `supported / partially_supported / unsupported / contradicted` classification — which is
   to say it owns the mechanism that keeps `unverified` from becoming `unmet`. Without it
   the Critic challenges conclusions that were never evidence-checked and DEC-009 has no
   enforcement point at all. It was missing from the component list entirely.
3. **Persistence, the artifact store, the orchestrator, `ReviewerDecision`, `Question`,
   `DocumentationGap`, and the requirements catalog loader.** The catalog has existed since
   this week and no product code reads it; the loader is what turns it from data into a
   dependency.

## Decisions made about the backlog itself

**Document loader and evidence model are swapped.** The loader's entire output is evidence
references. Built first, it would define its own location representation and be rewritten.

**A fifth milestone, M0, holds the decisions.** Twenty of them, deduplicated from the
overlapping sets each pass produced. Distributing them into M1 through M4 would have kept
the four milestones tidy and hidden the fact that seven of them gate the whole critical
path.

**Checkpoint 2 ships inside Findings, not after Report.** If it lands later, the report is
generated from unapproved findings for the whole of development, and a structural property
becomes something switched on at the end.

**Report is split into a model-assisted agent and a deterministic renderer**, with a
consistency validator between them. One issue covering both would produce a renderer that
reaches for the model when a section is awkward. The renderer carries an acceptance
criterion that it imports no model client, testable by import graph.

**Requirement matching is deterministic; control mapping is the single model-assisted
agent.** This is the working assumption pending DX-10, and it preserves the six-agent cap.
The likely implementation error it avoids: `agent-design.md` section 12 prohibits "apply
every requirement to every component," which constrains the *output*, not the input
breadth. Conflating those two produces the wrong design. With 23 requirements the whole
catalog fits in one prompt, so the constraint is about discrimination, not retrieval.

## Mechanics worth recording

- **Closing keywords only fire on a merge into the default branch.** Default is `main`;
  feature pull requests target `develop`. So `Closes #N` in a feature pull request links but
  does not close, and issues stay open until the release merge. That follows from the
  branching model rather than contradicting it, but it will be surprising in practice.
- **A Projects v2 board cannot be grouped by labels** — table layout can, board cannot. That
  decided component-as-label versus component-as-project-field: labels now, because they are
  greppable, visible on the issue, and need no project scope.
- **Issue dependencies are native and `gh` supports them** as of v2.94.0, so the component
  ordering is expressible directly rather than through task lists.
- **`gh auth refresh -s project` is required** before any Projects work; `read:project` is
  not enough, and a fine-grained token cannot reach user-owned projects at all.
- Board grouping, slicing, and the auto-add workflow have no API path and must be set in the
  web UI.

## Open next

- The seven first-slice decisions: DX-01, DX-02, DX-03, DX-05, DX-06, DX-08, DX-10. DX-03
  and DX-08 change the shape of what gets built the most — the first defines the object
  every conclusion traces through, the second defines the rule that currently keeps the
  project's central distinction alive by prompt wording alone.
- The fixture leak, which needs no decision.
- Creating the milestones, labels, and project, then running the seeding script.
- The threat model, still absent, and still a Stage 0 deliverable.
