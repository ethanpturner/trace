"""The capture stages (#482, DEC-091), run offline against a deterministic stand-in.

The stages are exercised exactly as `trace capture` drives them, with one substitution: the live
model is an injected `DeterministicModel` serving the committed ForgeFlow recording, so no test
spends a call. The scenario is a synthetic copy under tmp_path — a capture writes a staging
directory beside the scenario, and a test must never write into `demo/` or `data/`.

The round trip is the load-bearing assertion: three stages driven by the committed decision
files, from the committed responses, produce byte-for-byte the committed report hash. That is
the promotion criterion the capture flow exists to satisfy.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.infrastructure.model.fake import DeterministicModel
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.services.evaluation.capture import (
    CaptureError,
    CaptureRefusedError,
    capture_data_root,
    capture_dir,
    stage_extract,
    stage_reason,
    stage_report,
)
from trace_ai.services.evaluation.registry import Scenario

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow"
PROFILE = "primary-development"


def _scenario(tmp_path: Path) -> Scenario:
    root = tmp_path / "scenario"
    shutil.copytree(FORGEFLOW / "input", root / "input")
    return Scenario(slug="capture-test", name="ForgeFlow", path=root, status="authored")


def _recorded(stage: str) -> DeterministicModel:
    paths = sorted((FORGEFLOW / "recorded" / stage).glob("[0-9]*.json"))
    return DeterministicModel(list(load_recorded_responses(paths)))


def _run_extract(scenario: Scenario, tmp_path: Path) -> None:
    stage_extract(
        scenario,
        profile_name=PROFILE,
        live=_recorded("extraction"),
        data_root=tmp_path / "capture-data",
    )


def _run_reason(scenario: Scenario, tmp_path: Path) -> None:
    shutil.copy(
        FORGEFLOW / "recorded" / "decisions-context.yaml",
        capture_dir(scenario) / "decisions-context.yaml",
    )
    stage_reason(
        scenario,
        profile_name=PROFILE,
        live=_recorded("reasoning"),
        data_root=tmp_path / "capture-data",
    )


def _run_report(scenario: Scenario, tmp_path: Path) -> None:
    shutil.copy(
        FORGEFLOW / "recorded" / "decisions-findings.yaml",
        capture_dir(scenario) / "decisions-findings.yaml",
    )
    stage_report(
        scenario,
        profile_name=PROFILE,
        live=_recorded("report"),
        data_root=tmp_path / "capture-data",
    )


def test_the_three_stages_round_trip_to_the_committed_report_hash(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    _run_extract(scenario, tmp_path)
    staging = capture_dir(scenario)

    assert (staging / "assessment-id.txt").is_file()
    assert (staging / "review-export.yaml").is_file()
    envelopes = sorted(staging.glob("[0-9]*.json"))
    assert envelopes, "the extract stage records the responses it consumed"
    first = json.loads(envelopes[0].read_text(encoding="utf-8"))
    assert set(first) == {"schema", "usage", "response"}
    assert first["schema"] == "ContextExtractionProposal"

    _run_reason(scenario, tmp_path)
    assert (staging / "findings-export.yaml").is_file()

    _run_report(scenario, tmp_path)
    committed = (FORGEFLOW / "recorded" / "report-hash.txt").read_text(encoding="utf-8")
    assert (staging / "report-hash.txt").read_text(encoding="utf-8") == committed


def test_each_stage_refuses_to_run_twice(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    _run_extract(scenario, tmp_path)
    with pytest.raises(CaptureRefusedError, match="re-spend"):
        _run_extract(scenario, tmp_path)

    _run_reason(scenario, tmp_path)
    with pytest.raises(CaptureRefusedError, match="already ran"):
        _run_reason(scenario, tmp_path)

    _run_report(scenario, tmp_path)
    with pytest.raises(CaptureRefusedError, match="already ran"):
        _run_report(scenario, tmp_path)


def test_reason_requires_an_authored_decisions_file(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    _run_extract(scenario, tmp_path)
    with pytest.raises(CaptureError, match=r"decisions-context\.yaml"):
        stage_reason(
            scenario,
            profile_name=PROFILE,
            live=_recorded("reasoning"),
            data_root=tmp_path / "capture-data",
        )


def test_the_fake_profile_is_refused_before_any_side_effect(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    with pytest.raises(CaptureError, match="fake"):
        stage_extract(scenario, profile_name="offline-fake", data_root=tmp_path / "capture-data")
    assert not capture_dir(scenario).exists()
    assert not (tmp_path / "capture-data").exists()


def test_the_default_data_root_is_named_for_the_scenario() -> None:
    scenario = Scenario(slug="tiny", name="Tiny", path=PROJECT_ROOT, status="authored")
    assert capture_data_root(scenario) == PROJECT_ROOT / "data" / "capture-tiny"
