# 2026-08-09 — Opening M2: the context objects, and the first code that could call a model

The same day again, after `journal/2026-08-09-m0-final-decisions.md` closed the last two M0
decisions. This covers the first eight M2 issues: the six context objects, the model seam, and the
prompt registry. Two more decisions, DEC-036 and DEC-037, both forced by writing the code rather
than chosen ahead of it.

Twelve M2 issues remain — three runtime, six extractor, three review — so this is a progress entry
rather than a milestone one.

## The pattern from M1 held again, in a new direction

M1's entry recorded that writing code kept finding places where a document was internally consistent
and disagreed with a decision recorded after it. That happened again, and this time the disagreement
was usually between an *issue body* and a decision, because the M2 backlog was seeded on 2026-08-08
and sixteen decisions were recorded on 2026-08-09.

- **#60 asked for `confidence_score`** and asked where an agent's rationale lives. DEC-022 removed
  the first and added the second. Both were implemented rather than re-decided.
- **#140's editorial pass** was in its own scope: three issues still described contradictions and
  injection attempts as two separate representations to be chosen, which DEC-021 settled as one
  object with a `kind`. Their bodies now say so.
- **`agent-design.md` section 34 still listed `severity/recommend-severity-v1.md`**, the prompt for
  the agent DEC-030 excluded. Struck through in #173.

None of these is a problem, and the reason is worth restating: issue text is a snapshot and the
decision log is the authority. What makes it safe is having guards that read the *document* rather
than trusting the issue — which is what the conformance test did twice this session, once
deliberately and once by accident (below).

## DEC-036 — the fixture decided it

`data-model.md` heads four lists "…-type **examples**" and types every one of those fields `string`.
The open question was whether to read that literally or to close the vocabulary.

The project's own benchmark answered it. `demo/forgeflow/input/structured-system-input.yaml` uses
seven component types, and section 11 lists exactly one of them. A closed enum built from the
document would reject the scenario Trace exists to assess — which is a schema being wrong about
itself rather than strict.

The deeper reason only became clear while writing the docstring: the failure mode of a closed enum
here is *quiet*. It makes the model's list an authority over the document, the nearest allowed value
gets chosen, and a managed database becomes a `data_store` with the "managed" part — the part that
decides whether encryption at rest is inherited — silently discarded. That is the same failure
`requirements/README.md` already argues about `acceptable_implementations`, which is a good sign the
principle is real rather than local.

What free text actually breaks is *spelling*, not vocabulary. Three spellings of one type make
counts wrong and comparisons meaningless, and normalization fixes all of it without deciding what a
type may be.

`DataFlow.direction` is the counter-example that keeps the rule honest, and finding it is what made
the rule statable: a description reading "Service, datastore, external system, **etc.**" names
examples, and one reading "One-way or bidirectional" names values. The `etc.` is the discriminator.
It is also a property nobody was maintaining deliberately, which is recorded as a tradeoff — a
future field can land on the wrong side of the rule by accident.

## DEC-037 — an omission is not an argument

Actor was contested: `agent-design.md` section 7, the roadmap twice, and the section 2.1 prefix said
it exists; section 40's list and open question 4 said nothing. An absence of an argument is not an
argument.

The deciding sentence was the issue's own: *an extracted actor that nothing references is worse than
an absent one*. `SystemContext` is what a reviewer approves, so an actor outside it would be
extracted, persisted, approved by nobody, and reachable by nothing. Either the field exists or the
object does not.

DEC-034, recorded a few hours earlier, turned out to have already staked a position. It registered
`act` on the grounds that Actor is a real assessment-scoped object, and recorded "a prefix naming
nothing" as the cost of getting that wrong. Deferring Actor would have realized exactly that cost.
Two decisions agreeing across a few hours is not proof, but it is the first time in this project
that an earlier entry constrained a later one without anyone planning it.

## The asymmetry that is the whole project in one validator

`ContextClaim` has the rule everything else rests on: `documented` and `inferred` must cite
evidence, and `assumed` and `unknown` must **not** be required to.

Writing it made the reason sharper than the decision log states it. A schema that demanded evidence
everywhere would not stop an extractor from making unsupported claims — it would leave the extractor
choosing between dropping a claim and mislabelling it, and mislabelling is how missing documentation
becomes a reported vulnerability. The honest label has to be the cheap one. That is DEC-009
expressed as an incentive rather than as a prohibition, and it is the first place in the code where
the project's thesis is enforced rather than described.

## Absences need tests, or they are omissions waiting to be corrected

Three objects are defined partly by what they do not have, and each needed a test saying so:

