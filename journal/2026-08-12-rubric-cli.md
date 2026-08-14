# 2026-08-12 — The reviewer rubric reaches the CLI (#334)

M11 opened with nine issues and this session delivered one, chosen by triage rather than by
order. Three of the milestone's issues (#330, #331, #332) need live provider runs and spend
money; three more (#326, #327, #328) are truth-set and recording authorship, which is long
work. The two code-shaped items were #334, the rubric capture surface, and #333, scorecard
history. #334 was the smaller and went first.

## What changed

`trace report rubric <assessment-id> --score CATEGORY=N ...` now exists. `record_rubric()`
had sat in `services/evaluation/report_metrics.py` since #111 with no caller a reviewer could
reach, which meant the evaluation plan's section 9 human rubric could not be recorded without
writing code — exactly the gap #334 named.

Decisions worth recording, none of which needed a new DEC entry:

- **The command lives under `report`, not as a new top-level group.** The rubric scores the
  assessment's report, so `report rubric` reads as what it is, and the DEC-032 top-level
  surface is unchanged. The surface test now pins `report` as `{show, rubric}`.
- **The CLI parses `CATEGORY=N` and nothing else.** Which categories exist, that all seven
  are present, and that scores are one to five stay `record_rubric`'s refusals. Duplicating
  the category list in the CLI would be a second copy that drifts; the service's `ValueError`
  already surfaces as the one-line message the acceptance criteria ask for, because
  `ValueError` is in `EXPECTED_ERRORS`.
- **The rubric attaches to the latest workflow run and refuses when none exists.** It does
  not require a rendered report: the service does not, and gating on one would have coupled
  the capture surface to report rendering for no stated reason. The refusals the CLI does
  own are the malformed pair (`--score report_quality` with no value) and a category scored
  twice, both of which would otherwise be silently absorbed.

## Open next

Eight M11 issues remain. The sensible order: #333 (scorecard history, code-shaped), then the
authorship chain #326 → #327 → #328 (recordings for the outcome-truth scenarios, then the two
threat-seed scenarios, then the missing categories), then #329 (reserved metrics, which wants
the truth sources those scenarios author), and last the live-run trio #330/#331/#332, which
need a decision about spending provider money and are better run deliberately than tacked on.
