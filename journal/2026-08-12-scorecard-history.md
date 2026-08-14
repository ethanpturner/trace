# 2026-08-12 — Scorecard history (#333, DEC-081)

Second M11 delivery of the day, continuing the order the morning session set: the code-shaped
items first. The scorecard was a single static table regenerated in place — the numbers of the
current tree, with no record of how they moved across prompt, catalog, or code versions, which
evaluation-plan sections 16 and 17 both ask for.

## What changed

`docs/eval/history.jsonl` is a committed, append-only record of scorecard builds, and the page
now renders the retained history below the current table. `build_scorecard.py --snapshot
YYYY-MM-DD` is the deliberate step that retains one; a plain build reads the history and never
writes it. The first snapshot is committed with this change, keyed `654664d` — the develop tip
the sweep ran on.

The design turned on one constraint: the scorecard is deterministic and drift-checked (DEC-076).
Anything that stamped the current git ref onto the page at build time would change the page on
every commit and reduce the CI check to noise. So history is *retained*, not derived: written
only by the explicit flag, keyed by git ref, a path-keyed digest over the prompt tree, and the
catalog version, and the page renders from the committed file — regeneration stays reproducible.
Appending a snapshot with the same key as the last is refused, which is what guarantees any two
retained records are distinguishable. All of that is DEC-081; the corpus wanted the outcome
("metrics viewable across versions") and was silent on mechanism, so the mechanism got a
decision entry rather than an improvisation.

Two smaller judgements:

- **The prompt identifier is a file-tree digest, not a DEC-019 composed hash.** Composition
  needs per-agent substitutions a version key should not depend on; hashing every file under
  `prompts/` moves on any edit that could move any composed hash, which is the property needed.
- **The pooled history line covers authoritative rows only.** Baselines and ablations are
  retained in the snapshot's rows but stay out of the headline numbers — the history tracks the
  pipeline, and DEC-012 already marks those runs non-authoritative.

The DEC-076 content boundary applies to the history file unchanged: metrics and identifiers
only, since the file is committed to a public repository.

## Open next

Seven M11 issues remain, unchanged in shape from the morning entry: the authorship chain
#326 → #327 → #328, then #329 (reserved metrics), then the live-run trio #330/#331/#332, which
spend provider money and want a deliberate session. The snapshot step is manual by design;
when a release checklist exists, `--snapshot` belongs on it.
