# 2026-08-09 — Costing the pipeline, and correcting DEC-014

Answers the first open question on DEC-014: what a ForgeFlow assessment costs, and whether it
changes the model tier. It does not change the tier. It does correct two things I wrote in DEC-014
a few hours earlier.

## The answer

**$2.25 to $5.97 per assessment on `claude-opus-5`.** A twelve-scenario benchmark sweep is $27 to
$72. The range is wide because one assumption dominates, and it is the one I guessed at rather than
measured.

`scripts/estimate_cost.py` models the pipeline from the corpus: six model-assisted agents, ten
expected threats from `forgeflow-scenario.md` section 18, mapping running per threat, evidence
validation and critique over bounded groups. That comes to **28 model calls** per assessment.

## What the sweep showed, which was not what I expected

I was careful about the characters-per-token ratio — swept it 3.2 to 4.4, reasoned about the Opus
4.7 tokenizer producing more tokens for the same text, treated it as the main uncertainty.

It barely matters. Across that whole range, cost moves by about 8%.

The variable that actually drives cost is **adaptive thinking depth**, which I picked three numbers
for with much less care. Between 800 and 6000 thinking tokens per call, cost moves 2.6×. The
assumption I interrogated turned out to be nearly irrelevant and the one I waved at turned out to be
the answer.

That is worth remembering as a habit: sweeping the parameter you are unsure of is not the same as
sweeping the parameter that matters, and you find out which is which by sweeping both.

## Two corrections to DEC-014

**Prompt caching saves about 12%, not the large fraction I implied.**

DEC-014 argued that the capability-aware seam mattered — rather than a lowest-common-denominator
one — because prompt caching "is what makes the catalog-as-stable-prefix shape affordable across
repeated benchmark runs." The number is $3.95 to $3.47 at midpoint assumptions. Real, worth having,
not load-bearing.

The reason is that **thinking tokens are billed as output, and output is about 85% of the cost**.
Caching only touches input. I knew both facts when I wrote DEC-014 and did not put them together.

The decision itself still stands: a capability-aware seam is right, and an intersection-only seam
would still be worse. But the argument I gave for it was overweighted, and the honest version is
that caching is a modest saving rather than the thing that makes the shape affordable.

**Effort level is the cost lever.** Ahead of model tier, and well ahead of caching. That is a more
useful thing to know than the total, because it is the knob that actually exists.

## The corpus's own example limits were wrong in both directions

`data-model.md` section 6 set `maximum_model_calls: 25` and `maximum_cost: 5.00` as examples.

The estimate predicts 28 calls, so the call limit would have **halted the pipeline before it
finished** — and it would have looked like a runaway-loop trip rather than a limit set too low.

The cost limit held at low thinking and was exceeded at high: $5.97 against a $5.00 ceiling. So an
assessment run at effort `high` would stop partway through on cost, for the same reason.

Both are raised, with a note recording why and stating that they are examples rather than targets.
Being examples is exactly why they were worth fixing: the first implementer to need a number will
take the one that is written down.

## Does it change the tier

No. Sonnet 5 would roughly halve the cost, and DEC-014's reasoning still applies — the project's
central claim is analysis quality, and a cheaper model weakens the strongest reading of the
evaluation results. At $27 to $72 for a full sweep, the tier is not the constraint.

If cost does become a problem, the order to reach for levers is now clear: lower effort first,
then consider Haiku for mechanical steps, and only then reconsider the primary tier.

## What this estimate is not

It is not a measurement. There is no product code to instrument and no provider credential
configured, so there was no `count_tokens` call available either — the `.env` has an
`ANTHROPIC_API_KEY` line with a blank value, which `Settings` correctly reports as unset.

Every number rests on a stated constant in the script, and the pipeline shape rests on my reading
of `agent-design.md` rather than on anything that has run. The call count in particular assumes one
context-extraction call, one threat-analysis call, and bounded groups sized by guess — all three are
folded sub-decisions in open issues.

It should be re-run against real `ExecutionRecord` data once the pipeline runs. The script exists so
that is a re-run rather than a rebuild.

## Open next

The remaining M0 decisions are narrower than the five that gated M1 and M2. #34 (reviewer edit
representation) and #35 (CLI versus web) are the two closest to what is already settled.

M1 implementation is unblocked and would be the first product code in the repository.
