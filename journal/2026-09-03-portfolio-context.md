# 2026-09-03 — Trace as the first of four

Stage 6's goal is to turn Trace into a credible public career asset. The narrative was written for a
standalone project, and that is no longer what this is.

## What changed outside this repository

DEC-009 — missing documentation is never proof of a vulnerability — turned out to be portable.
Three sibling projects now apply it to other layers, and two of them run:

- **whence**: model supply chain. Per edge, was a lineage relationship asserted by the publisher or
  established by the tool? Model signing attests bytes and says nothing about lineage; AI-BOM
  generators transcribe what a card claims.
- **tearline**: retrieval entitlements. Does an index's per-chunk permission match the source
  system's, and does retrieval respect it? OWASP's RAG guidance prescribes exactly these controls
  and names no tool for any of them.
- **attestrun**: evaluation attestation. Binds a run's inputs and result and re-derives the claim
  offline.

All four carry the same three-valued verdict and none uses a boolean or a confidence score.

## Why this belongs in the interview package rather than only in a README

The obvious objection to story 9 is that a shared vocabulary is a naming convention. The answer is
that it changes what the tools refuse to say, and the sibling projects supply better evidence for
that than Trace can supply about itself.

`whence` emits `unverifiable` on essentially every lineage edge, because cards name a base and stop.
Its namespace check consulted only organizations at first, which would have reported every
user-owned namespace as abandoned — accusing live owners of releasing names they still hold. Its
structural lineage check went through two field sets producing 26% and then 3% false-positive rates
against real published models before measurement narrowed them to zero.

Those are three instances of the same discipline this project started with, caught in a domain where
I had no prior intuition to lean on. That is a stronger argument that the rule is load-bearing than
any number of Trace's own evaluation results, because Trace was designed around it and the others
were not.

## What remains, and what cannot be done here

Stage 6's exit criteria are otherwise met. The one open deliverable is #353, the narrated demo
video, and it is genuinely blocked: the CI-rendered GIF is the committed silent fallback, and the
narration requires a person. Recorded in the roadmap rather than left implied, so the sequence does
not read as though the asset is merely pending.

Story 9 also gives that video better material than it would have had. "Here is a tool" is a weaker
opening than "here is a distinction, here is what it cost to hold, and here are three other places
it turned out to matter."
