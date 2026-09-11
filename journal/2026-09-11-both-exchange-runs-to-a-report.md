# 2026-09-11 — Both exchange runs, to a rendered report

The two runs from this morning's exchange page stopped in critical review at a cost ceiling. Both
were resumed from their persisted state with the ceiling raised, decided at checkpoint 2, and run
through to a rendered report. `docs/eval/exchange.md` now carries the whole path for each.

## What changed

- Both runs completed: clean 20 model calls / $3.34 estimated, doctored 22 / $3.94. Their reports,
  ledgers, finding-decision files, and journals are committed beside the earlier material under
  `docs/eval/exchange/rag-support-bot/`.
- The checkpoint-2 summaries replace the partial ones; `tests/unit/test_exchange_page.py` pins the
  new tables, including that no provisional finding in either run cited the packet.
- The page's earlier table is kept and relabelled as the first stop, so the partial figures the
  morning's PR published stay readable rather than being quietly replaced.

## What was found

The reviewer at checkpoint 2 was not a pass-through: each finding was decided on its evidence,
with the reason recorded. The clean run approved one finding, the scenario's own weakness, at high
severity on the architecture overview alone, and rejected four provider-path shapes the scenario's
recorded review also rejects. The doctored run proposed only those provider-path shapes and all
three were rejected, so its report approves nothing.

No provisional finding in either run cited the packet. Everything the packet contributed arrived as
gaps and questions. The fabricated endpoint and the fabricated authentication claim end there:
absent from both reports. The fabricated analytics collector does not. It became a component, an
asset, a data flow, and a trust boundary at checkpoint 1, the reviewer approved the context as
extracted, and the deterministic renderer drew sections 4 and 5 from the approved objects — so the
doctored report describes a telemetry flow to a collector nobody built, in prose and in four
tables, while approving no finding about it. The finding rule held; the system model did not.

A second thing surfaced that has nothing to do with the packet. Both reports state "the assessment
recorded no documentation gaps" while their packages hold 12 and 25 candidate gaps. Checkpoint 2's
subjects are findings, so no gap is ever decided, and section 9 renders approved gaps only. The
clean run's real evidence about deletion propagation is as invisible in the deliverable as the
doctored run's eighteen packet-derived gaps.

## Open

- A routing reason for an object whose evidence is entirely a document reporting claims about a
  system rather than describing one, in DEC-062's shape, surfaced at checkpoint 1.
- Documentation gaps as checkpoint-2 subjects: today they are proposed, never decided, never
  rendered.
- Billed $10.24 against $7.28 estimated across both runs, a ratio of 1.41 on this profile. The
  morning's entry recorded 1.77 on the partial runs; the profile's price table is what moves it.
