# Live-failure diagnosis: the flagship 0-of-3 and the unsigned-webhooks failed runs

*Issue #564, decided as DEC-116. Written 2026-08-18 against the committed evidence: the
ForgeFlow live capture (`demo/forgeflow/recorded/`), the stability record
(`docs/eval/live-stability.json`), and the code paths named below.*

Two recorded results contradicted the project's thesis and had no diagnosis: the flagship
`claude-opus-5` capture approved four defensible findings that matched none of the truth set's
three expected (0 of 3 matched, 4 spurious), and the DEC-077 stability protocol saw three of
five `unsigned-webhooks` attempts fail outright, with the one expected finding reproducing in
only two of the five completed runs. This note records what actually happened, what changed
because of it, and what deliberately did not.

## 1. The flagship 0-of-3 is an evidence-validation funnel, not a mapping error

The recorded explanation — "real weaknesses, wrong requirement lens" — was wrong in a way that
mattered: it read as the model mapping weaknesses to the wrong requirements. The capture shows
the opposite. The run produced control mappings under **all three** expected requirement
identifiers (`req-AI-001`, `req-AI-002`, `req-DATA-002`), on threats naming the expected
components. Every expected component name appears in at least one approved finding; no approved
finding carries any expected requirement id. The expected lenses were produced and then lost,
in two stages:

**Stage one: silent assessment omission.** The single evidence-validation call returned 74
assessments — 25 of them over the run's 185 control mappings. DEC-013's outcome table resolves
an unassessed mapping to no output, so the 160 unassessed mappings could never become findings
regardless of content. The prompt (`prompts/evidence/validate-evidence-v1.md`) asks for every
conclusion and provides `not_evaluated` — "you did not assess it, and you say why" — as the
honest decline; the run instead omitted the subjects entirely, and nothing distinguished the
omission from a decision. The five mappings that were both `partially_satisfied` and assessed
`supported`/`partially_supported` are exactly the five candidate findings the reviewer saw.
Among the unassessed: the mappings carrying `req-AI-001` and `req-AI-002` on the
prompt-injection threat. (Mapping identifiers here are reconstructed from the recording by
sequential allocation and cross-checked against six critique references and the report's
verbatim text; the recording itself does not label which retry attempt was consumed.)

**Stage two: contradiction downgrades, by design.** The assessed mappings on the expected
requirements were classified `contradicted` and downgraded to questions: the 30-day retention
target against "deleted after analysis" (`req-DATA-002`), and automatic comment posting against
"reviewed before publication" (`req-AI-002`). The prompt mandates exactly this — "a
contradiction is named, never resolved by preference" — and the run surfaced both as
high-priority questions (`question_usefulness` 1.0). The truth set resolves each contradiction
and expects a finding; the pipeline's own rules require a question until a person resolves it.
The truth set also disagrees with itself: `expected-control-mappings.yaml` records GW-13.2
(`req-AI-002`) and GW-13.3 (`req-DATA-002`) as `reachable_at: unverified` with
`expected_outcome: question`, while `expected-findings.yaml` expects both as findings. That
tension is recorded here and left unresolved; reconciling the truth set is authored-content
work with its own decision, not a side effect of a diagnosis.

What was ruled out: the structural matcher's wording sensitivity. Matching is exact on
(requirement id, normalized component name) and never reads prose; the components all matched,
so no similarity threshold would have changed the score. The matcher behaved as specified.

## 2. The unsigned-webhooks failures were one mechanical slip, since fixed twice over

All three failed attempts died the same way: the extraction wrote `authentication: "none"` on a
data flow the documents are silent about, and the context validator refused it under
data-model.md section 14's rule that unstated transport security is `unknown`, never false-like.
The runs died at checkpoint 1; their traces went with the protocol's temporary directory and are
unrecoverable. Two fixes already landed in earlier sessions: the harness performs the mechanical
section-14 relabel through the ordinary reviewer-edit path (counted as a defaulted decision),
and DEC-093 replays recorded reviewer decisions by content fingerprint so the default policy no
longer approves everything blind. The protocol's own top-up session ran three attempts for three
completions after the relabel landed.

The three completed runs that missed `FND-UW-01` produced **zero findings** — the aggregate
arithmetic pins it: false-negative rate 0.6 ± 0.49 over a one-finding truth set, reviewer
acceptance 0.4 ± 0.49, zero spurious findings and zero invented report findings in every run.
The miss is under-production, not misnaming. Whether the same evidence-validation funnel is the
mechanism cannot be settled from the lost traces; the coverage instrumentation below measures
it on every future run.

