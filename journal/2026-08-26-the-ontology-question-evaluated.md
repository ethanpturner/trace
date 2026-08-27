# The ontology question, evaluated and declined — and what it returned instead

A session that started from a conference talk rather than from a defect, and that was worth having
mostly for the thing it was not looking for.

## What prompted it

Frank Coyle's AI Engineer talk argues that agent failures — brittle tools, fragile handoffs, drift
across iterations — come from a missing layer: a formal ontology outside the model, acting as
logical guardrails. The prescription is three layers, typed structure underneath, semantic
validation before any state change, and reasoning that proceeds only once both gates pass. The
question was whether Trace should adopt a graph database, an ontology, or both.

The first finding is that **the talk describes the architecture that is already here.** Agents
propose schema-validated objects, a deterministic node stands behind every one of them,
`extra="forbid"` turns an invented field into a validation failure, and no agent writes
authoritative state. What is left of the argument once that is noticed is the narrower claim that
the guardrail has to be RDFS or OWL specifically, and that is the part with no measured support.

## Why the formalism is refused

OWL makes the open-world assumption, so a reasoner can never conclude that something is missing.
It detects only that an assertion contradicts an axiom. Every check the Context Validation node
actually performs — a finding with no evidence, an unresolved proposal key, a flow naming a
component nobody extracted — is a completeness check, and completeness is precisely what the
open-world assumption forbids. The formalism cannot do the job the node exists to do.

The sharper version, and the sentence the entry in future-features is built around: **OWL's
unknown is passive and Trace's `unverified` is active.** OWL's unknown is the absence of an
assertion — nobody said it, so the reasoner declines. A `DocumentationGap` records that a search
was performed over a defined evidence scope and returned nothing, attributable to a run and
reviewable by a person. Those are different facts, and separating them needs epistemic operators
OWL 2 does not have.

SHACL can express what OWL cannot, which is what makes it the more dangerous of the two here. Its
verdict vocabulary is violation, warning, information — constraint importance, not epistemic
status — and it has no construct for an absence that is expected and benign. Putting a formalism
whose default speech act is *violation* on top of the DEC-009 distinction would leave a mapping
convention as the thing preventing the conflation the project exists to avoid.

The measurements point the same way. The nearest published implementation of this architecture in
the security domain reports constraint-violation rates of zero to under two percent before its
formal layer ran at all, because constrained structured output had already done the work. And in
the closest analog to Trace — LLM extraction of security documents diffed against a reference
graph — enforcing the ontology on model output raised node accuracy while suppressing discovery
outright, which the authors describe as masking undocumented infrastructure. That is measured
support for DEC-036, not against it: for a tool whose purpose is finding what documentation failed
to mention, accuracy bought by suppressing the unanticipated is the wrong trade at any number.

## Why the graph database is refused

The data is graph-shaped and the scale is not. Seventy-two declared edge types, most many-valued,
and a nine-hop lineage walk that ships — against roughly nine hundred objects and four and a half
thousand edges in one and a half megabytes. The graph industry's own benchmark floor is three
orders of magnitude above that, and the nearest published comparison has the relational engine
ahead on bounded fan-out from a known root, which is the shape of every query Trace makes. There
is no shortest-path query and no path enumeration, which are the two shapes where a graph engine
wins.

The objection that settles it was already written, though not for this. `lineage.py`'s docstring
says the walk is over identifiers the objects already carry, because DEC-006 makes the objects
authoritative and a second persisted lineage would be a second copy that could disagree. That is
DEC-016's argument about a framework checkpointer, aimed by its own author at exactly the artifact
a graph database would introduce, in the one module that most wants to be a graph. Nothing needed
to be decided; it needed to be noticed.

## The reversal that changed what got written

The survey concluded there was no design-time security-architecture ontology worth reusing. That
was wrong, and the reason it was wrong is the useful part: **the reusable material is
MIT-licensed plain data files inside threat-modeling tools, not ontologies.** The search looked
for the wrong kind of object.

Threagile's `technologies.yaml` carries around sixty component types, each with aliases and an
attributes map of semantic predicates — `may_contain_secrets`, `identity_store`,
`processing_end_user_requests`, `no_authentication_required`, `high_value_target`. That is a
machine-readable applicability representation, which is data-model open question 5 — the last
substantive open question in the model, deferred three times. DEC-024 deferred it because
`applicable_technologies` is populated on zero requirements and a pre-filter therefore has no
input. This is an input.

It is not permission to build the filter. DEC-024's second objection is independent and untouched:
a filter is a silent scope decision no reviewer sees, and a system that never considers most
requirements fails invisibly, because the requirement never appears at all. Having a
representation answers the representation question and nothing else. The future-features entry
says so explicitly, because the temptation to read one as the other is the whole reason that
question has stayed open honestly for as long as it has.

