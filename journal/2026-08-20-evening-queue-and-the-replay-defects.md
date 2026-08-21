# The evening queue: two stale premises caught, three deliveries, and the replay promise's real boundary

The sweep closed at midday; the evening worked the queue behind it. Not everything attempted
landed, and the misses taught more than the hits.

## Two forks stopped by their own step zero

The first two deliveries launched — #588's coverage enforcement and #589's conformance check —
were both already delivered by parallel sessions: DEC-134 had landed #588's exact scope with the
field measurement in hand, and DEC-133 had decided #589's boundary and shipped the disjointness
test. The coordinator was working from the previous day's issue-tracker snapshot. Both forks were
stopped before opening PRs, and the delivery protocol gained a mandatory step zero: verify the
issue is open and the scope undelivered before writing a line. The step fired for real an hour
later, when the #591 fork found DEC-110's instrument already finding-form and zero honestly
authorable pairs — it wrote nothing, recorded the no-data-is-not-a-zero-rate distinction on the
issue, and stopped. An issue list is a stale snapshot the moment two sessions deliver from it.

## What landed

- **DEC-140 (#598, PR #634):** `observed_at` on `EvidenceReference`, populated only by
  repository ingestion from committer dates at the pinned history; staleness prefers observation
  over capture age and names its basis per citation. Absence stays absent — a local copy's mtime
  measures the operator's disk, so it records nothing.
- **DEC-141 (#632, PR #635):** the sweep's sharpest defect closed — checkpoint-1 settlements
  (resolved contradictions, answered questions) now travel to the threat, mapping, and
  evidence-validation packages, derived from the authoritative objects the checkpoint actions
  write, fence-neutralized, provenance-labelled, verdict-free. No workflow-version bump: the
  ForgeFlow replay reproduces its pinned hash byte-for-byte under the new shape.
- **The #331 prompt comparison (PR #636):** the section-12 protocol's first real execution —
  pre- vs post-batching evidence validation as one unit, three scenarios, ~$8.10. The finding:
  every v1 arm read coverage 1.0 because run-emergent subject counts stayed under the single-call
  ceiling — so v2's verdict rests on construction (a per-batch guarantee) plus the two recorded
  above-ceiling failures, not on a live regression. First use exercised plumbing that had never
  run and fixed three defects, including a priced flag that was silently ignored.

## What did not land, and what it bought

The #332 model comparison completed zero opus/sonnet arms. Two attempt pairs died to
harness-side process kills — $30.45 against the $40 stop-loss — and the fork stopped rather than
buy a third attempt that could not fit. The attempt record (PR #637) preserves the scored
gpt-5.1 reference arm and sixty-one paid response envelopes as replayable journals, and names
the two defects that are the attempt's real yield: the harness's live path builds its model
bare, journaling nothing (#638 — DEC-139 covers only the CLI path, and #633's stability protocol
runs the same unprotected path); and journal replay diverges at the first post-checkpoint call
on a `call_sha256` miss despite pinned inputs (#639 — suspect: a per-process timestamp entering
the composed request). Until #639 lands, the DEC-139 re-drive promise holds only before
checkpoint 1 — a boundary nobody knew the promise had. The comparison completes from the
preserved journals for the cost of its tails once the fix lands; #332 stays open for exactly
that.

## The day's spend, complete

OpenRouter: ~$27 for the sweep waves plus $8.10 for the prompt comparison, key at ~$55 of $100.
Anthropic: $30.45 for the comparison attempts. Session total ≈ $66 against the ~$63 sweep
authorization plus the separately authorized ~$35–40 comparison envelope — inside both, with the
second envelope buying a diagnosis instead of a table.

## Open next

- #639, then #638, then the #332 completion from journals (~$3–5) — in that order, and #633's
  stability runs only after both.
- #601 scorecard v3: the pooled numbers now visibly need the stratified readout.
- The human items stand: #565's second annotator gates the reconciled-agreement story; #353's
  demo video gates the Stage 6 narrative; both are the operator's to start.
