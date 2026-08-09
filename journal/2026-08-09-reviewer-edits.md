# 2026-08-09 — Three mechanisms the corpus already had

Closes #34 as DEC-023. Open question 10 asked whether reviewer edits create new object versions or
update the current object with decision history. Both answers were already written down, in places
that had not been read together.

## What settled it

**Section 2.6 says "the MVP does not need full event sourcing."** Immutable objects with
`supersedes_id` chains on everything reviewable is event sourcing in effect, whatever it is called —
every read resolves a chain to a head and every write appends. One sentence already in the model
rules that option out.

**`supersedes_id` exists on exactly two objects.** `ContextClaim` and `Requirement` — and
`Requirement`'s serves catalog versioning across published versions, which is authored rather than
reviewed. If immutable-with-supersedes were the intended edit mechanism, the field would be on every
object a reviewer can touch. It is on one.

**`ReviewerDecision` carries `prior_value` and `updated_value`.** Those fields exist for one purpose:
recording what an edit changed. Under an immutable scheme they would be dead weight, because the
prior value is simply the superseded object.

And section 2.5's wording confirms it: reviewer actions must be recorded "rather than silently
overwriting generated content." The load-bearing word is *silently*. Overwriting is fine when it is
recorded; losing the fact that a human changed something is not.

## Three causes, not one rule

The thing I had been missing is that there are **three different reasons an object changes**, and
the corpus has a mechanism for each — it just never said which was which.

| Cause | Mechanism |
|---|---|
| A reviewer edits | Mutate in place, write a `ReviewerDecision` with the changed fields |
| A node regenerates | The new object carries `supersedes_id` |
| The approved baseline advances | `SystemContext.version` increments |

`supersedes_id` on `ContextClaim` finally has a defined case: **re-extraction**. DEC-017 lists
"request re-extraction" as a reviewer action, and the claims that come back replace the ones they
supersede. The reviewer's *decision to request* it is a `ReviewerDecision`; the claims that *result*
carry `supersedes_id`. One reviewer action, two mechanisms, and they are not in competition.

`SystemContext` earns its version because it is the only object whose whole state is approved as a
unit, and the only one later stages reason from as a baseline. "Analysis was performed against
context version 2" means something. "This claim is at version 3" would just be an edit count.

## The delta, not the snapshot

`prior_value` and `updated_value` hold only the fields that changed.

That is for evaluation. Reviewer edit rate is a primary metric, and "the reviewer changed this
finding" is much weaker than "the reviewer changed its severity and left everything else." A
whole-object snapshot pair pushes that into a diff computed after the fact, over objects whose
schema may since have moved.

The cost is that a decision is only interpretable against the schema in force when it was written.
DEC-020 already refuses to load assessments across incompatible model versions, so the two fail
together — but an old decision genuinely cannot be read in isolation, and that is worse than the
snapshot alternative.

## Reviewer identity, answered because it was in the way

DEC-017 left open where `reviewer_id` comes from under DEC-004, which has no authentication.

A configured local string, defaulting to the OS username, recorded so evaluation can attribute
decisions when more than one person reviews the same benchmark.

It is trivially forgeable and I have written that into the entry, because it sits in a data model
that also records approvals, and a field called `reviewer_id` next to `approved_by` invites being
read as identity. It is not.

## Open next

Eight M0 decisions remain, none gating M1. #35, CLI versus web, is the last one that touches M1's
surface — the corpus contradicts itself four to one and DEC-017 already made the checkpoint
mechanism interface-independent, so it is low-stakes and quick.
