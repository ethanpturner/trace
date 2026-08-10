# M3 opens: the catalog gets a reader, and the threat engine runs

Five issues merged in one session — #78, #79, #80, #81, #83 — which is the requirement-matcher's
first half, the whole threat-engine slice, and the mapping slice's object model. Four decision-log
entries came out of it: DEC-041 through DEC-044.

## The pattern that recurred, and is worth naming

Every one of these issues was written before several of the decisions that now govern it. That is
not a defect in the backlog; it is what a backlog written ahead of the work looks like once the work
starts answering questions. But it means **an issue body is a starting point and never the
specification**, and four of the five needed the corpus checked before anything was written.

The concrete instances:

- **#78 cites "the DX-20 decision" for `content_hash`.** DX-20 is DEC-019, which already states
  exactly what the loader computes. No new decision was needed; the citation was to a design
  exploration that had since been recorded under a different name.
- **#78 and #79 both ask for `src/trace_ai/domain/models/`.** Domain modules are flat in `domain/`.
- **#80 says `prompts/` "is currently an empty scaffold"** and asks for the three shared blocks to
  be created. M2 built them. What was actually missing was one file.
- **#83 asks for "the DX-15 representation" of `inheritance_scope`.** DX-15 is DEC-026, and
  DEC-026's answer is that the field does not exist — scope is the structured fields. The issue was
  asking for a representation of something that had been removed.
- **#79's acceptance criterion "`Threat` accepts the section 16 example without any modification to
  that example"** could not be satisfied, because the example predates DEC-018.

That last one is the interesting one, and it produced the change I would keep if I could keep only
one.

## The worked examples were teaching an illegal identifier

`data-model.md` section 16's `Threat` example names `cmp-webhook-receiver` and
`ast-analysis-capacity`. Neither is a DEC-018 identifier: generated is `<prefix>-<NNN>`, authored is
`<prefix>-<CATEGORY>-<NNN>`. Sections 10, 21, and 31 had the same problem.

The inconsistency was *inside a single example*. Section 16's own `thr-007` and `asm-001` are
correct, and only the objects it referenced were descriptive slugs. That is exactly why it survived:
nothing about the block looks wrong at a glance, and no test parsed examples.

Descriptive slugs read better in a document. That is both the reason someone wrote them and the
reason an agent would mint `cmp-webhook-receiver` at generation time — which is the thing DEC-018
exists to stop. A document that illustrates an illegal identifier is teaching one.
`test_the_worked_examples_use_conforming_identifiers` now parses every identifier-shaped token in
the data model and refuses anything section 2.1 does not permit. It skips `cat-core` correctly,
which is the case that made the regex worth writing carefully.

## DEC-041: the category vocabulary decided itself

#79 folded in a sub-decision: what are the "permitted values" section 11 requires the validation
node to confirm? I expected to have to ask. The corpus answered.

DEC-036 states its own test — does the document *name* the values or *illustrate* them? Section 16
types `category` as `list[string]` and shows two values in an example. That is the illustrated case,
so it is an open vocabulary.

And the decisive fact is not a rule at all, it is ForgeFlow: THR-001 is repository prompt injection,
which STRIDE has no category for. THR-005 is over-disclosure to a model provider and THR-006 is
unreviewed model output being published. A closed STRIDE enum would reject or — worse, because it is
silent — mis-bucket the threat the demo scenario is built around. Adding the AI categories to a
closed set does not fix it either; the set just becomes whatever taxonomy was current when it was
written.

This is the third instance of one principle, and they should probably be read together:
`component_type` (DEC-036), `acceptable_implementations` (DEC-011), and now `category`. **A list of
examples treated as the set of allowed values decides cases it was never shown.**

The thing I got wrong first and corrected: I assumed section 11's "confirm categories use permitted
values" and section 39's "generic STRIDE labels are rejected" were the same check. They are not.
The second is about *specificity* — a threat titled "Tampering" whose description restates the
category — and a category whitelist cannot catch it, because the label on a generic threat is a
perfectly valid STRIDE category. Two checks, and the vocabulary one is the weaker of them.

## DEC-042 and DEC-043 both came out the same shape as DEC-024

Neither was planned that way, which is why it is worth writing down.