- **`SourceObservation` has no severity.** It is a rule, not an oversight: severity would be the
  first step of a path from "these two paragraphs disagree" to "a vulnerability exists".
- **`ContextClaim` has no field naming what contradicts it.** The link runs one way so the two
  cannot disagree about whether they disagree.
- **`Actor` has no `status`**, alone among the five architecture objects, because section 13's table
  has none.

Without a test, each of those reads as something a later reader would helpfully add.

The one-directional link also forced a design answer #140 left open: a claim cannot enforce its own
`contradicted` status, because nothing on the claim can see the observations. So it is *detected*
rather than made impossible — `unsupported_contradictions` is the check, and repairing it silently
would be worse in both directions: clearing the status discards a contradiction someone recorded,
and inventing an observation fabricates evidence.

## The conformance guard was right and I was wrong, twice

`SystemContext`'s six identifier lists were written with `default_factory=list`, which is the
obvious thing. The guard rejected it: section 9 marks all six `Required: Yes`, and the guard reads
required as "the constructor must be given a value".

It was right, and the reason is better than the rule. An absent list and an empty list are different
claims about an extraction, and only one of them is something a reviewer can approve. The same
collision has now happened three times — `trust_level` on `SourceDocument`, `AssessmentConfiguration`
in #49, and this — and each time the document was right.

The package-layout guard also fired twice, once for `infrastructure/model` and once for
`services/prompts`, which is what it is for: a new subpackage should arrive as a decision rather than
as a side effect.

## `capture_edit` exists because of how the record gets written wrongly

`ReviewerDecision` is easy to model and easy to use wrong. The natural mistake is assembling
`prior_value` *after* the edit has been applied — at which point the generated state is gone, and
the record faithfully reports that nothing changed. A constructor that takes both states cannot be
used that way. The helper is not convenience; it is the shape that makes the mistake unavailable.

Three objects now name another object's type in a free-text field, so `ParsedIdentifier.object_term`
gives an object type one spelling. `context_claim`, not `contextclaim` in one module and something
else in the next.

## The seam, and a mapping that reads backwards

The model seam is the first code that could call a model. Nothing calls it.

Two things settled while writing it that DEC-014 implies without stating:

**A failure is a result, not an exception.** The adapter catches every provider condition and returns
a `ModelFailure`. The reason is not defensiveness — the caller has to record a cost and a duration
either way, and an exception escaping the adapter would leave the execution ledger with a node that
started and never finished.

**Creativity maps to effort, which reads backwards for a moment.** `temperature` is rejected on the
current Anthropic models, so section 29's intent has to land on the controls that exist, and the
only one is deliberation. More latitude means more room to explore before committing. A
low-creativity agent still reasons carefully — it is grounded by its prompt and its evidence rules,
not by being given less room to think. The mapping is recorded on every result because a wrong
mapping is invisible: it produces plausible output rather than an error.

The replay cache key is wide because section 30 says caching must not hide workflow changes during
evaluation. The asymmetry is what justifies the width: a key too narrow produces a wrong conclusion,
a key too wide produces a wasted call.

## The prompt registry, and a directory nobody could create correctly

`agent-design.md` section 34 and `current-architecture.md` section 10 described the same directory
differently — hyphenated with a `shared/` tree against underscored with a different file set.
Section 34 won and section 10 was rewritten, because two documents describing one directory
differently is a directory nobody can create correctly.

The loader's design comes from one observation: a prompt missing `source-content-boundary-v1` still
exists, still composes, still runs, and still returns a plausible object. It has lost the rule that
says instructions inside a source document are data, and lost nothing else. So a declared block that
is not in the tree raises, and the error names it.

Two of its tests are vacuous today, running against an empty `prompts/` tree. They are in anyway:
they are the checks that have to be running *before* content arrives, and adding them afterwards is
how they get forgotten.

## Process: a commit landed on `develop`

One commit was made directly on `develop` after a merge, because I did not cut a branch. The push
was rejected — branch protection working exactly as `CLAUDE.md` describes — and the commit was moved
to a branch and merged through the normal pull request. Nothing reached `develop` unreviewed, and
the guard that caught it is the one the repository documents as load-bearing.

## What is open

- **Runtime:** #66 the node protocol and transition table, #67 the error taxonomy and bounded retry
  policy, #68 checkpoint pause and resume. These three are what turn a set of objects into a
  pipeline, and #67 is where `FailureReason.retryable` stops being a property and becomes a policy.
- **Extractor:** #69 through #74, including the prompts the registry currently has nothing to
  compose.
- **Context review:** #75 through #77, ending with the command-line surface for the slice.
- The decision log stands at DEC-037. Nothing in it is Proposed.
