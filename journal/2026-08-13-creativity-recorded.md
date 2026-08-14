# The creativity column gets its decision, and the effort gets recorded

## What changed

Two audit chores that share section 29. #402: the nodes' creativity assignments had silently
diverged from the corpus — the table said "low to moderate" for critical review and report
generation, the code ran moderate and low respectively, the reasoning lived only in module
docstrings, and `Creativity.LOW_TO_MODERATE` sat unreachable in the seam mapped to an effort
tier nothing used. DEC-085 adopts the split reading (the critic is a search; the report agent is
a restatement), corrects the table, removes the dead enum member and its `xhigh` tier, and fixes
the now-false "one non-low setting in the MVP" claim in the threat node. #401: section 29 says
the creativity-to-effort mapping "is recorded on the ExecutionRecord", and it was recorded
nowhere queryable — the adapter put it on the outcome's metadata and nothing carried it further.
The six agent nodes now copy the call's effort and creativity into the execution metadata, so a
recorded run says what each call actually ran at.

## Why the decision went the way it did

The alternative was restoring the table as written — both agents at `low_to_moderate`, effort
`xhigh`. But the split reading is not an accident to be reverted; it is a position with an
argument: imagining how a conclusion fails benefits from the same breadth as proposing threats,
and restating approved objects takes the conservative reading. The divergence's sin was being
unrecorded, not being wrong. Recording it is the smaller and truer change, and the removal of
the unreachable member makes the seam stop promising an assignment the table no longer makes.
Nothing persists the value anywhere — no recording, profile, or feed — so the removal breaks no
stored data, which is what made it a chore rather than a migration.

## Open next

The remaining audit chores pair naturally: #406 and #407 (test and CI hardening), then #408 and
#409 (the dead surfaces, each needing a decision), then the doc sweeps #410 and #411 — last, so
they fold in everything this session changed.
