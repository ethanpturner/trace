# The checkpoint-1 surface reaches all ten actions, and the sixth trigger comes alive

## What changed

The audit's two checkpoint-1 gaps, delivered together. #399: the three reviewer actions that
existed as tested workflow functions but were reachable from no surface — add a missing object,
attach evidence, resolve a contradiction — are now wired into both halves of `trace context
review`: the review file gains `additions:`, per-entry `attach_evidence:`, and a `contradictions:`
section; the flags gain `--attach ID=EVD[,...]` and `--resolve ID=VALUE` with a required
`--rationale`. Both paths call the same functions, so the file-and-flags row-identity property
holds for the new actions the way it held for the old ones. #400: `previous_approved_context`
finds the latest approved revision, and all five `validate_context` call sites pass it, so the
sixth human-review trigger — material change from a prior approved version — fires in the
composed system instead of only when a test hands it `previous=` by hand.

## What the wiring surfaced

Two design questions fell out of making the file idempotent, and both got principled answers
rather than patches.

**A contradicted claim's value is not hand-editable in the file.** The first idempotence test
failed because a stale `editable:` snapshot, re-applied after the contradiction was resolved,
quietly reverted the resolution — the exact silent choice `resolve_contradiction` exists to
prevent, arriving through a different door. The fix removes `value` and `rationale` from a
contradicted claim's editable set: the `contradictions:` section is that claim's resolution path,
and it demands a rationale. The file now has one way to settle a disagreement, and it is the
recorded one.

**An addition naming an existing object is skipped, not duplicated.** The common cause is the same
edited file applied twice; the rare cause — a reviewer adding a namesake of an extracted object —
is a duplicate either way.

The trigger side clarified its own semantics: the comparison runs whenever the repository holds
an approved revision other than the current one, which in practice means the second approval
cycle — approve, revise, approve again — where the package then reports the membership drift
since the prior baseline. A first extraction and a pre-approval re-extraction have no approved
prior, and the trigger correctly stays silent rather than firing against nothing.

## Also found

A populated `.env` at the repo root — which this machine now has — breaks
`test_main_reports_none_when_no_credentials_configured` on a clean checkout. Pre-existing
isolation bug, invisible until a developer configures real credentials; filed as #417 and
deselected from this change's gate. CI is unaffected.

## Open next

The audit backlog's remaining code items are the M11 evaluation set (#403, #404, #405) and the
smaller chores (#401, #402, #406, #407, #408, #409); the doc sweeps are #410 and #411. And with a
real key now configured locally, #324's live ForgeFlow capture is one command away from being
measurable.
