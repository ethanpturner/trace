# 2026-08-14 — The demo catches up with its own recording (#428)

A three-agent survey of the demonstration surfaces, the demo content, and the project's own
recorded debt, run ahead of the presentation, found one urgent thing: the live capture (#324)
made the flagship recording genuinely impressive — and left every demo surface either broken
against it or hiding what it contains.

The tape decided one finding where the live run produces five, so `findings approve`, the
following `resume`, and `report show` all failed on camera — and the CI smoke stayed green,
because the epilogue asserted only `trace verify`, which counts a missing report as "no
manifest yet" success. The committed GIF still showed the pre-capture run. The demo script
cited eight deleted recording paths and narrated "one provisional finding, not a wall of
them." The three evaluation pages predated the capture, and the scorecard disagreed with the
history file about the same scenario. Meanwhile the recording's best content — the injection
detection, the two contradiction observations, the DEC-009 rejection of fnd-003 — appeared
nowhere a viewer would see it.

The findings became four issues (#428 correctness, #429 observation visibility, #430 report
content, #431 polish and Stage 6 assets), and this session delivers #428:

- The tape's checkpoint-2 beats mirror `decisions-findings.yaml` — four approvals with their
  severities, and the fnd-003 rejection as its own narrated beat, because the rejection is
  the thesis exercised at the product's own checkpoint.
- The smoke epilogue writes its marker only when the rendered report exists *and* the chain
  verifies. The old gate is worth remembering: a verification command whose success string
  covers the missing-artifact case ("no manifest yet") cannot gate that artifact's existence.
- The demo script is rewritten against the live recording — segmented paths, the 131-subject
  checkpoint, the five-finding beat, and a beat 10 that presents the honest miss (0/3 truth
  matches, four defensible spurious findings) as the measured number it is. The dry run of
  every scripted command against a fresh replay now completes end to end.
- The evaluation pages regenerate at the capture date with a DEC-081 snapshot, resolving the
  scorecard/history disagreement.
- The stale "the demonstration surface does not exist" prose in README and CLAUDE.md is
  corrected — the second time this class of rot has been swept this week, which strengthens
  the doc-sweep journal's case for auditing it continuously.

## Open next

#429 (contradictions and `--observations` at checkpoint 1, plus the adversarial beat), #430
(report §7 threats and question quality, one hash re-pin), #431 (view and scorecard polish,
architecture image, screenshots), then one GIF render after the last tape edit.

## Addendum — the full push (#429, #430, #431)

The remaining three issues landed the same day.

**#429** put the differentiators on camera: `trace context show` now prints the contradictions
block beside the injection attempts — the `--resolve-contradiction` action was unreachable
while nothing printed the observation it acts on — and `--observations` gives the demo a
one-screenful beat: the live model's full injection narrative naming the four poisoned claims,
and both planted contradictions. The tape gained that beat and the adversarial evaluation
(five payload classes resisted, compliance zero, offline).

**#430 (DEC-083)** fixed the report's two visible defects, and taught a compatibility rule
worth the detour: section 7's threat filter was never satisfiable (nothing approves threats),
so the section now renders the threats the approved findings rest on. The question dedupe was
first implemented at consolidation and was rejected by the recording itself — renumbering
questions invalidated the recorded report response, whose authentic prose enumerates
qst-001..026 — so byte-identical asks collapse at render instead, the duplicate identifier
riding its survivor's line. Derived-output changes are re-pin cycles; allocation changes are
re-capture events.

**#431** polished what the audience sees: the evaluation view is no longer a dead end, the
lineage walk is one click from the navigation with an index page, raw Python values left the
tables, `serve()` prints the deep links a presenter would otherwise type live, the scorecard
finally uses its own good/bad colors with the flagship's honest rows footnoted on the page,
the replay narrates its stages, and the architecture image (#354) exists — a hand-authored
SVG whose phase names are pinned to `workflow/phases.py` by a test. Committed view
screenshots stay with the presenter's rehearsal: the polished view now prints its own URLs,
and the GIF remains the terminal-screenshot source.

One process lesson repeated twice today: compound shell commands with relative `cd` and
branch switches scattered work onto wrong branches and even onto local develop once —
recovered by `git reset --hard origin/develop`, nothing lost, but absolute paths and
single-purpose commands are the rule this session re-earned.
