# The reason that refuses

DEC-157 landed a routing reason and nothing that acts on it. That was the right size for the
decision it was answering — the exchange page had asked for a signal, and a signal is what it got —
but the run that argued for it says plainly what a signal alone is worth. In the doctored exchange
run a fabricated candidate record became a component, an asset, a data flow, and a trust boundary;
checkpoint 2 approved no finding about any of them and rejected all three the analysis proposed;
and the rendered report still describes a telemetry collector nobody built, because the renderer
draws its system description from approved *context*. The finding checkpoint held. The context
checkpoint is where the fabrication walked in, and it walked in through a decision file that said
`decision: approve` under every subject and nothing else.

## What was decided

DEC-158. A `report_derived` subject is an approval blocker until its `ReviewerDecision` both
decides it and carries a rationale. `ContextReviewPackage.approval_blockers` gains the class beside
the unanswered blocking question and the outstanding validation error; `approve_context` refuses in
the same words, by the same mechanism, at the same place. The review file gains
`decision_rationale:` on object and claim entries, exported as an empty slot beside `decision:`,
and `trace context review --reason` carries the same on the flag path.

The thing to be careful about is what the gate is *not*. It does not re-label a claim, remove an
object, or judge whether the extractor was right — `agent-design.md` section 8 forbids the
validator from correcting, and this is not the validator. It demands a sentence, not a particular
answer. "Keep: the packet is the only source and the risk is acceptable" clears it, and the record
then carries that, which is more than the blanket pass carried.

## Why not the alternatives

Refusing the object outright — treating a subject whose sole evidence is report-kind as an
extraction error — was the tempting one, and it is the correction section 8 exists to prevent. It
also makes the legitimate use impossible: registering a scanner's output to see what it adds is a
thing an operator should be able to do deliberately.

Erroring on a `documented` claim whose evidence is entirely report-kind, and routing it back for a
retry, stays open exactly where DEC-157 left it. The failure mode is the one section 26 names: the
extractor rewords the claim until it stops being retried. Two runs, one sample per condition, is
not enough to decide it.

A blanket acknowledgement — one flag meaning "I saw the report-derived subjects" — is the pass with
an extra step.

Holding only objects and not claims would have let two of the three fabrications through: B.5 and
B.6 produced claims and no object, and the claims are what the analysis phases reason over.

## What it would have caught

The doctored run's own identifiers, pinned in `tests/unit/test_report_derived_gate.py` against the
committed checkpoint-1 summary: seven packet-sole `documented` claims, `ctx-030` to `ctx-032` among
them — one per fabrication — and the four objects `cmp-009`, `ast-005`, `df-005`, `tb-004` that
reached the report. Each is a subject the gate holds until the reviewer writes a reason. Whether
that reviewer then rejects them is the reviewer's business; what changed is that the question is
now asked out loud.


## What the live run showed

The same doctored packet, byte-identical, registered `--kind report`. The extraction built two
objects on the fabricated analytics record alone and four `documented` claims on the packet alone,
and the package carried no blocking question and no validation error — approvable exactly as it
stood, before this change. A file approving all 45 subjects as extracted with no reasons recorded
50 decisions; `trace context approve` exited 3 and named all six. Decided individually with
reasons, the fabricated component and asset and the two fabrication claims were rejected and the
two claims about the packet's own status were kept, because the packet does say that about itself.
The approved revision holds 8 components and 4 assets against the extraction's 9 and 5.

Two honest limits. This is a fresh extraction, not a replay: it produced 20 objects to the first
doctored run's 25 and built no fabricated data flow or trust boundary at all, so the two runs are
not comparable object-for-object and the difference is variance rather than an effect of the flag.
And the reviewer who answered the gate is the person who wrote it, which is the weakest possible
test of whether a reviewer under time pressure writes a considered reason or "ok" — the gate
accepts both, and DEC-158 records that as its own tradeoff rather than pretending otherwise.
