# 2026-08-08 — The switch that defeated the constraint

Closes #20, the first decision off the M0 milestone, as DEC-012.

## The contradiction

Three documents said three things about whether the two human checkpoints can be turned off.

`CLAUDE.md`, `README.md`, and DEC-005 said structural and not configurable.
`data-model.md` section 6 typed `require_context_review` and `require_finding_review` as
required booleans on `AssessmentConfiguration`, which is the definition of configurable.
`evaluation-plan.md` section 14 proposed "Human checkpoint vs No checkpoint" as a workflow
comparison, which needs the switch to exist.

Four of the six research passes that produced this backlog hit this independently, from four
different directions, which is why it went in as the first M0 issue.

## What changed the answer

Reading section 14 in context rather than as a line item. The checkpoint comparison sits in a
list with single agent against multi-agent, critic enabled against critic disabled, and
evidence validation against no evidence validation, and the section closes by saying the
purpose is to determine whether architectural complexity improves outcomes.

Every item in that list is an experiment on the architecture. None is a per-assessment
setting. The checkpoint comparison is not one either — it had simply been read as one because
the only mechanism available to express it was a configuration field.

The second thing, which took longer to see: **two different needs had been collapsed into one
boolean.**

Running 8 to 12 benchmark scenarios repeatedly requires checkpoints to be answered without a
human sitting there. That is a scheduling concern. The checkpoint node still executes, the
gate still holds, and a `ReviewerDecision` is still written — the decisions just come from a
recorded file instead of a keyboard. Reviewer acceptance and edit rates stay measurable.

Removing the checkpoint is a different thing entirely. It asks whether human review improves
outcomes, and it produces findings no human approved.

Only the second changes the pipeline, and it is the one that must never be reachable from an
ordinary run. The corpus had one field trying to serve both, and because the field lived on
the assessment's own configuration object, the dangerous one was the reachable one.

## The decision

Remove both fields. Checkpoints are workflow-graph nodes rather than runtime conditionals, so
there is no value to set. The section 14 ablation moves to the evaluation harness, where a run
that applies it is recorded as non-authoritative and names the ablation.

Marking it at the point of production rather than inferring it later is the part I would
defend hardest. An ablated run produces exactly the artifact DEC-005 exists to keep out of an
assessment. Working out afterwards, from a configuration value, that a set of findings was
never reviewed is a worse position than being told so by the run itself.

The cost is real and worth naming: this is a data-model schema change, section 6 was
authoritative for those fields, and the ablation now lives further from the checkpoint code
that implements it. A future change to the checkpoint could leave the harness path stale.

## What else had to move

DEC-012 resolving DX-01 made a live backlog issue wrong. #49, the Assessment object,
instructed an implementer to build both fields as required — which would have reintroduced the
contradiction the decision had just removed. Its body and acceptance criteria are amended, and
the acceptance criterion is now inverted: a test asserts that constructing an
`AssessmentConfiguration` with either field is *rejected*. The absence is the behaviour under
test, so it reads as deliberate rather than as an oversight.

That is the first time the manifest-in-the-repo arrangement had to earn itself. The issue text
lives in `scripts/backlog_bodies/`, so correcting it was a diff rather than an edit typed into
a web form, and the repo and GitHub were re-synced in the same change.

#68, the checkpoint machinery, needed no scope change — it already asked for a guard where
disabling a checkpoint is "not merely discouraged but unrepresentable", and removing the fields
is what makes that true. It got a comment noting the replay-versus-ablation distinction, since
whoever implements it needs a non-interactive decision source and that is not a switch.

## Open next

DEC-012 leaves three questions open, all of which belong to work not yet started: where the
non-authoritative marking lives, whether an ablated run should be prevented from producing a
report at all rather than producing a marked one, and whether the replay decision file belongs
with the benchmark scenario or with the run that produced it.

#26, the evidence threshold, is now the widest-blast-radius decision remaining. Until it lands
the Finding and DocumentationGap boundary is enforced by prompt wording, which design principle
7 says is not enforcement.
