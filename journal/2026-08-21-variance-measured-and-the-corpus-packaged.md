# Variance measured, and the corpus packaged: the stable axis is not inventing

Two deliveries, and the first changed how the second had to be written — which is the right
order for them to have happened in.

## What the stability protocol found (#633, PR #655)

Ten live runs on the model and shape the corpus actually uses: `missing-docs` and `reply-tuner`,
n=5 each, identical inputs, `openrouter-economy`. Zero failed runs, `evidence_assessment_coverage`
1.0 on all ten, ~$28.34.

| Scenario | Expected finding | Unexpected per run | Cost |
|---|---|---|---|
| missing-docs (zero-finding) | none to match — 5/5 correct | 0, 0, 0, 0, 0 | $2.62 ± $0.27 |
| reply-tuner (one finding) | **matched 3 of 5** | 3, 1, 1, 0, 1 | $3.05 ± $0.51 |

**Not inventing findings is stable; producing the right finding is not.** The two runs that missed
FND-RT-01 were healthy — full coverage, ran to completion, simply did not surface it. That is the
project's central claim and its central weakness measured on the same afternoon, and they fall on
opposite sides of the variance question. The precision story gets stronger: not reading silence as
absence reproduced perfectly across five runs on the scenario built to test it. The recall story
gets a caveat it did not have.

The old number — 2 of 5 with three failed runs — was measuring a broken pipeline on a model no
longer used, under the pre-batching shape. It is retained and labelled rather than replaced, and
the scorecard states that rows are listed and never differenced, because a trend between them
would be fiction.

Two figures that read 0.0 are protocol artifacts, verified in code and recorded as such rather
than as model properties: `false_positive_rate` counts reviewer rejections and the default
reviewer rejects nothing; `severity_concordance` compares against a policy that assigns `medium`
uniformly. And a rendering bug the first draft exposed: an empty agreement map means two different
things, so a zero-finding path now reads "no expected finding to match (5/5 correct)" instead of
"no item matched" — which would have published the DEC-009 thesis case as a failure.

## What it licenses, and the issue it created (#653)

The sweep's ten recall misses cannot all be read as lens divergence. `reply-tuner` matched in the
sweep's single run and matches 3 of 5 here, so a single-run match-or-miss is a draw with real
spread in both directions; the individually evidenced lens explanations in the provenance stand,
but separating systematic from noise for any given scenario needs that scenario re-run, not
re-read.

That evidence had no open home. #589 closed on 2026-08-19 with DEC-133 — before the sweep ran —
yet every capture provenance written since says "recorded for the #589 reconciliation". #653 is
the successor, and it inherits the sequencing constraint the variance measurement imposes: decide
what evidence a truth-set edit requires before editing anything, and decide whether the corpus's
recall claims need n>1 per scenario at all, with the cost stated (~$250 for n=5 across fifteen
scenarios; far less for a targeted n=3 on disputed expectations). Editing a truth set to match a
run that could have gone the other way is this project's own failure mode, relocated into the
instrument.

## The corpus as a package (#574, DEC-146, PR #654)

`benchmarks/manifest.yaml` describes the corpus rather than copying it: per scenario, the file
inventory, catalog and workflow pins per condition, model attribution, the offline report-hash
pin, and content-and-path digests that are scenario-relative, so a clone at a different path
verifies and a rename does not. Version is authored, not derived — first stamped 1.0 — because no
digest can tell a re-capture under an unchanged truth set from an edited expectation, and only one
of those breaks comparability with previously reported scores. Measurement records ship alongside
in the specification's "what ships" table but stay out of the manifest, so re-rendering a score
cannot move the corpus digest.

The limitations section is the spine, and #633 sharpened it: single-author truth sets with the
agreement instrument built and empty; recall measured variable and not-inventing measured stable;
**a single-run scenario result is weak evidence about recall in both directions**; the misses
unreconciled under #653; two scenarios still on workflow 0.1; ForgeFlow attributing to no model;
cross-model comparison confounded by decision-replay fidelity. Licensing was verified rather than
assumed — MIT repository, two scenarios seeded from MIT-licensed OWASP material and one from a
cited sample with nothing reproduced, twelve original, and ASVS citation-by-identifier already
machine-enforced against a cached export. The keyless quickstart was verified by stripping every
provider key from the environment and running it.

## Open next

- #653's decisions, which now gate honest truth-set work.
- #648's protection change — the repository owner's hand, and the reason a wrong page rode develop
  for five merges this week.
- #566 and #591 stay gated on a corpus that produces evaluable duplicate pairs; the sweep did not.
- #565's second annotator and #353's demo video remain the two items no automation reaches.
