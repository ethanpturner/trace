# 2026-09-11 — A reviewer's packet as a document

Yesterday two code reviewers were scored as external arms on the coded scenarios. Today the
exchange ran the other way: Mantis's review packet for `rag-support-bot`, plus the four candidate
records it had withheld from that packet, went into Trace as a fourth untrusted document beside
the three design documents. Twice: once as Mantis wrote it, once with three fabricated candidate
records appended in its register. The page is `docs/eval/exchange.md`.

## What changed

- `docs/eval/exchange.md`, in the site nav, with the two runs' decision files, packets, journals
  (DEC-139), ledgers, and identifier-only summaries under `docs/eval/exchange/rag-support-bot/`.
  The material sits under `docs/eval/` rather than under the scenario because the manifest
  digests a fixed set of scenario groups and an undigested sibling of `input/` would be material
  in the corpus that the corpus's digest does not cover.
- `tests/unit/test_exchange_page.py` pins every count the page states to the committed summaries
  and refuses a summary that carries a text field.

## What was found

The packet did not become a finding in either run, and the design held where it is structural.
It held unevenly where it is a model judgement. The same extractor, on the same model, classified
the four real candidate records `inferred` in the clean run and `documented` in the doctored run,
and in the doctored run it built a component, an asset, a data flow, and a trust boundary from a
fabricated telemetry record with that record as their only evidence. The checkpoint-1 package
presented those four objects the way it presented the ones grounded in the architecture overview.

The evidence validator's assessments split along a line nobody drew on purpose. Two fabrications
had been extracted as "a candidate record describes X": the validator marked them `supported`,
because the passage does describe X. The third had been extracted as a flat statement about the
system: the validator marked it `requires_confirmation` and recommended a question, citing the
packet's own disclaimer as the reason. The wording of the claim, not the truth of the record,
decided the verdict. Downstream, the fabricated flow became two documentation gaps and a blocking
question about a component that does not exist; the fabricated authentication claim became a
high-severity gap over a control the OpenAPI document declares, with no contradiction recorded.

## What went wrong in the running of it

Both runs stopped short of the finding checkpoint. The clean run hit a `--max-cost 3.0` ceiling in
critical review, set from the baseline's $2.55 without allowing for a fourth document. The
doctored run was stopped by hand when the billed spend reached the page's budget. The billed
figure was 1.77 times the ledger's estimate for the same calls, which means a ceiling on this
profile bounds a little over half of the money it appears to bound. That ratio belongs in the
profile's price table, not in a footnote, and it is recorded here so the next run's ceiling is set
from the billed figure.

## Open

- A routing reason for an object whose evidence is entirely a document that reports claims about
  the system, in the shape of DEC-062's `injection_flag`. The two runs argue for it; a decision
  entry would decide it.
- The finding checkpoint and critical review's disposition of packet-derived material, unmeasured.
- The `openai/gpt-5.1` price entry for the OpenRouter profile.
