# 2026-08-09 — Rejecting the framework, and closing the last Proposed entry

Closes #25 as DEC-016. DEC-007 is marked Rejected. Every entry in the decision log is now Accepted
or Rejected, and none is Proposed — the first time that has been true.

## What made this decidable

DEC-007 proposed LangGraph on 2026-08-05, before the workflow's shape existed. The shape now
exists, and it is the case a graph framework helps least with.

**The pipeline is a list.** `current-architecture.md` section 5.3 names fourteen phases in order,
with pauses at 5 and 11. There is no analytical branching. The conditional routing that exists is
local error handling — a validation node routing to retry or to human review — not the workflow
choosing between analytical paths. Fourteen ordered phases and two pauses is a transition table of
about twenty lines. A graph framework earns its cost on graphs whose shape is not known until
runtime; this graph is known now and written down.

**The state design already describes a database row.** `data-model.md` section 31 says workflow
state should hold "identifiers and concise routing information," with large objects in the
persistence layer. That is a `WorkflowRun`. Adopting a framework whose central value is managing a
state object, for a state deliberately designed to contain no objects, would be paying for the part
that was designed out.

**A checkpointer would be a second authoritative store.** This is the one that decided it. DEC-006
makes structured domain objects the authoritative state and gives the application ownership. A
framework checkpointer persists its own serialized copy, on its own schedule, in its own format.
Two stores that can disagree is exactly the condition DEC-006 exists to prevent, and reconciling
them would be permanent work in service of the dependency rather than the assessment.

**The limits that matter are invisible to a framework.** Section 27 requires ceilings on model
calls, cost, and duration; `AssessmentConfiguration` carries them. A cost ceiling means nothing to
an orchestration framework — it does not know what a model call costs, and after DEC-014 that
metadata arrives through the seam. Those checks get written either way. What the framework would
have supplied is the part that was already trivial.

## The pattern across the four decisions

DEC-012 made the checkpoints graph nodes rather than runtime conditionals and pushed the ablation
out to the evaluation harness. DEC-014 put the model behind a seam the application owns. DEC-016
declines to hand the loop to a framework. Each moved control into the application, and each was
decided on the same grounds: a second thing that could hold authority over the same state is worse
than writing the small amount of code that keeps authority in one place.

That was not planned as a theme. It emerged because DEC-006 — structured objects are authoritative
and the application owns them — turns out to have more consequences than it looks like it has.

## What I gave up, honestly

Graph visualization is the one real loss. The README already draws the pipeline in Mermaid by hand,
and the hand-drawn version is better: it distinguishes model-assisted steps, deterministic nodes,
and the two human checkpoints, which is a distinction the framework has no concept of and could not
have generated.

Retries, limits, resume, and the transition table are now code the project owns and tests. Small
individually; not free in aggregate.

And the decision is right for the pipeline as specified, which is a narrower claim than right. If
analysis later needs genuine branching, refinement loops, or parallel nodes, a hand-written
orchestrator grows toward being a worse framework. The trigger to revisit is stated in the entry:
a workflow that is no longer a list. Whether that trigger is observable *before* the orchestrator
has already grown is one of the open questions, and I do not have a good answer to it.

## Dependencies

`langgraph`, `langchain`, and `langchain-anthropic` removed. With DEC-014's removal of `instructor`,
`openai`, and `langchain-openai`, `anthropic` is now the only provider SDK declared and there is no
framework dependency at all.

Six declared-and-unused packages are gone across two decisions. `CLAUDE.md` used to warn that their
presence was not a choice; that warning is no longer needed because the presence is now a choice in
both directions.

## The portfolio angle, which is real here

`roadmap.md` Stage 6 asks for "why LangGraph was or was not retained" — it wanted the answer either
way, which is unusual and correct. Having evaluated the obvious framework against a specified
workflow and removed three dependencies is a better account of engineering judgment than having
adopted it because it is what these systems usually use. The entry is written so that account can
be given from it directly.

I have updated the roadmap line to say "evaluated and rejected" rather than leaving it open.

## Open next

DEC-016 leaves four questions, all about the orchestrator's own shape: whether the transition table
is data or code and whether a test checks it against the documented phases; whether a dry-run mode
is needed; when a workflow stops being a list; and where the five ceilings are checked.

DX-07 (#28), the checkpoint pause and resume mechanism, is now constrained by this decision — it
must work from a persisted row. That is the next orchestrator-adjacent decision.

Five M0 decisions remain closed out of twenty-two, and the four that gated M1 and M2 are all done.
The release to `main` follows this.
