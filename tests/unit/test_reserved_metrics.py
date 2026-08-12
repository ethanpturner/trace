"""The reserved truth-set metrics' matchers (#329).

Structural matching only, mirroring DEC-056's finding matcher: names and identifiers, never
wording. Each matcher is tested on the classification it returns, and the paired-question
exclusion — the one judgment in the set — is tested by name.
"""

from __future__ import annotations

from trace_ai.services.evaluation.matching import (
    match_context,
    match_expected_mappings,
    match_questions,
    match_threats,
)


def test_context_entries_match_by_the_truth_files_own_keys() -> None:
    expected = {
        "components": [{"name": "Callback Receiver"}, {"name": "Channel Poster"}],
        "actors": [{"name": "Payment provider"}],
        "assets": [{"name": "Order-status callbacks"}],
        "trust_boundaries": [{"name": "Public internet boundary"}],
        "data_flows": [
            {"source_component": "Callback Receiver", "destination_component": "Channel Poster"}
        ],
        "context_claims": [
            {"subject": "Callback Receiver", "predicate": "callback_authenticity"},
            {"subject": "system", "predicate": "deployment_model"},
        ],
    }
    outcome = match_context(
        expected,
        produced_names={
            "components": {"callback receiver"},
            "actors": {"payment provider"},
            "assets": {"order-status callbacks"},
            "trust_boundaries": set(),
        },
        produced_flows={("callback receiver", "channel poster")},
        produced_claims={("callback receiver", "callback_authenticity")},
    )
    assert outcome.matched_by_type == {
        "components": 1,
        "actors": 1,
        "assets": 1,
        "trust_boundaries": 0,
        "data_flows": 1,
        "context_claims": 1,
    }
    assert outcome.expected_count == 8
    assert outcome.matched_count == 5


def test_a_threat_matches_only_when_it_covers_every_must_reference() -> None:
    expected = [
        {
            "key": "THR-001",
            "must_reference": {"components": ["Bastion Server"], "assets": ["SSH keys"]},
        },
        {
            "key": "THR-002",
            "must_reference": {
                "components": ["Gather Images Application", "Jupyter Notebook"],
                "assets": ["Training images"],
            },
        },
    ]
    outcome = match_threats(
        expected,
        produced_references=[
            ({"bastion server"}, {"ssh keys", "bastion logs"}),
            ({"gather images application"}, {"training images"}),
        ],
    )
    # THR-002 requires both components; the produced threat names only one.
    assert outcome.matched_keys == ["THR-001"]
    assert outcome.missed_keys == ["THR-002"]


def test_a_mapping_matches_on_requirement_and_satisfaction_together() -> None:
    outcome = match_expected_mappings(
        [
            ("THR-001:req-WEBHOOK-001", "req-WEBHOOK-001", "unmet"),
            ("THR-002:req-WEBHOOK-002", "req-WEBHOOK-002", "unverified"),
            ("THR-002:req-DATA-001", "req-DATA-001", "satisfied"),
        ],
        produced={("req-WEBHOOK-001", "unmet"), ("req-DATA-001", "unverified")},
    )
    # The DATA-001 mapping exists with the wrong satisfaction: that is a miss, not a match.
    assert outcome.matched_keys == ["THR-001:req-WEBHOOK-001"]
    assert set(outcome.missed_keys) == {"THR-002:req-WEBHOOK-002", "THR-002:req-DATA-001"}


def test_questions_paired_to_a_gap_stay_out_of_the_denominator() -> None:
    expected = [
        {"key": "Q-01", "requirement_id": "req-DATA-001"},
        {"key": "Q-02", "requirement_id": "req-NET-001"},
    ]
    outcome = match_questions(
        expected,
        paired_keys={"Q-02"},
        produced_requirement_sets=[{"req-DATA-001"}],
    )
    assert outcome.matched_keys == ["Q-01"]
    assert outcome.missed_keys == []
    assert outcome.expected_count == 1


def test_a_question_can_match_through_its_own_text() -> None:
    outcome = match_questions(
        [{"key": "Q-01", "requirement_id": "req-AUTH-002"}],
        paired_keys=set(),
        produced_requirement_sets=[{"req-AUTH-002"}],
    )
    assert outcome.matched_keys == ["Q-01"]


def test_an_all_paired_question_set_is_vacuously_covered() -> None:
    outcome = match_questions(
        [{"key": "Q-01", "requirement_id": "req-DATA-001"}],
        paired_keys={"Q-01"},
        produced_requirement_sets=[],
    )
    assert outcome.expected_count == 0
    assert outcome.matched_keys == []
    assert outcome.missed_keys == []
