"""The deterministic half of scripts/triage.py.

The classifier model only proposes; everything that decides — the type:decision hard
rule, the deny-list clamp, tier-label bookkeeping, the body-hash staleness marker, and
the escalation bounds — is code, and this file pins it. Nothing here calls gh or a
model: the ruled paths are exactly the ones that must work without either.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT


def _load() -> ModuleType:
    path = PROJECT_ROOT / "scripts" / "triage.py"
    spec = importlib.util.spec_from_file_location("triage", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The dataclass machinery resolves string annotations through
    # sys.modules[cls.__module__], so the module must be registered before it executes.
    sys.modules["triage"] = module
    spec.loader.exec_module(module)
    return module


triage = _load()


def make_issue(body: str = "Add a docstring.", labels: frozenset[str] = frozenset()) -> Any:
    return triage.Issue(number=1, title="A small issue", body=body, labels=labels)


def test_type_decision_is_top_tier_without_a_model_call() -> None:
    issue = make_issue(labels=frozenset({"type:decision"}))
    result = triage.classify(issue, "unused-model")
    assert result.tier == triage.TOP_TIER
    assert result.classifier == "hard-rule"


@pytest.mark.parametrize("label", sorted(triage.DENY_LABELS))
def test_deny_labels_clamp_to_top_tier(label: str) -> None:
    issue = make_issue(labels=frozenset({label}))
    result = triage.classify(issue, "unused-model")
    assert result.tier == triage.TOP_TIER
    assert result.classifier in {"deny-clamp", "hard-rule"}


def test_deny_content_clamps_to_top_tier() -> None:
    issue = make_issue(body="Adjust the fence in services/context/input_package.py.")
    result = triage.classify(issue, "unused-model")
    assert result.tier == triage.TOP_TIER
    assert "excerpt fence" in result.rationale


def test_benign_body_trips_nothing() -> None:
    assert triage.deny_hits(make_issue()) == []


def test_rules_only_returns_none_for_an_unruled_issue() -> None:
    assert triage.classify(make_issue(), "unused-model", rules_only=True) is None


def test_tier_of_rejects_two_tier_labels() -> None:
    labels = frozenset({"model:1-routine", "model:2-standard"})
    with pytest.raises(triage.TriageError):
        triage.tier_of(labels)


def test_tier_of_reads_the_one_tier() -> None:
    assert triage.tier_of(frozenset({"model:2-standard", "type:feature"})) == 2
    assert triage.tier_of(frozenset({"type:feature"})) is None


def test_marker_comment_round_trips_the_body_hash() -> None:
    issue = make_issue(body="A body that will later move.")
    result = triage.Classification(2, "high", "specified", "claude-haiku-4-5")
    comment = triage.marker_comment_body(issue, result)
    assert triage.recorded_digest(comment) == triage.body_digest(issue.body)
    assert triage.recorded_digest(comment) != triage.body_digest(issue.body + " edited")


def test_tier_models_file_covers_every_tier() -> None:
    loaded = yaml.safe_load((PROJECT_ROOT / "scripts" / "tier-models.yaml").read_text())
    assert set(loaded["tiers"]) == set(triage.TIER_LABELS.values())


def test_escalate_refuses_above_the_top_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    issue = make_issue(labels=frozenset({triage.TIER_LABELS[triage.TOP_TIER]}))
    monkeypatch.setattr(triage, "fetch_issue", lambda number: issue)
    with pytest.raises(triage.TriageError, match="nothing above"):
        triage.escalate(1, "reason", None, apply=False)
