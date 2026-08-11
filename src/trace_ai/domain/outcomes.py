"""DEC-013's outcome table: what a satisfaction status and a validation status produce together.

The table is the single authority on whether an analysis becomes a finding, a question, a
documentation gap, or nothing. It is here, once, because three things consult it and a second
opinion is how the DEC-009 separation stops holding:

- `Finding` refuses a validation status no cell would produce a finding from.
- The Mapping Validation node applies the `unmet` half (DEC-046 records which half, and why the
  other half waits).
- Finding Consolidation applies the whole table.

**No cell produces a finding from the absence of documentation.** That sentence is DEC-013's and
it is the property `test_no_cell_produces_a_finding_from_silence` checks over the whole cross
product rather than over the rows somebody remembered to write down.

**The table is total.** Five satisfaction statuses times six validation statuses is thirty cells,
and every one resolves. A partial table would fail open: a pair nobody considered would raise, or
worse, fall through to a default that nobody chose.

**`not_evaluated` wins over everything.** DEC-013 states it as a row of its own — "any /
not_evaluated / No output. The mapping is incomplete, not negative" — and the ordering matters. A
mapping that was never evaluated is not a mapping that came out clean, and reading it as one would
turn an unfinished run into a passing one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from trace_ai.domain.control_mapping import SatisfactionStatus
from trace_ai.domain.enums import ValidationStatus

__all__ = [
    "FINDING_VALIDATION_STATUSES",
    "Outcome",
    "outcome_for",
]


class Outcome(StrEnum):
    """What DEC-013's table says to do with one mapping-and-assessment pair."""

    NO_OUTPUT = "no_output"
    """Nothing is produced. Either the requirement does not apply, or it is satisfied and the
    evidence carries that, or the mapping was never evaluated."""

    PROVISIONAL_FINDING = "provisional_finding"
    """The only outcome that produces a `Finding`, and it is reachable from exactly four of the
    thirty cells."""

    GAP_OR_QUESTION = "gap_or_question"
    """`unverified`: the expected result of assessing ordinary architecture documentation. Which
    of the two it becomes is `agent-design.md` section 16's reclassification rule — a question
    where the answer is obtainable and would change the assessment, a gap where the primary issue
    is inability to verify."""

    QUESTION_AFTER_DOWNGRADE = "question_after_downgrade"
    """The conclusion asserted more than its evidence carries. It is lowered to `unverified` and
    the resulting uncertainty is asked about."""

    DOWNGRADE_ONLY = "downgrade_only"
    """An `unmet` the evidence does not support. Lowered to `unverified` and recorded (DEC-046);
    nothing further is produced here, because what the documentation does establish is now the
    `unverified` case above."""


# The validation statuses under which a conclusion is carried by its evidence. DEC-013 pairs both
# of them with `partially_satisfied` and `unmet` to reach a provisional finding, and pairs every
# other status with a downgrade.
_EVIDENCE_CARRIES: Final[frozenset[ValidationStatus]] = frozenset(
    {ValidationStatus.SUPPORTED, ValidationStatus.PARTIALLY_SUPPORTED}
)

# The satisfaction statuses that assert a shortfall. Both reach a finding when the evidence
# carries them, and both are downgraded when it does not.
_ASSERTS_A_SHORTFALL: Final[frozenset[SatisfactionStatus]] = frozenset(
    {SatisfactionStatus.PARTIALLY_SATISFIED, SatisfactionStatus.UNMET}
)


def outcome_for(satisfaction: SatisfactionStatus, validation: ValidationStatus) -> Outcome:
    """One cell of DEC-013's table.

    The order of the branches is the order the table's rows have to be read in, and it is not
    interchangeable: `not_evaluated` is a row over `any` satisfaction status and has to be tested
    before the satisfaction status is looked at, or an unevaluated `unmet` would read as a
    downgrade rather than as an unfinished mapping.
    """
    if validation is ValidationStatus.NOT_EVALUATED:
        return Outcome.NO_OUTPUT

    if satisfaction is SatisfactionStatus.NOT_APPLICABLE:
        return Outcome.NO_OUTPUT

    if satisfaction is SatisfactionStatus.UNVERIFIED:
        return Outcome.GAP_OR_QUESTION

    if satisfaction is SatisfactionStatus.SATISFIED:
        if validation in _EVIDENCE_CARRIES:
            return Outcome.NO_OUTPUT
        return Outcome.QUESTION_AFTER_DOWNGRADE

    if satisfaction in _ASSERTS_A_SHORTFALL:
        if validation in _EVIDENCE_CARRIES:
            return Outcome.PROVISIONAL_FINDING
        if satisfaction is SatisfactionStatus.UNMET:
            return Outcome.DOWNGRADE_ONLY
        return Outcome.QUESTION_AFTER_DOWNGRADE

    raise AssertionError(  # pragma: no cover - the branches above are total over both enums
        f"DEC-013's table has no cell for {satisfaction.value!r} and {validation.value!r}"
    )


# The validation statuses a `Finding` may carry, derived from the table rather than restated.
#
# Deriving it is the point: `Finding` is not entitled to its own opinion about when a finding is
# reachable, and a hardcoded set here would be the second opinion this module exists to prevent.
# If DEC-013's table ever changes, this follows it.
FINDING_VALIDATION_STATUSES: Final[frozenset[ValidationStatus]] = frozenset(
    validation
    for validation in ValidationStatus
    for satisfaction in SatisfactionStatus
    if outcome_for(satisfaction, validation) is Outcome.PROVISIONAL_FINDING
)
