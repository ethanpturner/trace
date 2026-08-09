# 2026-08-09 — Two classes of identifier, and four things to hash

Closes #21 as DEC-018 and #30 as DEC-019. Taken together because both land in the same M1
foundations issue and both are about how an object is identified and how you know it has not
changed.

## The identifier conflict was a category error

`data-model.md` section 2.1 offered two incompatible schemes in adjacent sentences — nineteen
readable prefixes with sequential examples throughout, and then "UUIDs may be used internally, with
readable prefixes added for debugging and demonstration."

The apparent tension was readability against reproducibility. Sequential identifiers read well in a
report and are order-dependent, so a re-run that produces objects in a different order renumbers
them. If anything held a stored identifier across runs, that would break it.

The tension dissolves once you notice the corpus contains **two different kinds of identifier and
treats them as one**.

`req-AUTH-001` is authored. A person wrote it, the prefix names the object type, the middle segment
names the category, and it is stable across catalog versions. `thr-007` is generated during a run
and means nothing outside its assessment.

The thing that would have needed stable identifiers is the benchmark truth set — and it does not
use generated identifiers at all. It references catalog identifiers, which are authored, and
matches produced objects on requirement and affected component rather than on identity. That was
already settled when the M4 research designed expected-to-actual matching; I just had not connected
it to this question.

With that stated, order-dependence costs nothing and readability wins uncontested. `thr-007` in a
report or a validation error is legible; a UUID is not, and a reader cannot hold one in mind long
enough to match two mentions of it.

## The counter objection was already paid

The standing argument against sequential identifiers is that they need per-assessment state, which
makes minting an identifier a store operation rather than a pure function. That was the concern the
issue raised, and it is real.

It is also already true regardless. Agents return proposal objects that structurally cannot carry an
identifier — `agent-design.md` section 22 forbids an agent minting one, and the proposal models omit
the field. So the application assigns the identifier when it takes ownership, which is a write. A
UUID would avoid the counter read and nothing else.

I spent a while weighing this before noticing the proposal pattern had settled it. That is the third
time this week a decision turned out to have been made by an earlier one — DEC-017 was almost
entirely determined by DEC-016 and DEC-012, and DEC-015's normalization rule fell out of what the
schema already allowed.

## Hashing: one principle, four applications

`content_hash` is required on four objects and DEC-010 left open what computes it. The temptation is
a uniform rule — hash the file bytes — and it is wrong on three of the four.

The principle is: **hash the thing whose change you want to detect.**

- A source document is hashed over **raw bytes**, before normalization, because its hash exists to
  detect that the file changed. Hashing normalized text would mask exactly what it is meant to catch.
- An evidence reference is hashed over **`quoted_text`**, because DEC-015 makes that the verbatim
  excerpt and forbids modifying it.
- A prompt is hashed over the **composed** text, after shared blocks are merged in, because that is
  what the model receives. Hashing the file alone would miss a change to a shared block — which is
  the change most likely to alter behaviour without anyone noticing, since one edit to
  `evidence-policy-v1.md` affects every agent that composes it.
- The catalog is hashed over a **canonical re-serialization**, keys sorted and formatting discarded,
  because a hash that churns on whitespace reports change where there is none, and a hash that
  reports change constantly is one nobody reads.

The single utility matters more than the algorithm. Four call sites hashing four kinds of content
will drift if each is written where it is needed, and the drift is silent — a hash computed
differently still looks like a hash.

## The one I am least comfortable with

Canonical re-serialization means the catalog hash covers what the parser sees. Prose in a YAML
comment is invisible to it.

`requirements/README.md` treats the catalog's prose as meaningful — `rationale` and
`common_false_positives` carry real judgment — and while those are parsed fields rather than
comments, the boundary is thinner than it looks. Someone will eventually put load-bearing guidance
in a comment, and the hash will say nothing changed.

I noted it in the tradeoffs and added a line to the catalog README warning editors, because the
warning belongs where people edit rather than in a decision entry they will not read.

## Open next

Both entries leave questions I could not settle without an implementation. Whether the counter lives
in its own table or is derived from the maximum existing identifier. Whether a rejected proposal
consumes a number. And the one that matters most: when a source document's hash stops matching, what
happens to the evidence references into it — invalidated, re-anchored, or left with their own hashes
still passing. DEC-015 raised the same question from the other side and neither decision answers it.

#23, the persistence layer, is now the last M0 item gating M1 code.
