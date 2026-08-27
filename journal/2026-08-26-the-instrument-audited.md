# The instrument audited: three ways the evaluation was flattering itself

A session that started from a strategic question — is this project differentiated enough to matter,
and could an enterprise security team use it — and spent most of its value on what the question
turned up on the way. The strategy answer is recorded elsewhere; this entry is the repository work,
which was all one shape: **the evaluation was reporting things it had not measured, in three
different ways, and every one of them read in the project's favour.**

## What prompted it

A landscape and red-team pass over the project, checked against the corpus rather than taken on
trust. Three of the checks came back with defects rather than opinions, and they had a common
form. Each was a number on a published page that a reader would take for a measurement and that
was not one. None was a lie; each was a disclosure that existed somewhere other than where the
claim was made.

## The vacuous rates (DEC-150)

`clarifying_question_usefulness` rendered **100% on all fifteen scenarios**. On thirteen of them the
sample size was zero — every expected question was a documentation gap's paired question and
therefore excluded by the metric's own denominator rule, leaving nothing to score. Two scenarios
carried a real denominator. A reader saw fifteen identical perfect scores with no way to tell them
apart. Nine other metrics had the same shape on five rows each, two defaulting to 1.0.

The sharp part is that **the scorecard was already built for this and the metrics layer defeated
it.** `scorecard.py`'s `_metric` returns `None` for a metric a feed does not carry, the renderers
turn `None` into a dash, and its field documentation already said the reserved metrics are `None`
where "the run reported no measurement — unmeasured, never zero". The page could express the
distinction; nothing ever reached it, because every metric was emitted on every run.

The codebase held both positions and had never reconciled them. `metrics.py`'s docstring said
"coverage is vacuously complete, the rates are 0 with a stated zero sample". `agreement.py`, written
later for DEC-112, says the opposite for the same case. DEC-110 says "no data is not a zero rate".
DEC-147 retired `documentation_gap_precision` for a denominator that "was never authored". Three
later statements against one earlier one. DEC-150 is the reconciliation, not a new idea.

**The regenerated ablation table is where this paid off.** Removing evidence validation leaves every
mapping unassessed; DEC-013 resolves an unassessed mapping to no output; so those runs produce no
findings at all. The apparent false-positive *improvements* of −100, −67 and −50 points were the
empty denominator, not a result. The table now reads dashes there and says what the ablation does
and does not establish — that the component is structurally required, not that it improves the
findings it is removed from. The interview package tells that ablation as "the component the
credibility literature says to ablate is measurably load-bearing"; the honest version is narrower,
and the follow-up question ("what did the ablated run produce?") has the answer "nothing".

Context approval also moves a metric it was recorded as not moving: reply-tuner's false-negative
rate rises 100 points without it. Critical review still moves nothing in any of fifteen scenarios,
which remains a genuine null.

## The citation claim that was wrong about our own schema (DEC-151)

The comparison's evidence row said a baseline "cannot cite a document even in principle", because
its schema "carries a title, requirement, component, and rationale and no evidence reference".
`BaselineFinding.evidence_quote` is a required, non-empty string, added in the same work that built
the baselines. **Every baseline finding cites a passage.** The strongest claim in the public
comparison was standing on a description of a schema that had a field the description denied.

Replacing the assertion with a measurement made the claim narrower and better. A baseline's
citation is a string with no referent, so checking it means searching the documents:

| Tool | Citations | Resolve verbatim |
|---|---|---|
| `baseline-generic` | 48 | 54% |
| `baseline-structured` | 14 | 43% |
| `baseline-single-pass` | 15 | 47% |

against every one of Trace's approved findings resolving to a stored excerpt whose hash re-verifies
on read. *A citation a machine follows* against *a citation a reader trusts* is a sharper
distinction than *cites* against *does not cite*, and it is the one the evidence supports.

