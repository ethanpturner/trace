# 2026-08-09 — Removing a number nothing could use

Closes #36 as DEC-022. The third question in a row about how context extraction represents
something, and the one where the corpus had already written the answer down as a test.

## Principle 15 decides it

Design principle 15 ends with a decision test: "Does this score help the reviewer make a decision,
or merely make the output look precise? Remove metrics that do not improve judgment."

Applied to `confidence_score`, the answer is available rather than debatable. The field appears
**exactly once in the whole corpus** — `ContextClaim`'s field table — and nothing consumes it. No
threshold reads it, and after DEC-013 none will: that decision made every threshold a deterministic
rule over `satisfaction_status` and `validation_status`, which are categorical values compared by
membership, not by magnitude.

A number no rule can consume and no reviewer can calibrate is precision with no referent.

Keeping it would also have broken the principle it sits under, twice. Principle 15 says avoid
treating confidence as probability — and a decimal from 0 to 1 next to a three-value enum invites
exactly that. It says separate evidence strength from model confidence — and one score conflates
them, since a claim can be confidently inferred from weak evidence or tentatively drawn from strong
evidence, and a single number cannot say which.

## Three orphans in one area

Removing the score is the small part. The interesting thing is what the corpus already had and had
never connected.

Principle 15 demands that evidence strength and model confidence stay separate. The corpus has
**both halves and wired up neither**: `confidence` sits on objects as a categorical enum and means
model confidence, while `EvidenceStrength` was defined in section 4.3 and carried by no field at
all. The M1 research flagged it as vestigial. DEC-013 then relied on the judgment it expresses —
its second condition for `unmet` requires knowing whether a cited reference describes absence
*directly* or *contradicts* a claim of existence — and had to say that in prose, because there was
no field to hold it.

So `EvidenceStrength` moves onto `EvidenceAssessment` as a map from evidence identifier to strength.
Not onto `EvidenceReference`, because **strength is relational rather than intrinsic**: a sentence
describing an identity provider is direct evidence about authentication and contextual evidence
about session handling. A field on the reference would have to pick one and be wrong half the time.

The third orphan: `agent-design.md` section 7 requires inferred claims to carry "a concise
rationale" and `ContextClaim` had nowhere to put one. `reviewer_notes` exists, but that is the
reviewer's field, not the agent's — using it would have meant the agent writing into the human's
column. Added as `rationale`, required when the status is `inferred` or `assumed`.

## A responsibility that finally means something

`agent-design.md` section 8 gives the Context Validation node the job of "enforcing confidence
ranges" without saying what a range is. With two representations in play that was genuinely
ambiguous — check the enum, check the decimal, check they agree?

With the score gone it means one thing: `confidence` is a member of `ConfidenceLevel`. No range, no
consistency check, no arithmetic. A responsibility that was unimplementable because it was
underspecified is now trivial, which is the better kind of resolution.

## What I traded away

Three categories is coarse, and honestly so. A reviewer sorting forty claims by confidence gets
three buckets with no ordering inside `medium`. A score would have *appeared* more useful while
being no more informative, which is the whole of principle 15's argument — but the coarseness is
real and someone will want the resolution.

And I have replaced one unused field with another. `evidence_strengths` is wired to DEC-013's rule,
which is written and unimplemented, so nothing consumes it yet either. The difference is that it has
a named consumer waiting rather than none at all, which is a weaker defence than it sounds.

## Open next

Nine M0 decisions remain, none gating M1. `data-model.md` section 39 is now six of seventeen
resolved.

#34, how reviewer edits are represented, is the closest relative — DEC-017 settled that decisions
are *recorded* without settling how an edit changes the object it edits.
