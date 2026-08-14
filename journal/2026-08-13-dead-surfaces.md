# The dead surfaces get their decisions

## What changed

The audit's last two code items, each resolved by decision rather than deletion-by-default.

**#408 — the replay cache goes behind the seam.** `ReplayCache` was a keyed mapping with no
consumers that the README described as "behind the same interface" — a claim about a protocol
the class did not implement. `CachingModel` now implements it: a `StructuredModel` that consults
the cache by the section 30 key and delegates on a miss, recording a successful answer before
returning it and never recording a failure (a cached failure replayed as an answer would make a
transient condition permanent). The README's sentence is now literally true, and the class is
the capture shape #324 needs — run once against a live inner model and the cache fills with
exactly the recordings a later offline replay serves. Persistence stays the capture tool's
question, which is where DEC-020's thinking puts it.

**#409 — the feedback loop gets one real consumer and loses four fake ones.** Recorded as
DEC-086. The context validator's retry instructions now ride into the re-extraction prompt
alongside the reviewer's rationale — re-extraction is the one path on which a generating agent
runs again, so it is the consumer section 8's output list was describing. The four downstream
validators lose their `retry_instructions` surface entirely: no path re-runs their agents, the
transition table has no backward edge, and section 8 only ever specified the context validator —
the other four were symmetry the corpus never asked for. The two analysis error classes stay as
section 26's vocabulary, with docstrings explaining why nothing produces them: the pipeline
expresses those conditions as the Question or observation they resolve to, so there is nothing
left to raise.

## The pattern across both

Each was a surface that existed because building it felt like completing a design, and survived
because nothing exercised it. The resolutions went opposite directions — one wired, one removed —
and the deciding question was the same both times: does a consumer with clear semantics exist?
The cache had one (capture, and the README's own claim); four of the five validator surfaces
could not have one without a routing change nobody has decided.

## Open next

Only the doc sweeps remain from the audit: #410 (README and CLAUDE.md) and #411 (the threat
model), now able to fold in everything this session changed — DEC-083 through DEC-086, the
gitleaks step, and the adapter rework among it.
