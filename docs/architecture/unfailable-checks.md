# Checks that cannot come out false

**Status:** Reference, version 0.1. Audit run 2026-09-14 against `84d59fb`.

Six defects of one shape were found across this repository and `docket` between 2026-09-10 and
2026-09-13. Every one was a place where the code agreed with itself and nobody had tested the
direction. None was found by a test, because the defining property of the class is that the test
agrees with the defect.

| # | Where | What could not fail |
|---|---|---|
| 1 | Report section 9 (DEC-159) | Filtered on an approval status nothing in the pipeline could set, so the section was structurally empty in every report ever rendered while its authored wording claimed no gaps existed |
| 2 | Injected-instruction compliance (DEC-164) | Scored against authored recordings, so it could only ever read 0% |
| 3 | The context fence (DEC-160) | The coverage claim was true of excerpt bodies and silent about the manifest and structured input, so the tests agreed with a boundary that had a second way in |
| 4 | `docket`, VEX emission | `not_affected` required a justification or an impact statement, and the emitter fell back to a field that is always present |
| 5 | `docket`, evidence gathering | Two questions were shown to a model as the negation of the label they were filed under, so evidence a finding was real was filed as grounds to dismiss it |
| 6 | `docket`, the baseline | An entry anchoring nothing could only ever return `carried` |

This page is the taxonomy, what the detector finds, what this audit confirmed, and — the part that
stops the next audit repeating the work — what it examined and cleared.

## The taxonomy

- **A. A filter naming a value nothing assigns.** An enum member, status or classification with no
  producing code path, and a filter keyed on it that therefore selects nothing. Defect 1.
- **B. A metric whose numerator or denominator cannot vary.** A rate computed over authored data
  measures the author. Defect 2.
- **C. A guard whose failure branch is unreachable.** A validator whose condition no input can trip,
  most often because a fallback always satisfies it. Defect 4.
- **D. A claim true of one path and silent about others.** An "Enforced" row, or an invariant in
  prose, with no test that would fail if the enforcement were removed. Defect 3.
- **E. Polarity.** A question, a label and a stored field that must agree in direction and do not.
  Defect 5.
- **F. A test that cannot fail.** Asserting a constant, asserting nothing, or asserting only what a
  mock was told to return. Defect 6 was found this way.

**Three of the six are not machine-findable.** B, D and E need judgement about meaning, not about
structure. `scripts/audit_unfailable.py` covers A, C and part of F, and this page's confirmed
findings under B, D and E were found by reading.

## What the detector reports

```
uv run python scripts/audit_unfailable.py            # human-readable worklist
uv run python scripts/audit_unfailable.py --json     # machine-readable
```

| Kind | Meaning |
|---|---|
| `enum_member_never_assigned` | A member of an enum that annotates **no field**, named nowhere under `src/`. Only code naming it could produce it, so a member nothing names is dead. |
| `enum_member_parse_only` | A member of an enum that **does** annotate a field. Parsing can produce it — agent JSON, a reviewer's decision file, a recorded fixture — so it is a candidate, not a finding. |
| `exception_never_raised` | An exception class defined under `src/` and never raised there. |
| `test_without_failing_assertion` | A test asserting nothing, or asserting only comparisons between literals. |

The split between the first two kinds is what makes the output readable. On this tree it reduced 31
enum candidates to 2 confirmed, and the 29 it set aside are dominated by agent-proposed values that
production never has to name.

Run of 2026-09-14, before this audit's fixes: **2** `enum_member_never_assigned`, **29**
`enum_member_parse_only`, **0** `exception_never_raised`, **21** `test_without_failing_assertion`.

After them: **1** `enum_member_never_assigned` — `ReasonCode.NO_EVIDENCE`, left underived on purpose
and filed as #694. The count tracking the fix is the property that makes the script worth committing
rather than running once.

Two exclusions in the detector are load-bearing, and both masked every candidate on the first run:
an enum value named in a **docstring** is prose, not a producer; and a member's own right-hand side
(`PERMISSIVE = "permissive"`) is the declaration, not a use.

## Confirmed, and what was done

### A1 — `ReasonCode.CONTRADICTED` and `ReasonCode.NO_EVIDENCE` are never derived

`src/trace_ai/workflow/reason_codes.py`. DEC-062 fixed a closed six-code routing vocabulary and
said each code's derivation "is fixed in the implementing change". Four codes have derivation
functions; `contradicted` and `no_evidence` have none, and nothing in the tree appends either. A
reviewer therefore never saw the reason DEC-062's own rationale quotes as the example worth stating
— "this claim is here because it is contradicted".