## 3. What changed (DEC-116)

- **Omission is now named.** `validate_assessments` reports `unassessed_subject_ids` — every
  supplied subject the proposal never assessed — and the evidence-assessment node records the
  count in its execution metadata. Reported, never blocking: the recorded corpus was captured
  under the silent behaviour, and a validator that suddenly refused it would fail replays
  nobody can re-capture offline.
- **Coverage is a metric.** `evidence_assessment_coverage` (assessed subjects over assessable
  subjects, computed from persisted objects) lands in every evaluation feed, so replays of the
  existing corpus show the funnel retroactively and the stability protocol aggregates it
  automatically.
- **The recorded explanation is corrected** on the scorecard, the README failure taxonomy, the
  release record, and the interview package: the miss is the funnel, not the lens.
- **DEC-092's heading is restored.** The #534 merge replaced the `## DEC-092` heading line with
  the DEC-091 amendment paragraph, leaving the entry's body headingless inside DEC-091 through
  two merges while the corpus cited it. The decision-log structure guard now also asserts the
  numbering runs contiguously, so a swallowed heading is a visible gap.

## 4. What deliberately did not change

- **No blocking coverage check and no retry on omission.** A retry would consume recorded
  responses replays do not have, and live it would demand a single response assess every
  subject — the output-length physics that produced the truncation in the first place. The
  behavioural fix is batching the evidence-validation call per subject group, the same shape
  DEC-024 gave mapping (one call per threat); that is a design change with a cost profile, so
  it is DEC-116's named follow-up, to be measured by the #484 sweep rather than assumed.
- **No prompt edit.** The prompt already asks for full coverage and offers the honest decline;
  the truncation is a capacity behaviour, not an instruction gap. A prompt-version pair worth
  comparing under #331 should carry a real change, and the batching follow-up is that change.
- **The truth set stays as authored.** The GW-13.2/13.3 tension is recorded above.

## 5. Confirmatory runs

Two live runs (label `confirm-564`, 2026-08-18, `claude-opus-5` on `primary-development`), run
with the coverage instrumentation live. They confirm rather than replace: the committed
`docs/eval/live-stability.json` stays the DEC-077 record — a two-run confirmation is not a
five-run protocol — and the next full protocol rides the #484 sweep.

- **Zero failed runs.** The mechanical section-14 slip that killed three of the first protocol's
  five attempts did not recur under the current harness.
- **FND-UW-01 unanimous, two of two**, severity concordance 1.0, zero spurious findings, zero
  unsupported claims. The finding that reproduced in two of five completed runs reproduced in
  both — encouraging, and n=2 is stated rather than rounded into a claim.
- **`evidence_assessment_coverage` 1.0 in both runs** — the metric's first live readings. At
  this scenario's scale the single evidence-validation call covers every assessable subject,
  and with full coverage the expected finding materialised both times. Consistent with the
  funnel being a scale behaviour (forgeflow supplied 185 mappings; this scenario supplies far
  fewer), and the lost traces of the first protocol's zero-finding runs stay undiagnosable.
- **Defaulted decisions 33 per run** against the old protocol's ~36 per run: DEC-093's
  fingerprint replay ran live for the first time and matched only a few recorded decisions —
  the count now measures novelty honestly, and the reduction is modest.
- **Cost $9.29 ± 0.01 per run, ~54 minutes per run, 16 model calls** — above the recorded
  $6.92 ± $3.28 mean and inside nothing: two runs bound no distribution, and the sweep's
  per-scenario figures supersede both.

## 6. Postscript (2026-08-19, DEC-133)

Section 1's stage-two tension is decided. The truth set's finding expectations FND-002 and
FND-003 now declare the contradiction resolution they depend on (`requires_resolution`), and a
run whose reviewer supplies no resolution reports them as conditional-unreached rather than
missed — the run's paired questions carry the grade, which is what this document's own analysis
said the pipeline was right to produce. The flagship row's headline therefore reads 0 of 1
reachable with two unreached, not 0 of 3; the number reads better and nothing about the funnel
is fixed — FND-004 still dies unassessed, and #585 is still what moves it. The counts quoted
above are the scores as recorded at diagnosis time and stand as history.
