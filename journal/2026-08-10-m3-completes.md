# M3 closes: the analysis half exists, and five decisions came out of building it

Twelve issues merged in one session — #84, #85, #87, #88, then #89, #90, #91, then #92, #93, #94,
then #86 and #95. That is the mapping slice, the evidence-validation slice, the critic, and both
evaluation issues. Five decision-log entries came out of it, DEC-045 through DEC-049. The
milestone is empty.

The pipeline now has five of its six agents. Context Extraction, Threat Analysis, Requirement and
Control Mapping, Evidence Validation, and Critical Review all exist with their prompts, their
input packages, and a deterministic node behind each. Report Generation is the sixth and is M4's,
along with Finding Consolidation and checkpoint 2.

## The shape that repeated, and why it is worth naming

Four of these twelve issues asked for a validation node behind an agent, and by the fourth the
question had changed from "what does it check" to "who writes". The answer moved, and the move is
the most consequential thing in the session.

For the mapping slice the arrangement is the one M2 established: the agent node persists, having
validated first, and a separate function validates the persisted objects afterwards. Section 22's
write model — agents never write authoritative records — is true by convention there. A future
edit that persisted before validating would break nothing visible.

For evidence validation it became structural, and not by design. `NodeResult` carries identifiers,
counts, and costs and never an object, because `data-model.md` section 31 says a state carrying
content is a second copy of the authoritative data. So the proposal could not travel from the
agent to the validator through the normal return value. The workaround — a `propose()` method
returning the package, the proposal, and the result — put the write on the far side of the
validator, and `workflow/evidence_validation.py` ended up with no `objects.save`, no
`.transaction()`, and no `allocate(` in it at all. Section 22 became a property of the import
graph.

That was good enough to repeat deliberately for the critic. Both modules now have a test asserting
the absence, and DEC-048 records that this is the strongest available form of the rule and that
the other three agents do not have it. Whether they should is one of that entry's open questions.

## DEC-045: the field with no second chance

`DocumentationGap.severity` looked like a five-minute question and was not. DEC-030 gives severity
to the reviewer at checkpoint 2 and has findings arrive `unassigned`; the obvious move was to do
the same for gaps.

It is wrong, and the reason is `current-architecture.md` section 5.12. Checkpoint 2 lists actions
on *findings*. The gap-shaped action there is converting a finding *into* a gap. Nobody is ever
asked for a gap's severity, so a gap created `unassigned` keeps that value through the whole
pipeline and renders into report section 9 with it — a decision nobody was asked to make,
displayed as though someone declined to make it. So the mapping step assigns it and the model
refuses `unassigned` outright.

The general lesson is the one to keep: **a default that waits for a later step is only honest if
the later step exists.** `unassigned` is a perfectly good value on `Finding` because checkpoint 2
resolves it. The same value on a different object with no resolving step is a hole.

## DEC-046 and DEC-047 are the same decision about two different fields

Both answer "where does this record live", and both refuse the same shortcut.

DEC-046 gives `ControlMapping` a `downgraded_from` and `downgrade_reason` when validation lowers
an unsupported `unmet`. The obvious shortcut was to reuse DEC-025's `suppressed_conclusion` and
`suppressed_by` — they are both records of a conclusion not drawn, after all. Reusing them
destroys the measurement both exist for. A high suppression count with a low downgrade count means
the *catalog* is over-suppressing, which DEC-011 names as its principal risk. The reverse means the
*agent* is reaching for negatives the evidence does not carry. One pair of fields gives one number
that cannot tell a catalog problem from a model problem.

DEC-047 gives `EvidenceAssessment` a `recommendation`, because section 14 lists recommendations
among the agent's outputs and section 20's field table had nowhere to put one. The shortcut there
was to keep it on the proposal and drop it at promotion. That removes the only signal that would
show the agent and DEC-013's deterministic outcome table disagreeing.

Three entries now — DEC-044, DEC-046, DEC-047 — have taken the same shape: the corpus names an
output, the field table has no home for it, and the answer is to add the field rather than let it
evaporate at the proposal boundary. That is worth treating as the default.

## DEC-046's other half: the rule that only half runs

DEC-013 gives four conditions for `unmet` and says enforcement happens twice — Mapping Validation
applies the `unmet` rule, Finding Consolidation applies the outcome table. Implementing it exposed
that two of the four conditions read `EvidenceAssessment`, and `current-architecture.md` section
5.3 puts Evidence Validation *after* mapping. At Mapping Validation there are no assessments.

The tempting implementation is the dangerous one: check them anyway, treat a missing assessment as
a failed condition. That downgrades every `unmet` in every run, unconditionally, and looks like a
strict evidence rule rather than like a field that is not populated yet. Nothing fails; the
assessment simply never reports an unmet requirement and the false-negative rate moves with no
attributable cause. A test now pins that this does not happen.

Two of DEC-013's conditions also turned out to be unreachable for a different reason: the schema
already refuses them. `ControlMapping` will not construct an `unmet` with no evidence. So the node's
check for that is a second line, reachable only through `model_construct`, and the tests say so
where they use it rather than leaving a reader to conclude the node is doing the schema's work.

