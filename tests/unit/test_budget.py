"""The one character budget every model-input package shares (WS10).

Before this module the packages counted their input four ways and two of them counted nothing;
none charged the response schema the prompt teaches, the single largest fixed input the extractor
sends. These pin the shared accounting: the schema is now priced, the fill preserves order so a
package that does not overflow is unmoved, and an overflow sheds the excerpts that do not fit and
names them rather than dropping them in silence.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from trace_ai.domain.proposals.context_extraction import ContextExtractionProposal
from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
from trace_ai.domain.proposals.mapping import MappingProposal
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.budget import BudgetOutcome, fill_untrusted, schema_overhead

PROFILE = resolve_profile("primary-development")

# The five agent schemas whose export the prompt substitutes into its body, and which the budget
# now charges. Every one is substantial -- the whole point is that "substantial and uncounted" was
# the bug.
_AGENT_SCHEMAS = [
    ContextExtractionProposal,
    ThreatAnalysisProposal,
    MappingProposal,
    EvidenceValidationProposal,
    CriticalReviewProposal,
]


@pytest.mark.parametrize("schema", _AGENT_SCHEMAS)
def test_schema_overhead_prices_every_agent_schema(schema: type) -> None:
    """The overhead the packages charge is real and non-trivial for every agent."""
    assert schema_overhead(schema) > 1_000


def test_fill_preserves_order_and_includes_all_when_it_fits() -> None:
    rendered = [("evd-001", "a" * 10), ("evd-002", "b" * 10), ("evd-003", "c" * 10)]

    outcome = fill_untrusted(rendered, profile=PROFILE, overhead_characters=0)

    assert outcome.included_ids == ("evd-001", "evd-002", "evd-003")
    assert outcome.excluded_ids == ()
    assert outcome.untrusted == "a" * 10 + "\n\n" + "b" * 10 + "\n\n" + "c" * 10
    assert outcome.used_characters == 30


def test_overflow_sheds_what_does_not_fit_and_names_it() -> None:
    tiny = replace(PROFILE, max_input_characters=25)
    rendered = [("evd-001", "a" * 10), ("evd-002", "b" * 10), ("evd-003", "c" * 10)]

    outcome = fill_untrusted(rendered, profile=tiny, overhead_characters=0)

    assert outcome.included_ids == ("evd-001", "evd-002")
    assert outcome.excluded_ids == ("evd-003",)
    assert outcome.used_characters == 20
    assert outcome.residual_characters == 25


def test_overhead_reduces_the_residual_the_excerpts_fill() -> None:
    tiny = replace(PROFILE, max_input_characters=100)
    rendered = [("evd-001", "a" * 40), ("evd-002", "b" * 40)]

    outcome = fill_untrusted(rendered, profile=tiny, overhead_characters=70)

    # Only 30 characters remain after overhead, so the first excerpt does not even fit.
    assert outcome.residual_characters == 30
    assert outcome.included_ids == ()
    assert outcome.excluded_ids == ("evd-001", "evd-002")


def test_metadata_carries_the_keys_every_package_records() -> None:
    outcome = fill_untrusted([("evd-001", "a" * 10)], profile=PROFILE, overhead_characters=5)

    assert outcome.metadata() == {
        "evidence_included": 1,
        "evidence_excluded": 0,
        "characters": 10,
        "overhead_characters": 5,
        "residual_characters": PROFILE.max_input_characters - 5,
        "budget_characters": PROFILE.max_input_characters,
    }


def test_outcome_is_frozen() -> None:
    outcome = BudgetOutcome(
        blocks=(),
        included_ids=(),
        excluded_ids=(),
        used_characters=0,
        residual_characters=0,
        overhead_characters=0,
        budget_characters=0,
    )
    with pytest.raises(AttributeError):
        outcome.used_characters = 1  # type: ignore[misc]
