# Run-to-run stability on the sweep model (#633)

DEC-077's protocol re-run on the model and workflow shape the corpus actually uses: `openai/gpt-5.1`
through the OpenRouter gateway (`openrouter-economy`, DEC-135) under the batched evidence-validation
shape (workflow 0.2, DEC-134). Two scenarios, five live runs each, recorded 2026-08-21. The
committed summaries are in `live-stability.json`; the per-run feeds are keyed by scenario under the
results tree.

## What was measured, and why these two scenarios

Ten live runs, identical inputs, the same catalog and registry pins, one variable: model
nondeterminism. The pair was chosen to test the two answers the pipeline can be right about.

- **`missing-docs`** is a zero-finding path. Being right means producing no finding — the DEC-009
  thesis case.
- **`reply-tuner`** is the corpus's one live matched finding. Being right means producing one
  specific finding, FND-RT-01.

Stability of the first without the second would be a tool that reliably says nothing. The point of
running both is that they can disagree, and they did.

## Results

| Scenario | Completed | Failed | Defaulted decisions | Expected finding | Spurious per run | Coverage |
|---|---|---|---|---|---|---|
| `missing-docs` | 5 | 0 | 55 | none expected | 0, 0, 0, 0, 0 | 1.0 every run |
| `reply-tuner` | 5 | 0 | 134 | **FND-RT-01 in 3 of 5** | 3, 1, 1, 0, 1 | 1.0 every run |

| Scenario | Cost mean | Cost range | Runtime mean | Model calls |
|---|---|---|---|---|
| `missing-docs` | $2.62 ± $0.27 | $2.26 – $3.01 | 2923 s ± 428 | 16.0 ± 1.3 |
| `reply-tuner` | $3.05 ± $0.51 | $2.45 – $3.94 | 2762 s ± 494 | 17.0 ± 1.8 |

These runs also recorded `documentation_gap_precision` — `missing-docs` at 0.079 ± 0.064 across
the five. DEC-147 has since retired that metric: its denominator was produced gaps, which read the
expected-gap file as an exhaustive enumeration it never was, so the figure measured how much the
document set is silent about rather than anything about the run. The runs' recorded values stay in
the committed feeds as what they were; they are not restated here as a finding about stability,
and the wobble originally read as gap-precision variance is variance in produced gap volume.

Zero runs failed. Every run read `evidence_assessment_coverage` 1.0, so nothing here is the
pre-batching funnel failure recurring; DEC-134's guarantee reproduced ten times out of ten.

## What is stable and what is not

**Not inventing findings is stable.** `missing-docs` produced zero spurious findings in all five
runs, under a reviewer that rejects nothing. The project's headline claim — that the pipeline does
not read silence as a weakness — reproduced without exception.

**Producing the right finding is not.** `reply-tuner` reproduced its expected finding three times in
five, with no failed runs and full coverage in all five. The two runs that missed it were healthy
runs that reached the end and did not surface it. Alongside that, the number of unexpected findings
proposed varied from zero to three across the same five runs.

So recall is the unstable axis and not-inventing is the stable one. That is the useful shape: the
variance sits where the corpus already had its weakness, not where it had its claim.

## What this licenses about the sweep's ten recall misses

**It does not license treating every one of those misses as a property of the pipeline's lens.**
`reply-tuner` matched its expected finding in the #484 sweep's single run and matches in only three
of five here. A single-run match or miss is therefore a draw from a distribution with substantial
spread, in both directions: a scenario recorded as missed may match on a re-run, and one recorded as
matched may miss.

Any reconciliation of the sweep's recall record — #589's subject, and #653's — has to carry that
caveat. The lens explanations the sweep recorded (a finding surfacing as questions or gaps, the
DEC-066 component-name split) remain real and are individually evidenced in the provenance; what
this measurement forbids is inferring, from one run per scenario, that a miss was systematic rather
than a draw. Distinguishing the two for any given scenario needs that scenario re-run n times, not
re-read.

**The honest confound, stated rather than buried:** these runs use DEC-077's default reviewer
(approve as generated, uniform severity), while the sweep's runs used authored checkpoint decisions.
The conditions are not identical, and the defaulted counts here are high — 55 and 134 decisions
across five runs each — because fingerprint replay matched few of the recorded decisions. The
variance measured here nevertheless arises upstream of checkpoint 2, in what the model proposes, and
that source is present in the sweep runs too. The caveat stands; its exact magnitude under authored
decisions is unmeasured.

## Two figures that are protocol artifacts, not model properties

Both are zero for reasons of construction, and neither says anything about the model.

- **`false_positive_rate` is 0.0 in every run.** The metric counts rejected candidates over proposed
  findings — the reviewer is the judge — and DEC-077's default reviewer rejects nothing. The honest
  precision signal in these runs is the spurious count in the table above, not this rate.
- **`severity_concordance` is 0.0 in every `reply-tuner` run.** The default policy assigns `medium`
  uniformly, deliberately, so that severity judgment contributes no variance; `reply-tuner`'s
  expected severity is high. The zero is the policy working as designed.

## Relation to the prior measurement

The standing figure before this one was five `claude-opus-5` runs of `unsigned-webhooks` on
`primary-development`, FND-UW-01 in two of five with three further attempts failing
(`live-stability.json`, retained). It is **superseded, not compared**: a different model, a different
workflow shape, and a different scenario. It is not a baseline for these numbers and no trend is
claimed across them — the scorecard lists the rows and never differences them. Its three failed
attempts are worth one note on their own: this protocol had zero, which is a harness result rather
than a model one.

## Spend

Ten live runs, ~$28 total on the gateway: `missing-docs` five runs at $2.62 mean, `reply-tuner` five
at $3.05 mean. No run was re-bought — the harness journal (#638) was live on this path for the first
time and no kill occurred that needed it.