## DEC-049: the entry that had to resolve a contradiction rather than fill a gap

The critic's issues cited a decision that did not exist, so its scope had to be settled: the unit
of work, the identity of "candidate finding material", and whether it may propose missing threats.

The first two were mostly derivation. One threat's lineage is the review group, because section
15's twelve concerns are almost all *comparisons* — an ignored inherited control compares a mapping
against a control, a mislabelled documentation gap compares a conclusion against its evidence — and
none of them is makeable from a single object while all of them are makeable from one chain. That
also matches what the pipeline already does, since DEC-024 made mapping per-threat for its own
reasons.

The third was different. Section 15 lists "missing high-impact threats" among what the critic
looks for and "candidate missing-threat proposals" among its outputs, *and* makes "critiques lack
target objects" invalid output. A missing threat has no target object by definition. Three
statements, one of which has to give.

The failure condition wins, for two reasons. It is the one a schema can enforce, and section 27's
loop-prevention worked example is exactly this case from the other side: the critic may recommend
that a threat be reconsidered and may not start a threat-generation loop. A critic-proposed threat
would also be generated outside the single call DEC-042 specifies, from different inputs, with the
Threat Validation node several phases behind it — there is nowhere for it to be validated and no
phase for it to be generated in.

A real capability is gone and the entry says so under Tradeoffs rather than dressing the loss as a
scoping decision. Roadmap Stage 4 gates the critic on whether it improves results at all, and
building the widest, least verifiable thing it asks for before that gate is building the feature
most likely to be removed.

## The truth files, and the test that stops a negative suite lying

`demo/forgeflow/expected/` had two authored files and needed four more. The authoring itself was
mostly careful reading, but one design choice in the regression suite is worth keeping.

**A suite of negatives passes perfectly on a system that finds nothing at all.** Every case in
scenario section 14 and section 22 asserts that a claim is *not* made, and an assessment producing
no output satisfies every one of them. DEC-011 already names over-suppression as
`common_false_positives`'s principal risk; as a test-design problem it is the same thing.

So the truth files carry `genuine_weaknesses` alongside `must_not_conclude`, and each of scenario
section 13's five weaknesses gets a case asserting it stays *reachable* — given a mapping whose
rationale addresses the false-positive entry, `unmet` survives validation. If a catalog edit made a
weakness impossible to conclude even with qualifying evidence, those cases fail and no negative
case would notice.

The second choice: every negative names its mechanism, and the test asserts the mechanism rather
than the absence. A regression test that passes for an unknown reason is not evidence of anything.
The suite constructs the wrong conclusion directly, runs it through `validate_mappings`, and
asserts the downgrade and its recorded reason — which is why almost all of it runs with no provider
key. A test that waited for a model to decline to say something would be measuring the model; this
measures whether anything would stop it.

## Smaller things worth not forgetting

- **The mapping payload raises where the threat payload excludes.** Both bound their input; they
  differ because a threat citing fewer passages is still a correct threat, while a mapping run
  against part of the catalog is a complete-looking run that silently never considered the rest.
  DEC-024's escalation is partitioning, not truncation, and that is an orchestration decision an
  assembler may not take on its own.
- **`UnapprovedContextError` gained a `step` argument rather than a sibling class.** Section 9
  states the rule once — threat analysis and everything after it works from the approved baseline —
  so two classes would be two places to keep one DEC-005 citation correct. Same reasoning as the
  journal's earlier `ReviewTrigger` note.
- **A self-scanning test finds its own literals.** `test_no_case_asserts_a_minimum_output_count`
  scans its own file for `minimum_findings`-shaped names and found the name in its own assertion.
  The forbidden strings are now assembled from parts.
- **`test_data_model_conformance.py`'s section 40 parser split on commas only**, so "Add
  PromptDefinition and EvaluationResult" parsed as one name. It now splits on both, which lets the
  sentence read naturally whether it lists two objects or four.
- **A force-push retriggers CI and the old run's success does not carry.** PR #207 sat `BLOCKED`
  with a green check because a second run for the same required context was still in progress on
  the same SHA. Worth checking `check-runs` rather than `pr checks` when a green PR will not merge.
- **`EvidenceAssessment` and `Critique` both moved off section 40's deferred list**, and neither by
  preference. DEC-022 made the first the only home for `EvidenceStrength` and DEC-013's `unmet`
  rule reads its `validation_status`; roadmap Stage 4 gates the critic on evidence the gate cannot
  produce without the second.

## Where the project is

- **2,590 unit tests**, 1 skipped, 65 deselected. Still no API key needed for a bare
  `uv run pytest`. `uv run pytest -m evaluation` adds 53 offline regression cases and 11 skipped
  live ones.
- **The decision log stands at DEC-049.** Nothing in it is Proposed.
- **M3 is 17 of 17**, with #82 closed as obsolete before the milestone started.
- **One document disagreement is open on purpose.** DEC-048 records that `agent-design.md` section
  3's workflow diagram should gain the Evidence Assessment Validation node it does not draw.
  Editing that document is separate work and has not been done, so a reader of the diagram alone
  will believe evidence validation has no follow-up node.

M4 is Finding Consolidation, checkpoint 2, the Report Generation agent, and the renderer.
