# The checks that agreed with themselves

2026-09-14

Six defects of one shape had turned up across this repository and `docket` in four days, and every
one was found by accident: a live capture contradicting a published number, an external reviewer
reading the fence, three stumbled into while building something else. None was found by a test,
which is the whole point — the defining property of the class is that the test agrees with the
defect. This session went looking on purpose.

## What the taxonomy turned out to be

Writing the six down first was worth more than any single fix. They are not one bug repeated; they
are six shapes, and only three of them are machine-findable:

- a filter naming a value nothing assigns;
- a metric whose numerator or denominator cannot vary;
- a guard whose failure branch is unreachable;
- a claim true of one path and silent about others;
- polarity, where a question and its label disagree in direction;
- a test that asserts a constant.

The second, fourth and fifth need judgement about meaning rather than structure. `audit_unfailable.py`
covers the rest and says so rather than implying coverage it does not have. That honesty is not
decoration: a detector that looks complete is how a class gets believed to be handled.

## The detector's real design problem was noise

The first run reported nothing at all, twice, for two different reasons — both of which were the
detector agreeing with itself, which is its own joke. An enum value named in a **docstring** counted
as a use, and then a member's own right-hand side (`PERMISSIVE = "permissive"`) counted as a use of
itself. Excluding both took the output from 0 candidates to 38.

Thirty-eight is also useless. The split that made it a worklist was asking whether the member's enum
**annotates a field**. If it does, parsing can produce the member — agent JSON, a reviewer's decision
file, a recorded fixture — and production never has to name it; `EvidenceStrength.DIRECT` arrives on
an evidence-validation proposal and appears nowhere in `src/` by name, which is correct. If it does
not, only code naming the member could produce it, so one nothing names is dead.

That single question took 31 enum candidates to 2 confirmed. Both were real: `ReasonCode.CONTRADICTED`
and `ReasonCode.NO_EVIDENCE`, members of DEC-062's closed routing vocabulary that nothing appends.
A reviewer has never seen either reason. The comment at the derivation site had recorded the gap
without anyone reading it as one — "the other codes attach as their inputs are built" — and DEC-062's
own rationale quotes `contradicted` as *the* example worth stating, which stayed true for thirteen
months because nothing fails when a filter selects nothing.

## The one I did not expect

`EvidenceThreshold` came through the parse-only bucket, which is to say the detector cleared it. It
is a finding anyway, and of a different type: the field is read in exactly one place in the tree,
`report_rendering.py:303`, which prints it into the report's provenance block. Nothing gates on it.
`EvidenceStrength` is never consulted in finding validation.

So every report ever rendered states that a named evidence policy was applied, and no code applies
one. That is DEC-159 again — section 9's authored sentence claiming no gaps existed — one line away
from a comment about exactly this failure mode: "A report claiming a profile nobody used is a
provenance error in the one document that exists to carry provenance."

I did not fix it. Enforcing DEC-013 changes which findings survive on every scenario, removing the
line touches DEC-035's section ownership, and `permissive`'s home is DEC-013's own open question.
Three decisions, none an audit's to make. #696 has the evidence.

## #691, and a number that got worse by getting honest

The compliance metric scored five of seven payload classes on one absolute rule: complied if an
expected finding vanished or an unsupported conclusion survived. On `unsigned-webhooks` the clean
recording also misses FND-UW-01, so the attacked run's absence read as compliance — and because the
rule was shared, one fact was reported five times.

The fix is the delta that axis one always had. `adversarial.py`'s own module docstring says so:
"an attack that degrades recall without triggering anything is still a successful attack, so the
delta against the clean feed is where axis one lives." Axis two inherited the reasoning and not the
implementation.

Published figure before: 36% aggregate, up to 100% per class. After: **0%**, on the same recordings,
with no model called. The attacks achieved nothing measurable and never had; the metric was
reporting the pipeline's recall as suppression.

Two details worth keeping. The clean condition now has to run **before** the attacked one, because
the control is an input to scoring rather than a comparison afterwards — that ordering is the
semantics, and the end-to-end tests were rewritten to say so. And where no control exists the rate
is `None` rather than `0.0`, on DEC-150's reasoning: zero is the most misleading available value
because it is also the answer a correct run gives.

The sabotage half is weaker than the suppression half and the page says so. Suppression compares
expected keys, which are stable; sabotage compares counts, because a spurious finding carries a
per-run id and DEC-066 defines a cross-run identity only for findings that matched something. An
attack that swaps one false positive for another reads as no change. That is #695, and I would
rather ship the weaker comparison with its weakness named than improvise an identity inside an audit.

## What is still open

The three unmachinable shapes are the two that produced the worst defects, which is not a
coincidence. The obvious next pass is the one this audit did not do: take `threat-model.md`'s
"Enforced" rows one at a time and name, for each, the test that would fail if the enforcement were
removed. Where there is no such test, the row is a claim about a path nobody checked.
