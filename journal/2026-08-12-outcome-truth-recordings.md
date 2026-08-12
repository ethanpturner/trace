# 2026-08-12 — Recordings for the outcome-truth scenarios (#326)

Third M11 delivery of the day, and the first of the authoring chain: `invoice-agent`,
`oidc-portal`, and `managed-db-service` carried full outcome truth sets and no recordings, so
the harness reported them skipped — the debt the M7 closing journal named. All three now
replay offline through `trace evaluate`, score against their truth sets exactly, and appear on
the scorecard: invoice-agent matches all three expected findings and both gaps with nothing
spurious, and the two zero-finding scenarios each produce their one expected gap and no
finding at all.

## How the recordings were authored

The shape was learned from the unsigned-webhooks recording and the machinery, not guessed:
one JSON per model call in consumption order (extraction, threats, one mapping per threat,
one evidence validation, one critical review per threat, report sections), decisions files
answered through the same writers an interactive session uses, and a provenance file per
scenario. Evidence identifiers were minted for real — a scratch store ingested and indexed
each input document to learn which `evd-` references exist and what each covers — so every
citation in the recordings resolves to a passage that actually says what the rationale claims.

The interesting work was making the zero-finding path honest rather than empty:

- **The rejections are recorded as suppressions, not silences.** The oidc-portal
  req-AUTH-001 mapping concludes satisfied on the documented delegation and carries the
  password-policy conclusion in `suppressed_conclusion`, suppressed by the catalog's
  `common_false_positives` entry; req-AUTH-002 is not applicable under the requirement's own
  `non_applicable_conditions` entry. Managed-db-service does the same for the
  encryption-detail class, with the platform's encryption proposed as an *inherited* control.
  The false-positive classes the scenarios exist to test are visible in the record, not just
  absent from the output.
- **A gap needs an evidence assessment that says so.** DEC-013's table routes
  `not_evaluated` to no output before it looks at satisfaction, so an unverified mapping
  produces its gap only through an assessment — `unsupported`, with
  `recommendation: documentation_gap` so the section 16 split lands on the gap rather than a
  question. REJ-MD-03 (metrics-API authentication) is deliberately not mapped at all: an
  unverified mapping there would manufacture a gap the truth set does not expect and cost
  gap precision.
- **The unmet mappings address the false-positive field by name** (DEC-025's structural
  check): without that, mapping validation downgrades an unmet conclusion to unverified and
  the expected finding becomes a gap.
- **Zero findings still demand report discipline**: the assembler requires the
  `lim-empty-findings` limitation of a zero-finding run, and the finding review concludes
  over an empty candidate set.

The expected questions in the truth sets are not produced: the clarifying-question metric is
reserved (#329), and the gap route asserts the least. The provenance files say so.

## Fallout

- The registry advances all three to `status: authored`; only husky-ai and crypto-wallet
  (#327) remain threat-truth-only. The `evaluate --all` skip test now expects the three to
  run.
- The scorecard, comparison, and ablation pages regenerate with the new rows, and a second
  DEC-081 history snapshot is retained — the first real use of yesterday's mechanism for its
  purpose: the sweep's numbers changed because the scenario set grew, and the history says so.
- Authoring surfaced a metric bug, filed as #388: `model_call_count` reads the run row as of
  the segment being executed, so a zero-finding run — one long segment after context approval
  — reports 1 for a run that made 8 calls.

## Open next

Six M11 issues remain: #327 (husky-ai and crypto-wallet outcome truth and recordings), #328
(the missing scenario categories), #329 (reserved metrics), and the live-run trio
#330/#331/#332, which spend provider money and want a deliberate session.
