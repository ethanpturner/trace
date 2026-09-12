# What this measures, and what it does not

**Status:** Reference, version 0.1. Every figure on this page is taken from a page in this
directory and carries the denominator that page reports. Nothing here is new measurement; it is the
numbers already published, collected in one place and stated without framing.

This page exists because the figures are scattered across six pages, each written to answer a
narrower question, and a reader who wants to know whether the pipeline works has to assemble them.
Assembling them is the honest thing to do, and the assembled picture is not flattering.

## Accuracy

Pooled over fifteen authoritative clean rows (`scorecard.html`, DEC-143):

| Population | Rows | Matched | Missed | Spurious | Precision | Recall |
|---|---:|---:|---:|---:|---|---|
| Current workflow shape, `openai/gpt-5.1` | 13 | 2 | 10 | 2 | 50% (2/4) | 17% (2/12) |
| Pre-batching, `claude-opus-5` | 1 | 0 | 2 | 4 | 0% (0/4) | 0% (0/2) |
| Pre-batching, unattributed | 1 | 0 | 1 | 4 | 0% (0/4) | 0% (0/1) |
| **All strata pooled** | **15** | **2** | **13** | **10** | **17% (2/12)** | **13% (2/15)** |

The stratification is not a way of preferring the better number. DEC-143 separates the rows because
rows measured on different models and different workflow shapes are different populations, and the
two pre-batching rows carry a diagnosed evidence-validation funnel failure the batched rows do not.
Both the stratified and the pooled figures are reported here for the same reason they are reported
there: neither alone is the whole answer.

Run-to-run, on the three scenarios with a five-run stability protocol (DEC-077): `missing-docs`
has no expected finding to match and was correct 5 of 5 times; `reply-tuner` matched FND-RT-01 in
3 of 5 runs; `unsigned-webhooks` matched FND-UW-01 in 2 of 5.

**What that means, plainly.** Between a half and five sixths of the authored findings are missed,
and the recall varies run to run on the same input. A control that misses most of what it is
looking for is not a primary control, and this one should not be described as one.

## The comparison that makes it concrete

Two agentic code reviewers were run against implementations of two of these same scenarios,
authored from the same truth sets (DEC-156), and scored by the same matcher (DEC-155). Full
figures in [reviewer-arms.md](reviewer-arms.md).

Both reviewers matched the documented weakness in **every completed run** — Mantis 10 of 10, Codex
Security 2 of 2 — against Trace's live recall of 2 of 5 and 3 of 5 on comparable findings. On
systems that have code, a code reviewer finds the documented weakness and this pipeline often does
not.

The comparison is not like-for-like and the page says so: the reviewers read an implementation,
the pipeline reads documentation, and only one of the two scenarios overlaps with a stability run.
It is still the most directly relevant external number the corpus contains, and it goes against the
pipeline.

## Where the pipeline does lead

Rejection breaches — a spurious finding that makes a claim the scenario authors wrote down as one a
correct reviewer declines to make (DEC-154):

| Arm | Current shape | Pre-batching | Pooled |
|---|---|---|---|
| Generic prompt | 8/32 (25%) | 2/15 (13%) | 10/47 (21%) |
| Structured single-pass | 3/32 (9%) | 0/15 (0%) | 3/47 (6%) |
| Whole assessment, one call | 2/32 (6%) | 0/15 (0%) | 2/47 (4%) |
| **Trace** | **2/32 (6%)** | 3/15 (20%) | 5/47 (11%) |

On the current shape the pipeline breaches a quarter of what the generic prompt does and **ties**
the strongest baseline rather than beating it. Pooled, it is worse than two of its three baselines,
because three of its five breaches are in the two pre-batching rows.

The one cell where it leads unambiguously is `common_false_positives`, the mechanism where the
requirements catalog names the wrong conclusion explicitly: **0 of 14 breached, against the generic
prompt's 5 of 14.** That is one mechanism out of six, and it is the narrowest true version of the
abstention claim. The remaining breaches concentrate in `no_evidence`, 4 of 22.

Injected-instruction compliance is 36% across two adversarial scenarios, one captured live and one
authored — see [comparison.md](comparison.md) and `architecture/adversarial-defence.md` for why
that number is confounded by the clean condition's own recall failure, which is filed as its own
issue rather than smoothed over.

## What the corpus bounds

The corpus is synthetic by construction: fictional systems, original architectures, no
employer-derived content ([benchmark-package.md](benchmark-package.md)). That is what makes
publication safe and it means these figures establish behaviour on documentation written for this
purpose, not on the messier documentation real engagements produce.

The code layer compounds it. The two coded scenarios were written by the person who wrote the truth
they are scored against, so a reviewer's score against them is a score against one author's
construction of one small system. `code-notes.md` records the intent before the code so the choice
is inspectable; it does not make the code independent.

Fifteen scenarios is a small n. Percentages over denominators under five are reported as counts for
that reason (DEC-150).

## Why publish this

Because the alternative is that these numbers stay distributed across six pages that each had a
narrower question to answer, and a reader assembles a more favourable picture than the evidence
supports simply by not finishing.

The measurement apparatus is the part of this project that held up. It produced a recall figure its
author did not want, a rejection-breach table where two simpler baselines beat the pipeline, and an
external comparison where two off-the-shelf tools outperformed it on the thing it was built for.
An instrument that only ever confirms is not an instrument. This one did not, and the figures above
are what it returned.

## Sources

- [comparison.md](comparison.md) — the arm-by-arm table and its footnotes
- `scorecard.html` — pooled accuracy by stratum, per-scenario rows, live stability
- [reviewer-arms.md](reviewer-arms.md) — the two external code-review arms
- [exchange.md](exchange.md) — what happened when each tool was fed the other's output
- [self-review.md](self-review.md) — the pipeline and both reviewers turned on this repository
- [benchmark-package.md](benchmark-package.md) — what the corpus is and what it bounds
- `architecture/decision-log.md` — DEC-143 (stratification), DEC-150 (denominators), DEC-154
  (the negative set), DEC-155 (external arms), DEC-156 (the code layer)
