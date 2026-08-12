# 2026-08-12 — M12 Decision Debt: the first four

Opened milestone M12 (Decision Debt — the DEC-057..072 features decided in the M0 wave and left
unbuilt) and delivered four of its fifteen issues. Each shipped as its own squash-merged PR to
`develop` (#369–#372), CI green.

## What changed

- **#335 — risk treatment (DEC-060).** `Finding` gains `risk_treatment` (a closed vocabulary,
  section 4.8: `undecided`/`mitigate`/`accept`/`transfer`/`avoid`), `treatment_rationale`, and
  `treatment_review_by`. The reviewer assigns treatment at checkpoint 2 and no node proposes one —
  DEC-030's philosophy applied to the neighbouring judgment. Unlike severity it never blocks
  approval; the one gate is that `accept` without a rationale is refused, by the severity-gate
  mechanism. `assign_risk_treatment` records it as an edit; the CLI gained `--treatment` and its
  rationale/review-by flags.
- **#336 — episodic revisit (DEC-061), and a new decision.** DEC-061 said an expired accepted risk
  re-routes to checkpoint 2 "at the next run" and that the prior `accept` is never reverted
  silently, but left unspecified *how* an already-decided subject re-enters a checkpoint whose
  completion is a decision per subject. I wrote **DEC-079** to decide it: checkpoint completion is
  scoped to the current run (`decided_in_run` — a decision counts if it carries the current run's
  id or none at all, so recorded replays are unaffected). A revisit subject added to the subject
  list re-prompts because its prior-run decision no longer satisfies the checkpoint, and its accept
  stands until a fresh decision. `revisit_due` flags it.
- **#337 — typed routing reasons (DEC-062).** The substrate existed on the context side; I finished
  it on the finding side (`FindingReviewPackage.reasons_by_object_id`, `findings show` rendering)
  and added the `low_confidence` derivation at both checkpoints. `contradicted` and `no_evidence`
  stay deferred until their handling is built, per the module's plan.
- **#338 — STRIDE coverage baseline (DEC-063).** `STRIDE_APPLICABILITY` becomes authored data with
  a conservative `component_type → element kind` classification; an unrecognised type is
  `unclassified` and presented as such. Two warn-only uses in threat validation — coverage gaps and
  plausibility observations — added outside `errors`, so neither blocks nor can be retried against.

## Decisions and reasoning

- **The DEC is the authority, not the issue body.** Two issues cited a DEC whose number did not
  match my milestone-offset guess (#336→DEC-061, #338→DEC-063, #341→DEC-066). Reading the cited DEC
  each time was load-bearing: #336's issue implied "revisit fields" that DEC-061 explicitly does
  *not* add (assumptions carry no date; accepted risk reuses `treatment_review_by`).
- **Run-scoped completion was the minimal core change for revisit.** The alternative — a global
  "any decision ever" rule plus a per-pause re-open marker — needed new state and a second place the
  completion condition is evaluated. Run scoping is one rule in one place, and it was validated
  against the full suite before the revisit logic was layered on, precisely because it touches the
  DEC-005 checkpoint core.
- **Warn-only means structurally warn-only.** #338's coverage and plausibility observations live
  outside `errors` by construction, so `retry_instructions()`/`blocking_errors` cannot include them
  — the quality-over-volume constraint enforced by where the data sits, not by a comment.

## Open next

- **M12 continues at #341** (content fingerprints, DEC-066). `finding_fingerprint`/`normalized_name`
  already exist in `services/evaluation/matching.py` — reuse them so identity cannot drift. The
  finding half is straightforward; the gap half needs a defined `gap → related mapping →
  requirement_id + the threat's component names` resolution (mappings carry no components directly).
  Add `content_fingerprint` (optional) to `Finding` and `DocumentationGap`, set it at persist and
  recompute on identity-field edits, document it in data-model §21/§23, and add the DEC-019 hash
  row.
- Then #339, #340, #342–349 — ten issues.
- A parallel session's uncommitted work is still stashed as `stash@{0}`
  ("parallel-session-uncommitted-M9-work") on `develop`, unrestored.
- PR #281 (roadmap M6–M9) from an earlier session is still open on `feature/roadmap-m6-m9`.