The other half is TM-BOM, which Trace already speaks under DEC-120. Its schema carries
`assumption.validity: unconfirmed | confirmed | rejected` — the closest published analogue to the
Finding-versus-DocumentationGap discipline, arrived at independently by an OWASP project. Worth
citing in the Stage 6 narrative for the convergence alone.

## Two numbers that did not survive, and one licence that did not either

The evidence was audited against itself, and two figures that would have flattered the proposal
came apart:

- **DEC-107's nine-times partitioning penalty is not a taxonomy cost.** It is remainder
  duplication. The two-way split, with no taxonomy involved, already costs 1.8×. Flatness sets the
  magnitude; it does not set the sign.
- **"Twenty of seventy-nine spurious findings were naming artifacts" over-claims.** Nineteen of
  the twenty land on baseline arms, where a finding carries one free-text component string and a
  two-component answer fails equality with either. That is a harness data-shape defect. Trace's
  own correction is one.

DEC-149 remains the clean attribution and did not need help: the component qualifier is
non-discriminating, because no two expectations in a scenario share a `requirement_id`, and
unbindable, because no benchmark scenario declares components, so both names are summaries of one
prose description with no referent between them.

A process note worth keeping. A licence claim — that D3FEND is noncommercial — was carried through
two layers of research and into a recommendation before a verification pass caught it. It is
wrong: commercial use is explicitly granted, and the build repository is MIT. The figure came from
a secondary blog. Four version facts were stale by the same route. **Research that arrives with
citations is not research that has been checked**, and licence and version claims are the two
categories where being confidently wrong is most expensive.

## Two defects found on the way

Neither was what the session was looking for; both are real.

- `KNOWN_THREAT_CATEGORIES` is documented as validating nothing, and is used as a title blacklist
  in `domain/proposals/threat_analysis.py` through `_reads_as_a_category`. A hit raises
  `ProposalError`, which is retryable — so a term added to the documentation set silently becomes
  a banned threat title and costs a model retry. DEC-041 added `misinformation`; a threat titled
  "Misinformation" is now rejected and regenerated. One flat set doing two incompatible jobs
  because there is nowhere else to put the rule.
- `unfamiliar_terms` is computed in `context_validation.py` and never returned by the adapter in
  `driver.py`. Only two unit tests read it. Its threat-side twin `unfamiliar_categories` is
  surfaced; the context half is not.

## Also worth knowing

pytm — OWASP, MIT, maintained, released last month — ships threats whose conditions read a
`Controls` object where every field defaults to `False`. An undocumented control is
indistinguishable from an absent one, and a threat fires on documentation silence. That is the
DEC-009 collapse, in shipping software that people use. OCSF has the same shape in one field:
`compliance.status_id` is Pass, Warning, or Fail, with no `unverified`, so a documentation gap has
nowhere to go that is not either an accusation or a lie. Both are better arguments for the way
Trace is built than any restatement of the principle.

On licensing: NIST's OSCAL content is CC0, which makes it the one major control catalog whose text
may be reproduced verbatim — a second `source_frameworks` value with none of the ASVS share-alike
constraint. The CIS Controls are CC BY-NC-ND and the Secure Controls Framework is CC BY-ND with
terms that name AI-generated derivatives as the prohibited use. Both are recorded as excluded so
neither gets re-examined.

## What changed in the repository

`docs/product/future-features.md` gains 5.6 (reusable component taxonomy and applicability
predicates, Research), 5.7 (public-domain requirement sources, Idea), 7.8 (declared cross-object
constraints, Idea), 9.7 (external threat-model corroboration, Idea), three research questions, and
two entries in section 16 recording the graph database and the formal ontology layer as evaluated
and rejected, each with the condition that would reopen it.

Nothing in `src/` changed, which is the right outcome. Every roadmap milestone reads Delivered,
and the WIP limit says new ideas go to future features rather than into implementation. The
interview package's own headline is the LangGraph rejection and a section on what was removed for
adding no value; adopting a graph store at nine hundred objects, in the closing week, with no
measured limitation, would have been the counter-example to that story told in the same document.

## Open next

- The two defects above want issues. Neither is urgent; the blacklist one has a behavioural
  consequence and should be written up with the retry cost stated.
- The husky-ai TM-BOM diff (9.7) is the cheapest thing on this list and the only one that touches
  the single-author truth-set limitation without needing a person.
- #653's remaining truth-set decisions, #565's second annotator, and #353's demo video are
  unchanged by any of this.
- One improvement worth separating from the ontology question entirely: measured work on retry
  feedback suggests enumerating *admissible alternatives* rather than naming the failed field
  carries nearly all of the repair gain. `agent-design.md` section 26 already requires that a retry
  carry validation feedback forward. Making that feedback name the permitted values is a small
  change with external support and no new dependency.
