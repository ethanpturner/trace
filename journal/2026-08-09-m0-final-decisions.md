# 2026-08-09 — The last two M0 decisions, and what a stray value was really about

M0 had two decisions left after M1 finished: the report's shape (#38) and the requirements
catalog's identifier (#137). Both are now recorded, as DEC-034 and DEC-035, and the M0 Decisions
milestone is closed. Twenty-four decision issues, thirty-five entries in the log.

The two turned out to be the same kind of problem in different clothes: a value or a list that was
internally consistent, and a *rule* that nobody had written down.

## DEC-034 — the question was not `cat-core`

`requirements/catalog.yaml` called itself `cat-core`. `cat` is in no prefix list, and the shape —
prefix followed by a bare word — is neither of DEC-018's two forms. The issue offered four options:
register `cat`, rename the value, put the object outside the scheme, or drop the field.

The useful move was to notice that none of those is about `cat-core`. Section 2.1 lists twenty
prefixes and never says *what the list is for*. A document like that invites every object with an
`id` field to acquire a prefix by resemblance, which is exactly how the value was produced. Renaming
it would fix one file and leave the next authored object free to repeat it.

So the entry states the rule: **the scheme governs objects an assessment produces** — scoped to one
assessment, persisted by the store, referenced by identifier from somewhere else. `Requirement` is
the one authored member, because assessment objects cite `req-AUTH-001`. Authored configuration is
outside it and carries a *name*: a lowercase slug, identity `(id, version)`.

`PromptDefinition` is what turned this from an exception into a rule. It has an `id`, it has no
prefix, the corpus writes it everywhere as `extract-context-v1`, and in thirty-three decisions
nobody proposed `prm-`. The catalog and the prompt behave identically. One rule covers both, and
that is the difference between a rule and a special case — the same shape DEC-030 found when a
seventh agent turned out to be re-deriving fields that already existed.

Stating the rule immediately made the registry provably wrong. Three assessment-scoped objects
carry an `id` and had no prefix: `Actor`, `EvidenceAssessment`, `Critique`. So the entry adds `act`,
`eas`, and `crq`, and the registry is twenty-three. This is the part I nearly deferred, and
deferring would have been wrong for a reason worth recording: a closed registry that is incomplete
is not a closed registry, and three in-flight issues would each have invented a prefix independently.

`SystemContext` is the interesting negative case. It has no `id` at all — it is keyed by
`(assessment_id, version)` — and under the stated rule it needs none. The rule predicted an
existing design choice it was not written to explain, which is the best evidence available that it
is the right rule.

The marker test from #44 did its job exactly as designed. It asserted `cat-core` does not parse and
was written to fail the day the issue was resolved; it failed today, and was replaced by tests that
pin the outcome rather than the defect.

## DEC-035 — the disagreement was a category error

`current-architecture.md` 5.13 lists fifteen report sections. `agent-design.md` 19 shows the agent
returning four. That reads like a contradiction and is not one: fifteen sections of a *document*,
four keys of an *agent's output*. Both are right the moment someone says which sections the agent
writes, and nobody had.

That is the consequential question, because it decides what the agent can get wrong. A model
returning a document can put a fabricated fact anywhere in it, and checking that means reading every
sentence against every object. A model returning four prose fields — none allowed to contain a
heading, a table, a link, or an identifier the input did not carry — is checkable.

Sixteen sections, each with exactly one owner: four prose, twelve rendered. Risk summary is the one
addition, and it exists so that no section is half narrative and half table. The interleaving is
what makes a report unverifiable, not the prose itself.

The change I did not expect to make is that **per-object prose leaves the agent**. Section 19
listed finding descriptions, threat summaries, gap summaries, assumption summaries, and a
recommended-priority narrative among its responsibilities. All five are now rendered. The argument
came from the checkpoint rather than from anything about reports: a `Finding.description` is text
the reviewer approved, and often edited, at checkpoint 2 under DEC-023. If the report regenerates
it, the reviewer approved one thing and the report says another, and "only approved content appears
in the report" stops being checkable in the place it matters most.

Limitations resisted that logic, and the resolution is the part of this entry I expect to reuse.
Limitations should read well — the section is where the assessment says what it could not do — but
the failure mode is omission, and prose completeness is not checkable. So the assembler computes a
`required_limitations` list, hands the agent an identifier and the facts for each, and the validator
checks the *set* by identifier. The model writes the words; the application guarantees the
membership. That is the same shape as the proposal pattern one level down.

Two smaller things I would have got wrong by default:

- **`report.md` would have failed on the second run.** The artifact store refuses to overwrite
  stored content with different content, which is a rule written for evidence integrity, and it
  applies here. Reports are named per run.
- **Heading-derived anchors are not stable.** They vary between Markdown renderers and change when a
  title is reworded. The template emits explicit anchor elements instead, and section numbers are
  literal rather than computed, so "section 12" means the same thing in every report and a link into
  last quarter's report still points where it did.

The template is committed as a **structural specification, not an engine template**. Adding Jinja2
buys string substitution Python already does, in exchange for a dependency and a second place for
logic to live — the same trade DEC-032 refused for `typer`. What the artifact is needed for is to
make the report's shape reviewable in one file and comparable against what the renderer emits, and a
test does that against a specification just as well.

The empty-findings wording is authored in the template rather than composed at runtime, and it is
tested for both halves: it must not read as a failure, and it must not read as a clean bill of
health. Zero approved findings is a valid outcome for this project in a way it is not for most
tools, and the sentence that says so is the one most likely to be quietly softened by someone later.

## What is open

- Both pull requests append to the end of `decision-log.md`, so the second needs a rebase after the
  first merges. Nothing else in them overlaps.
- `risk_summary` and `executive_summary` may converge in practice. If they do, one of them stops
  earning a section, and that is a Stage 3 observation rather than a decision to make now.
- `required_limitations` is a mechanism serving exactly one section. It is justified there and it is
  the kind of thing that gets copied to a second place by analogy rather than by argument.
- The M0 milestone is closed, so the next thing the backlog offers is M2: the runtime, the model
  seam, and the first agent. Every decision those depend on is now recorded.
