# 2026-08-12 — The Stage 5 scenario categories close (#328)

Fifth M11 delivery of the day, and the largest: four new scenarios — input, full outcome
truth, offline recording, registry entry — closing every roadmap Stage 5 coverage category
that lacked one. The register now holds twelve fully authored scenarios, all replaying under
`trace evaluate --all` with nothing skipped, and the registry gained a `category` field so
coverage is a stated fact rather than something inferred from directory names. A test pins
both properties: every scenario declares a category, and the Stage 5 list is covered.

## The four scenarios

- **missing-docs (Kiosk Sync Service)** — the explicit missing-documentation scenario: a
  one-page note that makes three requirements applicable (the records are customer data;
  kiosks and fulfillment call the service) and answers none of them. Three gaps, three
  paired questions, zero findings by design — the DEC-009 acceptance criterion, replayed:
  a run that produces any finding from this input has invented a fact.
- **order-notifier (duplicate threats)** — two documents affirmatively describe the same
  unsigned callback intake, and the recorded mapping draws the conclusion once per document.
  The provisional findings share a threat and a requirement, so DEC-052 merges them: the
  survivor carries both documents' evidence, the duplicate is retained with
  `duplicate_of_id`, a merge record persists, and exactly one finding is approved. The
  scorecard's `duplicate_finding_rate` is non-zero here by design — the first scenario to
  exercise the dedup path end to end.
- **translation-gateway (third-party integrations)** — a connector sending full ticket
  bodies to an external translation SaaS. The graded boundary is between the relationship
  and the provider: the documented missing retention agreement and the admittedly
  over-scoped workspace token are findings; what the provider actually does with submitted
  text is unknown and the rejections keep it out.
- **parcel-platform (large architecture input)** — four zones, nineteen components,
  thirteen flows in one document. The graded property is that scale does not change the
  rules: two findings on affirmative statements (the admin console reached through the
  customer sign-in path; notification bodies logged with names, addresses, and delivery
  windows), two gaps, and rejections naming the conclusions a large surface most invites.

## Working notes

- The `category` field is informative by design — nothing routes on it, scenarios may share
  one, and prompt injection is deliberately a condition (unsigned-webhooks adversarial, M8)
  rather than a category value, which the new registry test documents.
- Two mechanical authoring lessons: relative `cd` in composed shell commands scattered
  recording files into the wrong directories (recovered from `git status`, nothing lost),
  and `0$((7+i))` produced `010` file prefixes that sort before `03` — the recording
  consumption order is the sorted glob, so the replay consumed responses out of order and
  the deterministic model refused with exactly the diagnostic the seam promises. Both
  worth remembering for #330's live captures: file order is the protocol.
- README and CLAUDE.md still described the benchmark suite as five-of-eight recorded;
  both now state the register as it is.

A fourth DEC-081 snapshot retains the day's final sweep: twelve scenarios, twenty-one
scored rows.

## Open next

Four M11 issues remain: #329 (reserved metrics — the register now carries question, threat,
and context truth for it to compute against), and the live-run trio #330/#331/#332, which
spend provider money and want a deliberate session.
