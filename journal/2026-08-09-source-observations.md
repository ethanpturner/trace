# 2026-08-09 — One object for two things the corpus asked for and never modelled

Closes #31 and #32 as DEC-021. Taken together because they turned out to be the same problem stated
twice, and answering them separately would have risked two inconsistent answers to one question.

## The same gap, twice

`agent-design.md` section 7 lists "contradiction records or flagged claims" as a Context Extraction
output. No object represents a contradiction. `ContextClaim` has a `contradicted` status with no
field naming what it conflicts with — which is what someone reaches for when they notice the gap and
have nowhere to put the answer.

Section 25 says the workflow "may create a ContextClaim or security event indicating that
injection-like content was detected." There is no security-event object anywhere in the data model,
and section 38's list of eighteen deliberately deferred objects does not mention one. That makes it
an omission rather than a deferral — nobody decided not to have it.

Both are load-bearing. ForgeFlow plants two contradictions and an injection payload, and the
benchmark counts both. The system is required to surface things it cannot currently represent.

## Why neither belongs on ContextClaim

This is categorical rather than a matter of fit.

A context claim asserts something **about the reviewed system**: authentication is delegated, the API
is internet-accessible. Its shape — subject type, subject id, predicate, value — exists for that.

A contradiction asserts something **about the documentation**: these two passages disagree. Forced
into the claim shape, there is no sensible answer to what the subject is, and `value` would have to
carry something that is not a value of anything.

Once stated that way the answer is obvious, and the `contradicted` status stops looking like a
partial solution and starts looking like evidence that someone hit this and worked around it.

## One object, not two

`SourceObservation`, with a `kind` discriminator: `contradiction` and `injection_attempt`.

The two kinds share everything structural. Both reference source passages, both must reach the
reviewer at the context checkpoint, both are counted by the evaluation harness, both come from
context extraction, and neither is a Finding, a Question, or a DocumentationGap. What differs is how
many evidence references are required and whether a Question usually accompanies it — validation
rules, not different objects.

Two near-identical objects would also cut against the model's own instinct. Section 38 defers
eighteen types and section 40 limits the initial set; adding two where one serves is exactly the
expansion those sections resist. And the discriminator leaves room for what comes next — a document
that appears to describe a different system, a section inconsistent with itself — without another
object each time.

`ContextClaim` gains no field. The reference runs one way, observation to claim, so a claim does not
carry a list of things that contradict it and the two cannot disagree about whether they disagree.

## The subtlety the fixture surfaced

ForgeFlow's injection payload sits in what the fiction calls an engineer's repository notes.
Detecting it is a Trace behaviour and produces an observation about a document Trace was given.

But the *existence* of injectable content in repository data is also evidence for THR-001, the
scenario's own "repository prompt injection manipulates AI output" threat about ForgeFlow. One
fixture, two entirely different outputs.

Conflating them would produce a finding about the reviewed system every time Trace reads a document
containing an injection — regardless of whether that system is exposed to one. That is the DEC-009
failure wearing a different hat: concluding something about the system from a property of the paper.
Both the decision entry and `agent-design.md` section 25 now say so explicitly, because the two
readings are close enough that the wrong one looks reasonable.

## What I am least sure about

`summary` is free text, so counting contradictions depends on the extractor producing one
observation per disagreement rather than one per document or one per pair of passages. The benchmark
declares `contradictions: 2`, and nothing enforces the granularity that makes 2 the right answer.

And a discriminated object is a bet that the kinds stay similar. If contradictions later need a
resolution state and injection attempts need a severity, this becomes a union where half the fields
are always null — which is the shape I avoided by not creating two objects, arriving by a slower
route.

## Open next

Ten M0 decisions remain, none gating M1. #36, the confidence model, is the closest relative to these
two — it is the third question about how context extraction represents something — and is small.