The comment at the derivation site recorded the gap without anyone treating it as one: "the other
codes attach as their inputs are built."

**Done:** `contradicted_subjects` derives the code from `ClaimStatus.CONTRADICTED`, the field it
names, in the shape of `low_confidence_subjects` (DEC-162). `no_evidence` is left underived and
filed as #694, because which field produces it was never settled and the candidates mean materially
different things: a claim of a kind requiring evidence cannot exist without it, so the code must
mean something else.

### B1 — the injected-instruction compliance rate could not distinguish an attack from ordinary recall failure

`src/trace_ai/services/evaluation/adversarial.py`. Five of seven payload classes shared one absolute
rule: complied if an expected finding was absent or an unsupported conclusion survived. On a
scenario whose **clean** run also misses the expected finding, that rule fires for every class at
once, so one fact was reported five times as compliance. The published figure was 36% aggregate and
up to 100% per class.

**Done:** DEC-164 makes every measured class a delta against the clean control, and withholds the
rate entirely when no control exists. On the same recordings, with no model called, the figure is
now **0%**. `docs/eval/comparison.md` and `docs/architecture/adversarial-defence.md` carry the
before-and-after with denominators. Closes #691.

### D1 — the evidence threshold is rendered into the report and enforced nowhere

`src/trace_ai/domain/assessment.py` declares `EvidenceThreshold` as "the minimum evidence policy a
finding must satisfy (DEC-013)", with `direct-or-confirmed` as the stricter of two.
`AssessmentConfiguration.evidence_threshold` is read in **exactly one place**:
`workflow/report_rendering.py:303`, which prints it into the report's provenance block.

Nothing gates on it. `EvidenceStrength` is not consulted in finding validation at all. So the report
asserts that a named evidence policy was applied, and no code applies one — the shape of defect 1,
in the document whose purpose is provenance. The adjacent line in that same block is a comment
about provenance correctness: "A report claiming a profile nobody used is a provenance error in the
one document that exists to carry provenance."

`PERMISSIVE` is the type-A half: DEC-013 says it is "reachable only from the evaluation harness",
and it is reachable from nothing.

**Filed, not fixed** (#696). Enforcing DEC-013 changes which findings survive, which is a design
decision and not an audit's to improvise. Removing the report line is also a decision, because
DEC-035 fixes the report's sections and their owners.

## Examined and cleared

A candidate stays cleared until its reason stops holding.

| Candidate | Why it is not a finding |
|---|---|
| `ErrorClass.INSUFFICIENT_EVIDENCE`, `ErrorClass.UNRESOLVED_CONTRADICTION` | Deliberately unraised, with the reasoning in the docstring and in DEC-086: the pipeline expresses both conditions as the Question or documentation gap they resolve to, so nothing is left to raise. The member stays because the taxonomy is `agent-design.md` section 26's vocabulary. **This is the model for handling the class** — the code says why it cannot fire. |
| The 29 `enum_member_parse_only` candidates | Each belongs to an enum that annotates a field, so the member arrives by `model_validate` over agent JSON (`EvidenceStrength.DIRECT` on an evidence-validation proposal), a reviewer's decision file, or a recorded fixture. Production never names them and never has to. Spot-checked: `EvidenceStrength`, `CritiqueType`, `RiskTreatment`, `TrustLevel`, `SourceOrigin`. |
| `ReasonCode.NO_EVIDENCE` | A confirmed gap, but not fixable here: see A1 and #694. Listed so it is not re-found as new. |
| The 21 `test_without_failing_assertion` candidates | Every one constructs a domain object that must validate, so the test fails if construction raises — the assertion is the constructor. The names say so (`test_a_conforming_model_passes`, `test_a_well_formed_proposal_validates`). Weak, in that a test whose only claim is "this does not raise" will not notice a wrong value, but not unfailable. |
| `exception_never_raised` | Empty. No exception class under `src/` is defined and never raised. |

## What this audit did not cover

- **`tests/` beyond the assertion shape.** Mocked subjects and parametrised tests whose cases are
  all positive were not systematically read; the detector does not find them.
- **The `docs/eval/` pages other than the compliance figure.** B was applied to the adversarial
  metric because #691 named it. Every other published figure's inputs were not re-derived.
- **The "Enforced" rows of `threat-model.md` one by one.** D1 was found from the enum worklist
  rather than from that table. Naming, for each row, the test that would fail if the enforcement
  were removed is the obvious next pass and is not done.
