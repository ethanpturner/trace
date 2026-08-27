# The Trace benchmark package

*Package `trace-benchmark-corpus`, version 1.0. Specification for DEC-146 (#574).*

## What this is

Fifteen security-architecture assessment scenarios, each with the material a reviewer would be
given, an authored truth set stating what a competent review should conclude, a recorded set of
model responses that replays the whole pipeline offline, and three one-call baselines captured
against the same inputs. The corpus is the measurement substrate behind every number in
`docs/eval/`: the scorecard, the comparison table, the ablation study, and the adversarial
condition all read it.

`benchmarks/manifest.yaml` describes the package — every scenario, the files it carries, the
versions it pins, the models its recordings attribute to, and a digest over each group of files.
The manifest is generated from the corpus and checked in CI, so it describes what is actually
present rather than what someone remembered writing.

Nothing in the package requires a provider key. The recordings are the point: a consumer replays
the committed responses and reproduces the committed scores without spending anything or holding
credentials.

### What ships alongside

The corpus is the substrate; the measurements taken from it are separate artifacts, and anyone
evaluating the corpus should read them rather than the scores alone:

| Artifact | What it holds |
|---|---|
| [`scorecard.html`](scorecard.html) | Per-scenario results, pooled by stratum rather than across models and workflow shapes (DEC-143). |
| [`comparison.md`](comparison.md) | The pipeline against the three one-call baselines, live against live. |
| [`ablation.md`](ablation.md) | Each component removed in turn, with the ablated runs marked non-authoritative. |
| [`stability-633.md`](stability-633.md) | Run-to-run variance: two scenarios, five live runs each, on the model the corpus uses. |
| [`prompt-comparison-331.md`](prompt-comparison-331.md) | The evidence-validation prompt pair, pre- and post-batching. |
| [`model-comparison.md`](model-comparison.md) | Three model profiles, cost beside quality, with its confound stated. |

These are deliberately **not** in the manifest, and the boundary is the point. The manifest
establishes which corpus you hold, so re-rendering a score must not move the corpus digest. The
corpus and the numbers measured from it change on different cadences, and covering both would make
the digest answer a question nobody asked of it.

## Version, and what it promises

The package version is `MAJOR.MINOR` and is authored rather than generated, because only a person
can say whether a change leaves previously reported numbers comparable.

- **MAJOR** changes when previously reported scores stop being comparable: a truth set's
  expectations change, a scenario leaves the corpus, or the identity rule the matcher scores on
  moves.
- **MINOR** changes when the corpus grows or its provenance improves without disturbing what a
  score means: a scenario is added, a recording is re-captured under an unchanged truth set, a
  baseline is added.

What a version promises a consumer:

- The files are the files the manifest names, at the digests it records.
- Replaying the committed recordings offline reproduces the scores committed against that same
  package version.

What it does not promise, and these are the important half:

- **Not that a live run reproduces those scores.** The pipeline is model-assisted and the models
  are nondeterministic. See Limitations.
- **Not that the truth sets are objectively correct.** They are one author's judgment about what a
  competent review should conclude. See Limitations.
- **Not comparability across MAJOR versions.** A number reported against 1.x and a number reported
  against 2.x are two different measurements.

## Run it yourself

No API key, no network, no provider account.

```bash
uv sync                              # install from the committed lockfile
uv run trace evaluate --all          # replay every scenario against its truth set
uv run trace evaluate missing-docs   # one scenario
uv run python scripts/replay_forgeflow.py   # the whole pipeline, hash-checked
```

`trace evaluate` replays the recorded responses through the real pipeline — the same nodes, the
same validation, the same two checkpoints answered from each scenario's committed decision files —
and scores the result against `expected/`. Each run writes a metric feed under
`benchmarks/results/` (derived, gitignored).

To drive the pipeline directly rather than through the harness, `--model-profile offline-fake
--response <recording>` runs it against a recorded response set with no provider behind the seam.

The keyless claim is verified rather than asserted: the replay above was run with
`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, and `OPENAI_API_KEY` removed from the environment.

## What the corpus contains

Each scenario exercises one coverage category. Directory layout is uniform: `input/` is what Trace
is given, `expected/` is the truth set and is never supplied to the pipeline, `recorded/` holds the
response envelopes plus the checkpoint decision files and the report-hash pins, and
`recorded/baselines/` holds the three one-call baselines.

| Scenario | Category | What it measures |
|---|---|---|
| forgeflow | baseline | The demo system, and the corpus's widest truth set: the scenario the narrative and the walkthrough use. |
| husky-ai | ai-service-risks | An ML image classifier, seeded from an externally authored threat model. |
| crypto-wallet | third-party-integrations | The hedged-statement path: documentation that gestures at a control without establishing it. |
| invoice-agent | ai-service-risks | The first scenario whose subject is itself an LLM agent. |
| unsigned-webhooks | genuine-missing-controls | A documented-absent signature check — the finding-versus-gap boundary from the documented-negative side. Also carries the adversarial condition. |
| contradictory-docs | contradictory-documentation | Two supplied documents that disagree about retention: contradiction handling. |
| oidc-portal | delegated-authentication | Delegated OpenID Connect: the local-password-policy false-positive class. |
| managed-db-service | managed-platform-controls | Inherited platform encryption: the encryption-detail false-positive class. |
| missing-docs | missing-documentation | A system description that establishes almost nothing about protections. Silence must resolve to gaps and questions, never to a finding (DEC-009). |
| rag-support-bot | ai-system-retrieval | A shared retrieval index selecting passages by relevance alone. Also carries the adversarial condition. |
| reply-tuner | fine-tuning | Fine-tuning on collected customer content, with a governed write path whose suppressed conclusion is the pack's false-positive class. |
| order-notifier | duplicate-threats | Two documents describing the same unsigned callback: whether the same conclusion drawn twice is merged. |
| translation-gateway | third-party-integrations | Ticket bodies sent to an external translation service with no retention agreement. |
| parcel-platform | large-architecture-input | Four zones, eighteen components, six actors: size in the context rather than in the finding count. |
| nightly-reconciler | organizational-control-inheritance | Controls provided organizationally rather than by the system, asserted through an org-controls catalog. |

Two scenarios carry an **adversarial condition** (DEC-075): a poisoned input document carrying
prompt-injection payloads, with its own truth set and its own recording under
`conditions/adversarial/`. The clean and adversarial recordings pin their workflow versions
independently.

Per-scenario catalog pins, workflow pins, model attribution, file counts, and digests are in
`benchmarks/manifest.yaml`. They are not restated here, because a second copy would drift.

## How it was built

Scenario inputs are fictional systems. Three scenarios were seeded from externally authored threat
models so their truth sets arrive independently written rather than invented alongside the inputs;
the rest are original small architectures, each built to exercise one catalog mechanism cleanly.

Truth sets are authored before the recordings exist and are never supplied to the pipeline. Each
states the findings a competent review should reach, the documentation gaps it should open, the
questions it should ask, and — importantly — the conclusions it should *reject* as false positives.

Recordings are live captures. Every response envelope in the corpus came from a real provider call
against the real inputs: ForgeFlow and husky-ai on `claude-opus-5`, the other thirteen on
`openai/gpt-5.1` through an OpenRouter gateway. The recordings are promoted only after the replay
round-trip verifies, and each scenario's `recorded/provenance.md` states what was captured, when,
on what model, and at what cost.

## Limitations

This section is the point of the package, not a disclaimer attached to it. A benchmark that
oversells what it establishes is worse than no benchmark, because a reader takes the numbers at
face value.

**The truth sets are one person's judgment.** Every score is measured against expectations a single
author wrote. The instrument for measuring inter-annotator agreement is built (DEC-112) and holds
no data, because no independent second annotation pass has been authored (#565). Until one exists,
"precision 40%" means "40% against this author's reading", and the reading itself is unvalidated.

**The corpus has measured what that costs, and the number is large.**
[`authored-versus-live.md`](authored-versus-live.md) pools the retained 2026-08-18 snapshot, whose
recordings were written offline, beside the current corpus, whose recordings are live captures —
same truth sets, same matcher, same scenarios. The first reads 78% precision and 82% recall; the
second reads 17% and 13%. Recordings written to exercise a truth set score well against it, which
is the property they were built for and not a measurement of the pipeline. The gap is the size of
that error, and it is the most useful thing this corpus knows about itself (DEC-153).

**Recall varies from run to run; not-inventing is the measured-stable axis.** DEC-077's protocol
was re-run on the model and call shape the corpus actually uses — `openai/gpt-5.1` through the
gateway under workflow 0.2, two scenarios, five runs each, identical inputs
(`docs/eval/stability-633.md`). Ten runs, none failed, `evidence_assessment_coverage` 1.0 every
time. `missing-docs`, the zero-finding path, produced **zero spurious findings in all five runs**.
`reply-tuner` reproduced its one expected finding in **three of five**, and the two runs that
missed it were healthy runs that reached the end with full coverage and simply did not surface it;
the number of unexpected findings proposed varied from zero to three across the same five runs.
The pipeline is therefore stable where its headline claim lives — it does not read silence as a
weakness — and variable on recall.

The earlier measurement, five `claude-opus-5` runs of `unsigned-webhooks` with the expected finding
in two of five and three attempts failing (`live-stability.json`), is retained and **superseded,
not compared**: a different model, a different workflow shape, and a different scenario. No trend
is claimed between the two, and the scorecard lists stability rows rather than differencing them.

**A single-run scenario result is weak evidence about recall.** Every committed metric feed comes
from one replay. The replay itself is deterministic — the same recording produces the same score —
but that recording is one draw from a distribution with measured spread in both directions: a
scenario recorded as missing its expected finding may match on a re-run, and one recorded as
matching may miss. Reading any single scenario's recall result as a property of the pipeline is
reading one sample as a summary.

**The recall misses are not settled facts.** The sweep's captures missed expected findings on
several scenarios. The lens explanations recorded in the provenance — a finding surfacing as
questions or gaps, the DEC-066 component-name split — are real and individually evidenced, but the
stability measurement forbids inferring from one run per scenario that any given miss was
systematic rather than a draw. Separating the two for a particular scenario requires re-running it,
not re-reading it, and the reconciliation is open as #653.

**Two scenarios' recordings predate the batched evidence-validation shape.** ForgeFlow and husky-ai
carry workflow version 0.1, where evidence validation made a single call that could silently
under-assess; the other thirteen carry 0.2. Their numbers are not directly comparable to the rest,
which is why the scorecard renders strata rather than one pooled figure (DEC-143).

**ForgeFlow's recording attributes to no model.** It was captured before the usage format carried
model attribution, so DEC-136 renders it unattributed rather than inventing a name. The manifest
shows this as an empty `models` list.

**Cross-model comparison is confounded.** `docs/eval/model-comparison.md` records the measured
confound: replaying one model's recorded checkpoint decisions against a different model defaults a
different number of subjects, so a foreign model's spurious findings partly measure the default
reviewer rather than the model.

**The corpus is synthetic by construction.** Fictional systems, original architectures, no
employer-derived content (design-principles §19). That is what makes publication safe, and it also
means the corpus establishes behaviour on documentation written for this purpose — not on the
messier documentation real engagements produce.

## Licensing and provenance

The repository is MIT licensed. Scenario provenance:

- **husky-ai** and **crypto-wallet** are seeded from the OWASP Threat Model Library (MIT). The
  source's system description became `input/` and its threat list became `expected-threats.yaml`.
- **invoice-agent** is seeded from a GenAI Agent Security Initiative insecure-agent sample whose
  license is unasserted. Nothing from it is reproduced: the scenario content is authored originally
  and the source is cited by URL.
- **Every other scenario** is original to this project.

Requirement text in `requirements/` is written originally. Source frameworks are recorded as
provenance and cited by identifier only — ASVS 5.0 is CC BY-SA 4.0, so its wording is never
reproduced, only referenced as `OWASP ASVS: v5.0.0-<requirement>`. This is enforced rather than
promised: `tests/unit/test_requirements_catalog.py` pins the citation format and resolves every
ASVS identifier against a cached export of the published release.

## Keeping the manifest true

```bash
uv run python scripts/build_benchmark_manifest.py           # regenerate
uv run python scripts/build_benchmark_manifest.py --check   # fail if stale
```

The manifest is assembled from the corpus, never authored (DEC-076). CI runs `--check` beside the
scorecard, comparison, ablation, and mapping-variants currency checks: promoting a capture without
regenerating the manifest leaves the package describing a corpus that no longer exists, and the
check is what catches it.

The package version in `src/trace_ai/services/evaluation/package.py` is the one value a person
sets. DEC-146 states when it moves.
