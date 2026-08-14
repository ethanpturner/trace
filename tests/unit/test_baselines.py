"""The baseline comparisons (#269, DEC-074): one call, same documents, scored by the same matcher.

The thesis these tests pin: on the two zero-finding scenarios, a generic single-pass baseline
produces the false-positive findings the catalog names — a local password policy where auth is
delegated, encryption where a managed platform provides it — while the structured baseline, given
the pipeline's discipline in one prompt, produces none. That contrast is the project's central
claim made measurable and re-runnable from the repository.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.proposals.baseline import BaselineFindings
from trace_ai.services.evaluation.baselines import BaselineError, run_baseline
from trace_ai.services.evaluation.registry import scenario as load_scenario

if TYPE_CHECKING:
    from pathlib import Path


def _recorded(slug: str, baseline: str) -> BaselineFindings:
    entry = load_scenario(slug)
    path = entry.recorded_dir / "baselines" / f"{baseline}.json"
    return BaselineFindings.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("slug", "spurious_expected"),
    [("oidc-portal", 2), ("managed-db-service", 1)],
)
def test_the_generic_baseline_invents_the_false_positives_trace_avoids(
    tmp_path: Path, slug: str, spurious_expected: int
) -> None:
    outcome = run_baseline(
        slug,
        "baseline-generic",
        label="test",
        response=_recorded(slug, "baseline-generic"),
        results_root=tmp_path / "results",
    )
    assert outcome.schema_valid
    assert outcome.matched == {}, "the truth set expects no findings here"
    assert len(outcome.spurious) == spurious_expected
    assert outcome.metrics["spurious_finding_count"] == float(spurious_expected)


@pytest.mark.parametrize("slug", ["oidc-portal", "managed-db-service"])
def test_the_structured_baseline_matches_trace_on_the_zero_finding_scenarios(
    tmp_path: Path, slug: str
) -> None:
    outcome = run_baseline(
        slug,
        "baseline-structured",
        label="test",
        response=_recorded(slug, "baseline-structured"),
        results_root=tmp_path / "results",
    )
    assert outcome.schema_valid
    assert outcome.spurious == []
    assert outcome.metrics["spurious_finding_count"] == 0.0


def test_a_baseline_matches_the_real_finding_where_there_is_one(tmp_path: Path) -> None:
    outcome = run_baseline(
        "unsigned-webhooks",
        "baseline-generic",
        label="test",
        response=_recorded("unsigned-webhooks", "baseline-generic"),
        results_root=tmp_path / "results",
    )
    assert list(outcome.matched) == ["FND-UW-01"]
    assert outcome.metrics["false_negative_rate"] == 0.0
    # The generic baseline still over-reports: the replay finding is spurious here.
    assert len(outcome.spurious) == 1


def test_the_baseline_feed_is_marked_non_authoritative(tmp_path: Path) -> None:
    outcome = run_baseline(
        "unsigned-webhooks",
        "baseline-structured",
        label="test",
        response=_recorded("unsigned-webhooks", "baseline-structured"),
        results_root=tmp_path / "results",
    )
    assert outcome.feed_path is not None
    feed = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert feed["authoritative"] is False
    assert feed["condition"] == "baseline-structured"
    assert feed["metrics"]["schema_validity_rate"]["value"] == 1.0


def test_an_unknown_baseline_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BaselineError, match="not a baseline"):
        run_baseline("oidc-portal", "baseline-nonsense", label="test", results_root=tmp_path)
