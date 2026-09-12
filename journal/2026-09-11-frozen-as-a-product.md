# Frozen as a product

Two measurements decided this, and the fact that both are already published in this repository is
the only reason the decision was available to make.

The first is accuracy. Pooled across fifteen authoritative rows the pipeline reaches 17% precision
and 13% recall. Stratified to the current workflow shape, where the argument for the better number
is legitimate and made in DEC-143, it reaches 50% and 17%. Live per-scenario recall is 2 of 5 and
3 of 5, which means the run-to-run variance on one input is wider than the difference between
several design generations. A control that misses most of what it looks for is not a primary
control. Nobody had written that sentence down until today, and everything in the roadmap past this
point assumed otherwise.

The second is the comparison that landed this week. Two agentic code reviewers, run against
implementations of two of this corpus's own scenarios, scored by this corpus's own matcher, matched
the documented weakness in 12 of 12 completed runs. That is the number that actually settles it.
The pipeline's premise is that a system existing only as documentation cannot be reviewed by
reading code. That premise is true and much narrower than the design assumed, because most systems
worth reviewing have code, and on those an off-the-shelf tool outperforms this one at the job.

What survives is the part I did not set out to build. The apparatus produced a recall figure I did
not want, a rejection-breach table where two simpler baselines beat the pipeline pooled, and an
external comparison that went against it. It also caught three of this project's own checks that
could not fail — a report section filtering on a status nothing set, a compliance rate scored
against recordings nobody ran, a fence whose coverage claim was true of one path and silent about
another. An instrument that only ever confirms is not an instrument. This one did not confirm, and
the honest response is to keep running it rather than to keep improving the thing it measures.

So: the harness continues, the corpus continues, measurement continues, and fixes that keep a
replay honest continue. New capability stops. `docket` — the disposition recorder — takes four
mechanisms from here by reimplementation, and the striking thing is that three of them were built
this week for a different reason. DEC-157, DEC-158 and DEC-160 all exist because a code reviewer's
report was fed in as a source document and the fabrications it carried reached a rendered report
through approved context. Registering a third-party report as what it is, blocking any subject that
rests on it alone until someone writes down why, and keeping its text out of the trusted region are
not incidental hardening. They are the core mechanic of recording a disposition for an inbound
finding, and they were finished before the job had a name.

The uncomfortable part of the freeze is the reading it gives a visitor. Someone arriving at a
pipeline that runs end to end, with six agents, fourteen phases, two structural checkpoints and a
CI-checked scorecard, will find a decision at the top saying this is not the product. That is the
correct reading and `docs/eval/what-this-measures.md` is where it is made legible instead of buried
across six pages that each had a narrower question to answer. A reader who stops halfway through
those pages assembles a more favourable picture than the evidence supports, purely by not
finishing. Collecting the numbers in one place removes that.
