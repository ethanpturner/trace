"""The evaluation harness (#266, DEC-073): registry-driven, offline, ablation-aware, diffable.

The end-to-end tests replay the committed ForgeFlow recording through the harness with no
provider credential — the same recording the replay script and the demo tape use — and assert the
DEC-073 properties: the run went through the ordinary pipeline, the metrics landed in both homes,
the feed carries the per-item sets, and an ablated run is marked non-authoritative from birth.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.evaluation_result import EvaluationResult
from trace_ai.domain.execution import ExecutionRecord, ExecutionType, WorkflowRun
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evaluation.harness import HarnessError, diff_feeds, run_scenario
from trace_ai.services.evaluation.registry import (
    UnknownScenarioError,
    load_registry,
    scenario,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


# ------------------------------------------------------------------------------------------
# The registry
# ------------------------------------------------------------------------------------------


def test_the_registry_parses_and_carries_forgeflow() -> None:
    scenarios = {entry.slug: entry for entry in load_registry()}
    assert "forgeflow" in scenarios
    assert scenarios["forgeflow"].has_outcome_truth
    assert scenarios["forgeflow"].recorded_dir.is_dir()


def test_an_unknown_slug_is_refused_with_the_known_list() -> None:
    with pytest.raises(UnknownScenarioError, match="forgeflow"):
        scenario("no-such-scenario")


def test_a_scenario_without_a_recording_is_refused_by_name(tmp_path: Path) -> None:
    """Silent skipping is the failure mode; the refusal names the scenario and the reason."""
    with pytest.raises(HarnessError, match=r"husky-ai.*no recorded"):
        run_scenario("husky-ai", data_root=tmp_path, label="test")


# ------------------------------------------------------------------------------------------
# The ordinary (clean) harness run
# ------------------------------------------------------------------------------------------


def test_forgeflow_replays_through_the_harness_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    outcome = run_scenario(
        "forgeflow",
        data_root=tmp_path / "work",
        label="test",
        results_root=tmp_path / "results",
    )

    assert outcome.completed
    assert outcome.ablations == []

    # Both result homes: EvaluationResult rows with the assessment, and the derived feed.
    with AssessmentStore.at_root(tmp_path / "work") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "work")
        handle = service.handle(outcome.assessment_id)
        names = {
            result.metric_name
            for result in handle.objects.list(EvaluationResult)
            if result.workflow_run_id == outcome.workflow_run_id
        }
        assert "finding_evidence_coverage" in names, "the pipeline's own metrics are kept"
        assert "false_negative_rate" in names, "the harness topped up the benchmark metrics"
        assert "documentation_gap_precision" in names

    assert outcome.feed_path is not None
    feed = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert outcome.feed_path == tmp_path / "results" / "forgeflow" / "clean" / "test.json"
    assert feed["scenario"] == "forgeflow"
    assert feed["authoritative"] is True
    assert feed["metrics"]["false_negative_rate"]["evaluator_type"] == "benchmark"

    items = feed["items"]["findings"]
    assert set(items) == {"matched", "missed", "spurious", "fingerprints"}
    classified = len(items["matched"]) + len(items["missed"])
    assert classified > 0, "every expected finding is classified, not merely counted"
    for prints in items["fingerprints"].values():
        assert all(fingerprint.startswith("sha256:") for fingerprint in prints)


def test_an_ablated_run_is_marked_from_birth_and_substitutes_the_nodes(
    tmp_path: Path,
) -> None:
    outcome = run_scenario(
        "forgeflow",
        data_root=tmp_path / "work",
        label="ablated",
        ablations=["no-critical-review"],
        results_root=tmp_path / "results",
    )

    assert outcome.completed
    assert outcome.ablations == ["no-critical-review"]

    with AssessmentStore.at_root(tmp_path / "work") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "work")
        handle = service.handle(outcome.assessment_id)
        run = handle.objects.get(WorkflowRun, outcome.workflow_run_id)
        assert run.ablations == ["no-critical-review"]
        assert not run.is_authoritative

        critique_records = [
            record
            for record in handle.objects.list(ExecutionRecord)
            if record.workflow_run_id == run.id
            and record.node_name in ("critical-review", "critique-validation")
        ]
        assert critique_records, "the declared names still executed — as stand-ins"
        assert all(
            record.execution_type is ExecutionType.DETERMINISTIC for record in critique_records
        )
        assert all(
            record.metadata.get("ablated_by") == "no-critical-review" for record in critique_records
        )

    assert outcome.feed_path is not None
    feed = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert feed["authoritative"] is False
    assert feed["ablations"] == ["no-critical-review"]


def test_an_unknown_ablation_is_refused_with_the_family_named(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"closed.*no-context-approval"):
        run_scenario(
            "forgeflow",
            data_root=tmp_path,
            label="bad",
            ablations=["no-everything"],
            results_root=tmp_path / "results",
        )


# ------------------------------------------------------------------------------------------
# The per-item run diff (DEC-073)
# ------------------------------------------------------------------------------------------


def _feed(path: Path, *, label: str, findings: Mapping[str, object]) -> Path:
    payload = {
        "feed_version": "1",
        "scenario": "forgeflow",
        "condition": "clean",
        "label": label,
        "items": {"findings": findings},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_the_diff_classifies_each_expected_item(tmp_path: Path) -> None:
    """Two runs can hold the same rate while disagreeing per item; the diff says where."""
    prior = _feed(
        tmp_path / "prior.json",
        label="prior",
        findings={
            "matched": {"FND-A": ["fnd-001"], "FND-B": ["fnd-002"], "FND-C": ["fnd-003"]},
            "missed": ["FND-D", "FND-E"],
            "spurious": ["fnd-009"],
            "fingerprints": {
                "FND-A": ["sha256:aaa"],
                "FND-B": ["sha256:bbb"],
                "FND-C": ["sha256:ccc"],
            },
        },
    )
    current = _feed(
        tmp_path / "current.json",
        label="current",
        findings={
            "matched": {"FND-A": ["fnd-001"], "FND-B": ["fnd-005"], "FND-E": ["fnd-006"]},
            "missed": ["FND-C", "FND-D"],
            "spurious": ["fnd-009", "fnd-010"],
            "fingerprints": {
                "FND-A": ["sha256:aaa"],
                "FND-B": ["sha256:changed"],
                "FND-E": ["sha256:eee"],
            },
        },
    )

    diff = diff_feeds(current, prior)

    assert diff.matched == ["FND-A"], "same expectation, same DEC-066 identity"
    assert diff.changed == ["FND-B"], "same score concealing a different conclusion"
    assert diff.regressed == ["FND-C"]
    assert diff.missed == ["FND-C", "FND-D"]
    assert diff.recovered == ["FND-E"]
    assert diff.new_spurious == ["fnd-010"]
    assert not diff.clean


def test_a_diff_across_scenarios_is_refused(tmp_path: Path) -> None:
    prior = _feed(tmp_path / "p.json", label="p", findings={})
    current_payload = json.loads(prior.read_text(encoding="utf-8")) | {"scenario": "husky-ai"}
    current = tmp_path / "c.json"
    current.write_text(json.dumps(current_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="different scenarios"):
        diff_feeds(current, prior)


def test_a_run_with_no_prior_run_status_change_diffs_clean(tmp_path: Path) -> None:
    same = {
        "matched": {"FND-A": ["fnd-001"]},
        "missed": [],
        "spurious": [],
        "fingerprints": {"FND-A": ["sha256:aaa"]},
    }
    prior = _feed(tmp_path / "prior.json", label="prior", findings=same)
    current = _feed(tmp_path / "current.json", label="current", findings=same)

    assert diff_feeds(current, prior).clean
