# Prompt comparison: validate-evidence v1 against v2 (#331)

The first execution of the evaluation plan's section 12 protocol through the harness's
`--label`/`--diff-against` plumbing, on the pair DEC-134 names as this comparison's subject.
Recorded 2026-08-20. The committed feeds live beside this file under
`prompt-comparison/<scenario>/clean/`.

## What the comparison isolates

Pre-batching against post-batching evidence validation, as one unit. `validate-evidence-v1`
rides the single-call shape and `validate-evidence-v2` the batched shape, both selected by the
assessment's pinned `workflow_version` (DEC-134), so prompt text and call shape change together
and no pure prompt-text isolation is claimed. Held fixed across arms: the model
(`openai/gpt-5.1` through the OpenRouter gateway, `openrouter-economy`), the scenarios and
their inputs, the catalog pins, and the harness.

Not fully held fixed: the checkpoint decisions. The v2 arm replays the promoted sweep captures,
which carry their authored reviewer decisions (`defaulted_decisions` 0); the v1 arm runs live
under DEC-077's default policy with recorded answers matched first (each feed states its
defaulted count). Coverage, call shape, cost, and token rows compare cleanly; finding-layer
rows carry this caveat.

## Arms

- **v2** — offline replays of the promoted sweep recordings, label `prompt-v2`, zero spend,
  report hashes verified against the recorded pins.
- **v1** — live runs pinned to the pre-batching shape with `--live-workflow-version 0.1`
  (plumbing added for this comparison; live-only by construction, because a replay's version is
  the recording's fact), label `prompt-v1-live`, diffed against `prompt-v2` as each landed.

Composed template hashes (DEC-019, DEC-094):

- `validate-evidence-v1` — `sha256:c9cbc1df483a43fc81dde07312576f8a4698727b0cb235f5b9d0fd5e9e180199`
- `validate-evidence-v2` — `sha256:e0565fdfa3db7232c48111897a10a2ab824a52eae9cbcbd09619220b45379479`

## Scenario selection

The single call's failure regime is output-ceiling scale (DEC-116: ~310 output tokens per
subject against a 64,000-token ceiling), so the set samples both regimes:

- **missing-docs** — small, the zero-finding DEC-009 path; within the ceiling.
- **crypto-wallet** — mid-size, 156 assessable subjects (~48k output tokens single-call);
  within the ceiling, barely.
- **parcel-platform** — the sweep set's largest architecture, above the single call's ceiling;
  carries the set's matched finding (FND-PP-01).

reply-tuner's v2 baseline feed was staged before the first within-ceiling result motivated
swapping its live arm for parcel-platform's above-ceiling probe; the feed stays committed as
the unbought arm's baseline and no v1 row exists for it.

## Results

| Scenario | Arm | Coverage | Findings (matched/missed/spurious) | Calls | Est. cost | Defaulted |
|---|---|---|---|---|---|---|
| missing-docs | v1 live | 1.0 | 0 / 0 / 0 | 14 | $1.80 | 9 |
| missing-docs | v2 replay | 1.0 | 0 / 0 / 0 | 16 | $2.83 | 0 |
| crypto-wallet | v1 live | 1.0 | 0 / 0 / 1 (fnd-001) | 16 | $2.75 | 34 |
| crypto-wallet | v2 replay | 1.0 | 0 / 0 / 1 (fnd-001) | 25 | $4.87 | 0 |
| parcel-platform | v1 live | 1.0 | 1 (FND-PP-01, by two produced findings) / 1 / 1 (fnd-003) | 22 | $3.52 | 43 |
| parcel-platform | v2 replay | 1.0 | 1 (FND-PP-01) / 1 / 0 | 30 | $7.70 | 0 |

Diff classes (`prompt-v1-live` against `prompt-v2`, DEC-073): missing-docs — clean;
crypto-wallet — spurious `fnd-001` in both arms, nothing regressed, nothing recovered;
parcel-platform — `changed` FND-PP-01 (matched in both arms by different DEC-066 identities),
`missed` FND-PP-02 in both, `new spurious` fnd-003 under v1. The v1 arm also matched FND-PP-01
with two produced findings — a live duplicate pair the DEC-110 instrument's population has been
waiting for, noted for #591.

## Reading

All three v1 runs reached `evidence_assessment_coverage` 1.0 — including parcel-platform,
selected as the above-ceiling probe. The regime was not reached, and the reason is itself a
measurement: subject counts are run-emergent, not scenario-fixed. The v1 live runs minted fewer
approved objects under the default decision policy than the promoted captures carry (143
assessable subjects on parcel-platform against the capture's ~240), and 143 subjects fit the
single call. This comparison therefore did not reproduce the coverage failure live on the
gateway model; the above-ceiling evidence remains the two pre-batching opus captures — coverage
0.275 (husky-ai, 298 subjects) and 25 of 185 mappings (forgeflow) — which no run here
contradicts.

What did differ within the ceiling: v1 spends less where it fits (fewer calls, 27–55% cheaper
per scenario); v1's worst-case request is unbounded (crypto-wallet's evidence call ran as
single ~10-minute requests, the shape that wedged a capture model for two hours in the DEC-135
pilots) where v2 bounds every request at forty subjects; and the finding-layer rows differ only
within the decision-protocol caveat above.

Wall clock is not neutral: crypto-wallet's v1 evidence call ran as single ~10-minute requests,
the shape that wedged a capture model for two hours in the DEC-135 pilots; v2's batches bound
each request.

Section 12's rule is to keep only changes that improve overall performance. **v2 stays**, on
construction rather than on a reproduced failure: per-batch coverage enforcement is a
guarantee, v1's coverage 1.0 here is contingent on run-emergent subject counts staying under a
ceiling nothing controls, and the recorded above-ceiling runs measured what the contingency
costs. The comparison also prices the guarantee where it is not needed — roughly 27–55% more
spend on within-ceiling scenarios — and bounds worst-case request size, which the pilot record
shows is not a theoretical concern.

## Caveats

One run per arm per scenario: no variance is claimed (DEC-077 owns that instrument). The
decision-protocol asymmetry above. And the v1 arm's assessments are experiment scratch — the
feeds are the record; nothing was promoted.
