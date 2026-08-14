# The flagship recording is real now

## What happened

Issue #324 closed: `demo/forgeflow/recorded/` now holds a complete pipeline run captured live
from `claude-opus-5` — 38 responses in consumption order, both checkpoints' decisions authored
against what the model actually produced, and a report hash the offline replay reproduces
byte-for-byte. The capture session cost roughly $30 including every discarded attempt, against
an estimate of $2.25–$5.97, and the overrun *was* the measurement: eight distinct defects fell
out of trying, every one invisible to the offline suite because the deterministic model never
serializes a schema, never thinks, never retries against real variance.

## What the live run produced

The extraction alone justifies the capture: sixteen components, six actors including the
untrusted repository-content author, twenty-seven flows, sixty-three claims of which fourteen say
`unknown` where the documents are silent, fourteen questions including the scenario's two
load-bearing ones, both planted contradictions surfaced as observations, and the injection
attempt detected and recorded. Fifteen threats, five candidate findings. At checkpoint 2 the
reviewer approved four with severities and rejected one on DEC-009 grounds — the run had proposed
a finding whose enforcement evidence was silence, and the rejection routes it back toward the gap
the run had also raised, which is the product's thesis exercised at its own checkpoint.

The scorecard now scores the flagship honestly: 100% finding evidence coverage, 72% mapping
accuracy, 100% question usefulness — and 0 of 3 expected findings matched, with 4 spurious by the
structural matcher. The model found real, defensible weaknesses that are not the ones the truth
set names. That is the live-model failure mode the README's taxonomy now reports as observed
rather than hypothesized.

## The defects the money bought

Beyond the four from the first session (grammar-size fallback, output-budget sizing, actionable
retry feedback, the vocabulary prompt rule), this session found four more:

1. **DEC-087.** The provider's strict grammar rewrites an open mapping to accept only `{}` —
   DEC-083's lesson recurring on a *required* field. `evidence_strengths` demanded one entry per
   citation while the wire grammar forbade any; the evidence agent burned five attempts on a
   structurally impossible instruction. Proposal dicts are now typed pair lists; the legacy form
   still loads.
2. **Promotion-only constraints crash paid calls.** The DEC-025 suppression pairing, the DEC-022
   coverage rule, and the subject-prefix checks lived only on domain objects, so a proposal
   violating one crashed at conversion after the call was paid. All are mirrored onto the
   proposals, where the retry feedback names the field.
3. **The driver's critique subject map omitted `EVIDENCE_ASSESSMENT`** — the enum declares it,
   the input package presents the assessments to the critic, and the validator refused critiques
   of objects sitting in the store.
4. **Severity critiques against severityless subjects** are now structurally refused at the
   proposal (only a gap carries an assigned severity before checkpoint 2), with the prompt
   teaching the rule.

## The shape changes that made it consumable

A 38-file recording made per-file `--response` flags unwritable, so the CLI accepts a directory
(numbered files, sorted), the recording is organized by segment — `extraction/`, `reasoning/`,
`report/` — matching the pipeline's two pauses, and the replayer, the demo tape, and the README
walkthrough all hand the three directories over. The harness discovers recordings recursively,
numbered files only. Retried calls are part of the recording: the four failed responses replay in
their consumed positions, inside the default retry budget, so the replay reproduces the retries
rather than hiding them. The replayer stamps the capture's true profile into the report while
building the deterministic model — the provenance lines say `claude-opus-5` because that is what
produced the responses.

## Open

Repeated live-run measurement (cost, runtime, DEC-077 stability) is M11's #330–#332, now
genuinely one command away. The README's remaining "not measured" claims are down to those.
