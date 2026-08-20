# Recorded run for the unsigned-webhooks scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-19 via `trace capture` under
the `openrouter-economy` profile (DEC-135), in the #484 subset wave — replacing the authored
offline recording file for file. Version pins: profile openrouter-economy, workflow 0.2 (the
registry pin; the adversarial condition keeps its own 0.1 pin beside its authored recording,
per the DEC-134 amendment this wave produced), catalog per the registry, template report-v1,
generation timestamp 2026-08-11T12:00:00+00:00. Ten envelopes, real usage throughout, $1.28
staged: two extraction positions (a schema-failed first attempt and its retry, both consumed
on replay), one threat analysis, three mappings, one evidence batch, two critical reviews, one
report. `report-hash.txt` is pinned from the deterministic double replay rather than the
capture's own print: the zero-finding completion path rendered with an unpinned wall-clock
stamp — a capture-flow defect this capture surfaced and this wave fixed — so the capture-time
hash was unreproducible by construction.

## Reviewer decisions and what the recording measures

Checkpoint 1 approved all objects with one edit the validation node itself demanded: the
CI-to-receiver flow's `authentication` relabelled from `none` to `unknown` (section 14 — the
documented no-signature-check fact rides the evidenced `ci_signature_verification: false`
claim; the flow-level field is genuinely undetermined). The blocking question was answered
from the document: the platform supports signed deliveries and the receiver checks no
signature — a documented posture. The run then completed with zero candidate findings:
evidence validation assessed every subject (`evidence_assessment_coverage` 1.0 — the funnel
that hid the flagship's misses is closed) and judged the missing signature verification a
documentation gap rather than an unmet control. Against the truth set expecting FND-UW-01
this scores 0 matched, 1 missed, 0 spurious: a model-lens divergence on exactly the scenario's
subject, measured with the omission excuse gone. The score is the measurement; reconciliation
is #589's.

`baselines/` now carries live `openai/gpt-5.1` recordings for all three DEC-074/DEC-126
conditions, captured the same day.
