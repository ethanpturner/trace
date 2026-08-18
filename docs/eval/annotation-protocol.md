# Second-annotation protocol

*The instrument is DEC-112; the adjudication rule is DEC-119; the machinery is
`src/trace_ai/services/evaluation/agreement.py`. This document is the procedure a second
annotator follows. Issue #565 stays open until a person has completed a pass.*

Every truth set in this repository is one person's judgment, and every benchmark number is
measured against it. This protocol produces the second, independent annotation set that turns
"my numbers agree with me" into a measured inter-annotator agreement statistic. The pass is
designed to be a bounded afternoon, not a project.

## Who can annotate

A security-literate person — someone who has performed or closely reviewed architecture-level
security assessments — who has not authored or reviewed any of this repository's truth sets and
has not read its `expected/` directories, evaluation results, or reports. Independence is the
entire value of the exercise: a pass by someone who has seen the answers measures memory, not
agreement.

**Solo fallback (DEC-112):** if no second person is available, the same annotator may repeat
the pass months later without consulting the first set. That result is reported as
*test-retest agreement* and never as inter-annotator agreement.

## The scenarios

Five scenarios, chosen so the pass covers the judgment classes the truth sets exercise:

| Scenario | Input | Catalog | Why this one |
|---|---|---|---|
| `demo/forgeflow` | eight documents | 0.1 | The flagship: the richest truth set, and the one the portfolio's headline numbers rest on. |
| `benchmarks/unsigned-webhooks` | one document | 0.1 | The finding/gap boundary: a documented weakness beside an undocumented one — the project's central distinction. |
| `benchmarks/missing-docs` | small | 0.1 | Missing documentation: where "silence is not absence" (DEC-009) most invites disagreement. |
| `benchmarks/contradictory-docs` | small | 0.1 | Contradictory sources: whether a contradiction resolves to a finding or a question is a live judgment call. |
| `benchmarks/oidc-portal` | small | 0.3 | Delegated authentication: the inherited-control false-positive class; expects restraint, not findings. |

The catalog column names the requirements catalog version to assess against, from
`benchmarks/scenarios.yaml`; the catalog lives under `requirements/<version>/`.

## What the annotator receives

For each scenario, exactly:

- the scenario's `input/` directory — the documents Trace itself would be given;
- the requirements catalog version named above;
- this protocol.

## What the annotator must not consult

- any `expected/` directory, `reviewer-notes.md`, or `annotations/` content;
- any `recorded/` directory, `benchmarks/results/`, or anything under `docs/eval/`;
- Trace's own output for any scenario, and the journal's discussion of scenario authoring.

The withholding rule mirrors the harness's own: nothing under `expected/` is ever supplied to
Trace, and nothing from it is supplied to the second annotator.

## What the annotator produces

For each scenario, a directory `annotations/second/` beside its `expected/`, holding up to
three files that mirror the truth-set shapes. Only the identity fields are scored — wording is
never compared (DEC-056, DEC-112) — but notes are welcome and help adjudication.

`expected-findings.yaml` — evidence-supported weaknesses:

```yaml
findings:
  - key: SEC-FND-01            # any unique key; your own numbering
    requirement_id: req-XXX-000  # from the scenario's catalog version
    affected_component: Component Name
    notes: optional free text
```

`expected-documentation-gaps.yaml` — a control whose existence cannot be determined:

```yaml
documentation_gaps:
  - key: SEC-GAP-01
    requirement_id: req-XXX-000
```

`expected-questions.yaml` — what a reviewer would need answered:

```yaml
questions:
  - key: SEC-Q-01
    asks: The question, phrased so a person could answer it.
```

Three rules while annotating:

- **A finding needs affirmative evidence.** A weakness the documents state or demonstrate is a
  finding; a control the documents are merely silent about is a documentation gap or a
  question, never a finding. Requirements are phrased so silence resolves to unverified.
- **Name components as the input documents name them.** Identity matching is
  whitespace-collapsed and case-insensitive, but `Comment Service` and `GitHub Comment
  Service` are different components. Use the document's most specific name.
- **A file you did not get to is a file you omit.** An absent file is scored as "not covered",
  never as "found nothing". If you assessed an artifact and found nothing, commit the file
  with an empty list — that is a statement.

Budget roughly 90–120 minutes for forgeflow and 30–60 minutes for each small scenario: four
to six hours for the full pass. Record the actual time; it is worth reporting beside the
numbers.

## What happens afterwards (DEC-119)

The second set is committed as authored and is immutable from that point: it is the
measurement. The harness computes Jaccard agreement per artifact and pooled
(`annotation_agreement` in the feed; the "Annotator agreement" section of the scorecard) on
the next benchmark run. The first set stays authoritative whatever the number. The truth-set
owner reviews every disagreement — each identity present in only one set — and records the
outcome in `annotations/second/adjudication.md`: *agree* (the expected set gains or amends an
entry through an ordinary, separately-committed truth-set edit), *hold* (the first set stands,
with the reason), or *out of scope* (the item lies outside the scenario's documents). The
agreement statistic is always reported as measured against the second set as submitted;
adjudication edits change the truth set going forward, never the measurement.