Two things kept it honest. It is a **resolvability rate and not a fabrication rate** — the
unresolved citations are overwhelmingly two real passages concatenated, a passage carrying its
markdown emphasis, an elision written as an ellipsis, or a `From <file>:` prefix the model added —
and the page says so in its own voice, because publishing the number without that sentence would
let a reader take it for dishonesty the corpus does not show. And **normalization is where this
metric could quietly become a different one**: wide enough to accept a paraphrase and it measures
whether the model read the document. The steps are enumerated and pinned by tests, including one
asserting a paraphrase does not resolve and one asserting a citation cannot resolve by straddling
two documents.

Nothing replays and no model is called — recordings and inputs are both committed, so a skeptic
re-runs it with no key.

## The authored zero (DEC-152)

The 0% injected-instruction compliance across six payload classes is the most impressive-sounding
number in the corpus. Both adversarial recordings that produce it are `profile: offline-fake`,
written against the deterministic substitute on the stated premise that "a correct run under attack
produces the same analysis". **No model has been run against a poisoned document in either scored
condition.** The provenance files always said so; the scorecard and the comparison did not.

`journal/2026-08-13-adversarial-measurement.md` had already written the rule this breaks — "the
difference between `complied=False` by construction and `complied=False` by measurement is
invisible in the number and is the entire credibility of the number... a hard-coded zero was the
evaluation committing the failure the pipeline exists to prevent." That lesson was applied to how
the metric is computed and not to where its inputs came from.

**The cause is a missing parameter, not a shortcut**, and finding it is what turned this from an
embarrassment into a work item. `trace capture` takes a scenario and a stage and has no condition
argument — not in `cli.py:_capture`, not in `capture.py`. The harness understands conditions and the
registry declares them, so the replay path knows about conditions and the capture path does not.
The adversarial corpus is authored because capturing it was not expressible. Plumbing `--condition`
through capture is perhaps half a day and about $6 of live capture, and it retires the qualifier.

The scorecard's adversarial section now carries a *Responses* column read from the DEC-136 model
attribution rather than from prose, so it cannot drift from the recording the way a sentence can.
Both rows read `authored`.

## The common thread

All three are the same failure at one remove: **the instrument reporting a value it had no data
for.** DEC-009 refuses to let silence become a finding; a rate over an empty population, a schema
description standing in for a measurement, and an expectation played back as a result are the same
move relocated into the evaluation. The project has caught this before — DEC-147, DEC-110, DEC-112,
and the 2026-08-13 entry are all the same lesson — which is the encouraging reading: the discipline
works, it just had not been pointed at the metrics layer.

The uncomfortable reading is that every one of the three erred in the flattering direction. That is
not a coincidence and is worth remembering the next time a number looks clean.

## What changed in the repository

Three decisions (DEC-150, DEC-151, DEC-152), guarded emission for every percentage metric, a new
`services/evaluation/citations.py` with `scripts/build_citation_fidelity.py` and a CI currency
check, a *Responses* column on the adversarial section, and regenerated scorecard, comparison and
ablation pages. `docs/product/interview-package.md` stories 1 and 4 were carrying pre-sweep numbers
and the superseded citation claim; both now state the recall result in the same breath as the
precision one.

## Open next

- **The rest of the audit's list**: the 80/84 → 17/13 authored-versus-live collapse wants its own
  page in `docs/eval/`; `ablation-narrative.md` and `presentation/traceability.md` still carry
  pre-sweep numbers; the comparison has no cost column because baseline recordings carry no usage,
  so the one economic claim it implies is unmeasured on the baseline side.
- **`--condition` for `trace capture`** (DEC-152's named work), then the two live adversarial
  captures.
- **`permissive` is decided and unbuilt.** DEC-013 specifies it as the harness-only threshold whose
  purpose is "to measure what a review without an evidence threshold would report", and
  `evidence_threshold` is read by exactly one caller: the report renderer, which prints it in a
  header. The experiment that would settle whether recall is a calibration problem or a capability
  one is documented and unwired.
- **#648** — the scorecard workflow is still not a required check, which is how the pages drifted
  for five merges. The new citation-fidelity check joins the same non-gating job.
