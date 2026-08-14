# 2026-08-12 — The reserved metrics compute (#329)

Sixth M11 delivery of the day. Six metrics the harness reserved but never emitted now
compute, persist as `EvaluationResult` rows, and render on the scorecard's new "Truth-set
coverage" table: context accuracy, threat coverage, requirement-mapping accuracy,
clarifying-question usefulness, an unsupported-claim rate beside the existing count, and a
token-usage row.

## The judgments

- **Each truth metric computes only where its truth is authored.** `context_accuracy` needs
  `expected-context.yaml` (forgeflow alone authors one), `threat_coverage` needs
  `expected-threats.yaml`, and so on; a scenario without the file simply lacks the row, and
  the scorecard shows a dash — unmeasured, never zero. The matchers live in `matching.py`
  beside the DEC-056 finding matcher and are structural throughout: names, endpoints, and
  (subject, predicate) pairs, never wording.
- **Paired questions stay out of the usefulness denominator.** DEC-013 routes one mapping to
  a gap *or* a question, so a question named as a gap's `paired_question` is structurally
  unproducible beside its gap — it documents how the gap converts once answered. Counting it
  would penalise the gap route the truth sets themselves expect. Where every expected
  question is paired, the metric is vacuously covered with a note saying so.
- **Mapping accuracy does not bind threat identity.** An expected (requirement,
  satisfaction) pair matches any produced mapping stating both; binding the threat would
  make this metric depend on the threat matcher's outcome, and the `must_not_conclude`
  negatives stay asserted by tests rather than scored.
- **The unsupported-claim rate's denominator is the agent-authored prose**, naively
  sentence-segmented; the count row keeps the numerator alone. Computing it required wiring
  `compute_report_metrics` into the pipeline at all — the module existed since #111 with no
  pipeline caller, so even the count never reached a run. The report-rendering adapter now
  computes and persists the report metrics from the same validation passes that gated
  publication, carried on `PublishedReport` rather than re-validated.
- **Token usage is emitted only when a provider reported spans.** An offline replay has no
  token truth, and a zero row would be a default wearing a measurement's clothes; the
  column populates on the first live run (#330).

## What the numbers say

The new table is honest in ways the old one could not be. Forgeflow's minimal recording
scores 6% context accuracy, 40% threat coverage, and 6% mapping accuracy against its full
truth set — the README has said since M10 that the recording does not score against the full
truth, and now the scorecard measures the statement instead of footnoting it.
Husky-ai and crypto-wallet score 100% threat coverage — their recordings were authored
against the OWASP-derived threat truth — while invoice-agent scores 20%, because its #326
recording was authored against the outcome truth before threat coverage existed. That last
number is a legitimate target for a better recording, and it is exactly the kind of movement
the DEC-081 history now retains across builds.

A fifth history snapshot retains the day's final sweep.

## Open next

Three M11 issues remain, all wanting live provider runs: #330 (the measured live
assessment — which will also populate the token column), #331 (prompt-version comparison),
and #332 (model comparison). All three spend API money and want a deliberate session.
