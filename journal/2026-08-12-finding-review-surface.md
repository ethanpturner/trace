# 2026-08-12 — The full finding-review action set reaches the CLI (#351)

M13 closes. `workflow/finding_review.py` implemented eleven reviewer actions and the CLI
exposed four; defer, request-more-analysis, both DEC-051 conversions, the reviewer merge,
reviewer rationale, and remediation guidance had no command, and checkpoint 2 had no file
round-trip while checkpoint 1 did.

## What changed

`services/findings/review_file.py` is the context review file's pattern applied to findings:
derived from the package, an unchanged file applies nothing, and applying a file writes the
same `ReviewerDecision` rows as the equivalent flags because both call the same functions.
`trace findings review --export/--apply` carries it, and `--defer` / `--request-more-analysis`
joined the direct flags. A reachability test now pins the acceptance criterion: every action
in `finding_review.__all__` — minus the checkpoint node and its subject helper, which are the
workflow's — is called from the CLI surface.

The judgments worth recording:

- **A conversion and a decision on one entry are refused, not ordered.** A conversion
  supersedes the finding; a decision after it would judge something no longer under review.
  The context file has no equivalent rule because context objects have no conversions —
  this is the one structural difference between the two formats, and the file says so.
- **Merges apply before everything else**, so a decision lands on the survivor rather than
  on a finding about to be marked a duplicate. The merge entry requires its rationale, per
  DEC-054: a reviewer merge has no matched-feature rule behind it, so the stated reason is
  the whole explanation.
- **`recommendation` in the editable block routes through `add_remediation_guidance`**, not
  a bare edit — the action carries the non-empty rule, and the file should hit the same
  refusals the flags do. `reviewer_rationale` likewise appends through its action.
- **The review package now shows recorded decisions per finding.** A deferral or a request
  for more analysis leaves the finding a subject, and a reviewer returning to it sees what
  was already said — the rendering half of exposing the non-terminal dispositions.
- The package gained an `assessment_id` field of its own: deriving it from the first
  finding's row broke on the zero-finding package, which the CLI smoke test caught.

## Open next

M13 is done. What remains across the project: the live-run batch (#324, #330, #331, #332 —
provider spend, awaiting authorization) and the M9 demo materials (#354 and #355 startable
offline; #353's narration needs a person; #356 depends on the others).
