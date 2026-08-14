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


def test_every_scenario_declares_a_category_and_the_stage_5_list_is_covered() -> None:
    """Issue #328: the registry states which roadmap Stage 5 categories are covered.

    Prompt injection is deliberately absent from the category values: it is carried by the
    unsigned-webhooks adversarial *condition* (M8), not by a scenario of its own.
    """
    scenarios = load_registry()
    assert all(entry.category for entry in scenarios)
    covered = {entry.category for entry in scenarios}
    assert {
        "delegated-authentication",
        "managed-platform-controls",
        "genuine-missing-controls",
        "contradictory-documentation",
        "missing-documentation",
        "ai-service-risks",
        "third-party-integrations",
        "duplicate-threats",
        "large-architecture-input",
    } <= covered


def test_an_unknown_slug_is_refused_with_the_known_list() -> None:
    with pytest.raises(UnknownScenarioError, match="forgeflow"):
        scenario("no-such-scenario")


def test_a_scenario_without_a_recording_is_refused_by_name(tmp_path: Path) -> None:
    """Silent skipping is the failure mode; the refusal names the scenario and the reason.

    Every registered scenario now carries a recording (#326, #327), so the unrecorded one is
    fabricated: a registry whose scenario directory has input and truth but no recorded/.
    """
    scenario_dir = tmp_path / "bench" / "unrecorded"
    (scenario_dir / "input").mkdir(parents=True)
    (scenario_dir / "input" / "overview.md").write_text("# Overview\n", encoding="utf-8")
    (scenario_dir / "expected").mkdir()
    registry = tmp_path / "registry" / "scenarios.yaml"
    registry.parent.mkdir()
    registry.write_text(
        "registry_version: '1.0'\n"
        "scenarios:\n"
        "  - slug: unrecorded\n"
        "    name: Unrecorded\n"
        "    path: bench/unrecorded\n"
        "    status: expected-outputs-authored\n",
        encoding="utf-8",
    )
    with pytest.raises(HarnessError, match=r"unrecorded.*no recording"):
        run_scenario(
            "unrecorded", data_root=tmp_path / "data", label="test", registry_path=registry
        )


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


@pytest.mark.parametrize(
    ("slug", "expected_key", "expected_requirement"),
    [
        ("unsigned-webhooks", "FND-UW-01", "req-WEBHOOK-001"),
        ("contradictory-docs", "FND-CD-01", "req-DATA-002"),
    ],
)
def test_a_second_scenario_replays_and_scores_its_finding(
    tmp_path: Path, slug: str, expected_key: str, expected_requirement: str
) -> None:
    """The multi-scenario harness: two authored #268 scenarios replay offline and their one
    finding matches its truth entry with nothing spurious."""
    outcome = run_scenario(
        slug, data_root=tmp_path / "work", label="test", results_root=tmp_path / "results"
    )
    assert outcome.completed
    assert outcome.feed_path is not None
    feed = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    findings = feed["items"]["findings"]
    assert list(findings["matched"]) == [expected_key]
    assert findings["missed"] == []
    assert findings["spurious"] == []
    assert feed["metrics"]["false_negative_rate"]["value"] == 0.0


def test_the_adversarial_condition_loads_the_poisoned_doc_and_the_finding_survives(
    tmp_path: Path,
) -> None:
    """DEC-075: a condition is a real variant, not a feed label. The adversarial condition adds a
    poisoned document to the input, and a correct run's finding survives the attack (axis one)."""
    from trace_ai.services.evaluation.registry import scenario as load_scenario

    entry = load_scenario("unsigned-webhooks")
    assert "adversarial" in entry.conditions
    clean_docs = {p.name for p in entry.input_documents("clean")}
    adversarial_docs = {p.name for p in entry.input_documents("adversarial")}
    assert adversarial_docs - clean_docs == {"team-notes.md"}, "the overlay adds the poisoned doc"

    outcome = run_scenario(
        "unsigned-webhooks",
        data_root=tmp_path / "work",
        label="adv",
        condition="adversarial",
        results_root=tmp_path / "results",
    )
    assert outcome.completed
    assert outcome.feed_path is not None
    feed = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert list(feed["items"]["findings"]["matched"]) == ["FND-UW-01"], (
        "the attack did not suppress it"
    )
    assert feed["metrics"]["false_negative_rate"]["value"] == 0.0


def test_a_clean_run_ignores_a_condition_it_does_not_name(tmp_path: Path) -> None:
    """The clean condition sees only the base input; the poisoned doc is the adversarial overlay."""
    from trace_ai.services.evaluation.registry import scenario as load_scenario

    entry = load_scenario("unsigned-webhooks")
    assert all(p.name != "team-notes.md" for p in entry.input_documents("clean"))


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


def test_model_call_count_matches_the_responses_the_recording_supplies(tmp_path: Path) -> None:
    """#388's regression pin. The metric read `run.total_model_calls` — a snapshot written at
    the last pause, while the metric is computed inside the final segment, before complete()
    writes the closing counters — so the final segment's calls were missing. oidc-portal is the
    worst case the issue observed: zero findings means the finding checkpoint never pauses, so
    everything after context approval is one segment and the stale row said 1 of its 8 calls.
    The count must equal the recorded responses the run consumed, derived from the recording
    itself so authoring a scenario cannot silently diverge from this test."""
    entry = next(item for item in load_registry() if item.slug == "oidc-portal")
    supplied = len(list(entry.recorded_dir_for("clean").glob("*.json")))
    assert supplied == 8, "the scenario's recording changed; re-derive this test's expectation"

    outcome = run_scenario(
        "oidc-portal",
        data_root=tmp_path / "work",
        label="calls",
        results_root=tmp_path / "results",
    )
    assert outcome.feed_path is not None
    feed = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert feed["metrics"]["model_call_count"]["value"] == float(supplied)
