# The readout and the reliability pair: what stratifying the scorecard changed, and two bugs the week's own runs wrote the tickets for

Three deliveries closed the measurement arc that began with the sweep: the scorecard learned to
say which numbers may be pooled, and the two reliability defects the week's own live runs
discovered were fixed. A fourth thing happened by accident and mattered as much — a stale page on
develop that nothing was gating.

## The scorecard says what it is now (DEC-143, #601)

Scorecard v3 renders the corpus's numbers stratified by model and workflow shape, reads the two
comparison feeds out with their own caveats carried rather than restated, and states absence
where absence is the honest answer. The split is the point, and it is sharper than the argument
for it was:

| Stratum | Rows | Precision | Recall |
|---|---|---|---|
| `openai/gpt-5.1`, workflow 0.2 (the sweep) | 13 | 40% | 17% |
| `claude-opus-5`, workflow 0.1 (pre-batching) | 1 | 0% | 0% |
| unattributed, workflow 0.1 (forgeflow) | 1 | 0% | 0% |
| mixed pool | 15 | 15% | 13% |

Two of fifteen rows carry eight of the eleven pooled spurious findings. The pooled 15% precision
was not a summary of the pipeline; it was an average across a diagnosed, since-fixed failure
shape and the current one. DEC-143 also records what the page refuses: no intervals, no
reviewer-time synthesis from replayed runs, no bare F1 in the trend matrix, no cache saving until
a feed carries the field. A page that renders what it cannot support is the failure DEC-076's
assembled-not-authored posture exists to prevent.

Forgeflow renders as its own unattributed stratum because its pre-usage-format capture carries no
model attribution — correct under DEC-136, and the argument for finishing the usage backfill.

## Two defects, both written by our own runs

**DEC-144 (#645):** a journal did not carry forward what it served, so a second-generation
re-drive had holes and needed hand consolidation — which is exactly what the #332 completion did
at 2am to get its arms home. Served entries are now copied into the active run's journal at serve
time, keeping the usage the call was bought at while the ledger still reads zero for the replay,
so nothing double-counts. The order-sensitivity half turned out to be a real defect rather than
the contract working: `call_sha256` was always the guarantee and position never was, so the queue
became a non-destructive hash-keyed scan and a passed-over entry no longer poisons everything
behind it. A latent sort bug — entry 100 sorting between 10 and 11 — was fixed on the way, newly
reachable now that journals accumulate across generations.

**DEC-145 (#641):** the orphan class was misdiagnosed in its own issue, and the correction is the
interesting part. The window was not process startup; `resume_assessment` reopened the ledger only
for a *failed* run, so a run resumed from a checkpoint kept `paused` on its row through every
phase while its state file advanced. That is why `trace runs status` reported `paused` for runs
that were visibly executing all through the sweep and the comparison attempts — the runs were
healthy and the status was lying, and the coordinator read those reports as checkpoint pauses more
than once. The row is authoritative for what a run is (DEC-006's persisted object); the state file
records where it was (section 31 routing state, which DEC-016 refused to make a second store). A
disagreement is therefore a stale row, not a competing claim — and repairing it stays an operator
assertion, because before the reopen fix that same combination was what a *live* resumed run
looked like, so automatic recovery could have started a second process against one assessment.
Two further gaps fell out of its tests: repair must refuse a paused row with no state file (that
is prune's), and a repaired strand died at the next checkpoint because `resume_from_review` sat
inside the paused branch despite promising otherwise.

## The page nobody was watching (#647, #648)

The v3 fork stalled on an unexplained mapping-variants staleness. Isolating it against a clean
develop proved it was not the branch's: DEC-141 added settlement content to the mapping package in
#635, and the page — which rebuilds packages from persisted assessments rather than reading feeds
— was last regenerated in #630. Develop carried wrong numbers for five merges. It merged silently
because the four currency checks live in the `scorecard` workflow, which is not the required
status check; only `lint / typecheck / test` gates. #647 regenerated the page, #648 records the
gap and the two things worth deciding rather than assuming (whether a full-sweep job is acceptable
as a merge gate, or the checks should split cheap-from-expensive).

The lesson is the corpus's own: a page that silently drifts is worse than an authored one, because
it still reads as generated truth.

## Open next

- #633's stability protocol, now journal-protected on both paths; needs its spend go-ahead.
- #648's protection change is the repository owner's hand.
- #574's public benchmark package — sequenced last, and the scorecard it would ship with now says
  what it is.
- The human items stand: #565's second annotator, #353's demo video.