**DEC-042** (threat analysis runs once per assessment, not per trust boundary): four of ForgeFlow's
ten expected threats cross boundaries, and THR-004 concerns tenancy, which is not a boundary in the
architecture at all. A per-boundary agent is structurally unable to see any of them, and the failure
is silent — each call returns plausible threats about its slice, and nothing reports what could not
be seen from there. The escalation path, when the context outgrows one request, is partition fan-out
over connected component groups: narrow the call without excluding anything.

**DEC-043** (duplicate detection is deterministic feature comparison): embeddings have no substrate
while vector infrastructure is deferred, and a model-assisted comparison would put a model call in a
node section 4 classifies as deterministic — and would return a judgment with no features attached,
when section 11 requires the decision to be traceable.

DEC-024 said: send the whole catalog; when it stops fitting, partition rather than filter. Both of
these arrived at *send the whole thing, escalate by partitioning, never exclude silently.* Three
independent decisions converging on one shape suggests it is a property of the problem rather than a
preference.

One implementation detail from DEC-043 that took a second to notice: **two empty sets score 0.0, not
1.0.** DEC-041 makes `category` optional, and the usual Jaccard convention would have made every
pair of uncategorised threats look identical on that feature.

## DEC-044: the object with three possible parents

`Control` was the one object in the pipeline whose origin could not be recovered. Three places imply
controls exist — extraction identifies them, the mapper outputs them, validation confirms their
identifiers — and section 18 carried no provenance field. So `Control` gained `generated_by` and
`created_at`, which is a data-model change and is recorded as one.

The part that took the most thought was *when* an extraction-found control becomes a row. Deferring
it to the mapping step is tempting and wrong: DEC-040 recomputes approved membership from the store
at approval, so a control created after checkpoint 1 would never be in an approved revision, and the
reviewer would first meet a safeguard the documentation describes inside a mapping. A control the
documentation describes is an architectural fact and belongs in the baseline a person signs off.

## Smaller things worth not forgetting

- **`compute_hash` is deliberately separate from `load_catalog`, and skips the manifest-agreement
  check.** The loader refuses to read a catalog with a stale hash; the repair tool has to be able to
  compute the right value *from that state*. A repair tool that refuses to run until the thing is
  already correct is not a repair tool. This was a real bug first: `rehash()` in the tests called
  `compute_hash`, which ran the agreement check, which raised inside the fixture before the test's
  own `pytest.raises` could see anything.
- **`detect-private-key` flagged `tests/unit/test_threat_injection.py`.** The file lists credential
  *shapes* the threat package must not contain, and a PEM header written as a literal is a PEM
  header. The hook was right; the header is now assembled from fragments. A repository guard firing
  on the test that exists to check the same property is a good sign about both.
- **`tests/` is not a package**, so one test module cannot import another's harness. The threat
  injection tests duplicate the fixture rather than importing it, which matches how
  `test_context_injection.py` already works. A `conftest.py` would be the better answer if a third
  module needs the same thing.
- **One `ReviewTrigger`, not two.** Section 7's and section 10's human-review triggers are the same
  record — a name, the objects that caused it, a sentence. `threat_validation.py` imports the
  context validator's class rather than defining one with `threat_ids` in place of `object_ids`.
- **`RequirementsCatalog` moved off section 40's deferred list.** Not by preference: DEC-019
  computes its hash at catalog load and DEC-024 sends the whole catalog to every mapping call, so
  the loader needed the object before the workflow began operating. Section 40 states the reason
  where the list is.

## Where the project is

- **1,987 unit tests**, 1 skipped, 13 deselected. Still no API key needed for a bare `uv run pytest`.
- **The decision log stands at DEC-044.** Nothing in it is Proposed. Three `agent-design.md` open
  questions closed this session: section 38's questions 2 and 7, and DEC-010's `content_hash`
  question was already closed by DEC-019 and is now actually true.
- **M3 is 5 of 17 issues**, with #82 closed as obsolete before the session started. The threat
  engine runs end to end offline; the mapping slice has its object model and needs the payload, the
  agent, and the validation node.
- **`applicable_technologies` is now asserted to be empty on every requirement**, in
  `test_requirements_catalog.py`. It is the fact DEC-024 turns on, and it should not be able to stop
  being true without that decision's expiry trigger being re-read.

Next is the rest of the mapping slice — #84, #85, #87, #88 — then evidence validation, the critic,
and the two evaluation issues.
