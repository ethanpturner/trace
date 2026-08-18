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
    rehearsing = capture_data_root(scenario, rehearsal=True)
    assert rehearsing == PROJECT_ROOT / "data" / "capture-rehearsal-tiny"


# ------------------------------------------------------------------------------------------
# The rehearsal (#534): the same three stages, the money removed, nothing promotable
# ------------------------------------------------------------------------------------------


def _run_rehearsal_stage(scenario: Scenario, tmp_path: Path, stage: str) -> None:
    if stage == "extract":
        stage_extract(
            scenario,
            profile_name=PROFILE,
            live=_recorded("extraction"),
            data_root=tmp_path / "rehearsal-data",
            rehearsal=True,
        )
    elif stage == "reason":
        shutil.copy(
            FORGEFLOW / "recorded" / "decisions-context.yaml",
            capture_dir(scenario, rehearsal=True) / "decisions-context.yaml",
        )
        stage_reason(
            scenario,
            profile_name=PROFILE,
            live=_recorded("reasoning"),
            data_root=tmp_path / "rehearsal-data",
            rehearsal=True,
        )
    else:
        shutil.copy(
            FORGEFLOW / "recorded" / "decisions-findings.yaml",
            capture_dir(scenario, rehearsal=True) / "decisions-findings.yaml",
        )
        stage_report(
            scenario,
            profile_name=PROFILE,
            live=_recorded("report"),
            data_root=tmp_path / "rehearsal-data",
            rehearsal=True,
        )


def test_the_rehearsal_round_trips_offline_into_its_own_marked_directory(tmp_path: Path) -> None:
    """The whole three-stage flow rehearses without a provider, staging apart from a real
    capture, every envelope marked, and the committed report hash still reproduced — the
    mechanics are the real ones, only the money is missing."""
    scenario = _scenario(tmp_path)
    _run_rehearsal_stage(scenario, tmp_path, "extract")

    staging = capture_dir(scenario, rehearsal=True)
    assert staging.name == "capture-rehearsal"
    assert not capture_dir(scenario).exists(), "a rehearsal must not touch the real staging"
    assert (staging / "REHEARSAL").is_file()
    envelopes = sorted(staging.glob("[0-9]*.json"))
    assert envelopes
    first = json.loads(envelopes[0].read_text(encoding="utf-8"))
    assert first["rehearsal"] is True

    _run_rehearsal_stage(scenario, tmp_path, "reason")
    _run_rehearsal_stage(scenario, tmp_path, "report")
    committed = (FORGEFLOW / "recorded" / "report-hash.txt").read_text(encoding="utf-8")
    assert (staging / "report-hash.txt").read_text(encoding="utf-8") == committed


def test_a_rehearsal_artifact_is_refused_as_a_recording(tmp_path: Path) -> None:
    """The structural half of the promotion guard: every reader of a recording refuses a
    rehearsal envelope, so a hand-copied rehearsal file cannot enter recorded/ quietly."""
    scenario = _scenario(tmp_path)
    _run_rehearsal_stage(scenario, tmp_path, "extract")
    staged = sorted(capture_dir(scenario, rehearsal=True).glob("[0-9]*.json"))

    with pytest.raises(ValueError, match="rehearsal"):
        load_recorded_responses(staged)

    replayable = load_recorded_responses(staged, allow_rehearsal=True)
    assert replayable, "the rehearsal's own resume path still reads its staging"


def test_a_rehearsal_without_a_model_is_refused_before_any_side_effect(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    with pytest.raises(CaptureError, match="rehearsal"):
        stage_extract(
            scenario,
            profile_name=PROFILE,
            data_root=tmp_path / "rehearsal-data",
            rehearsal=True,
        )
    assert not capture_dir(scenario, rehearsal=True).exists()
    assert not (tmp_path / "rehearsal-data").exists()


def test_a_scenario_catalog_pin_reaches_the_assessment(tmp_path: Path) -> None:
    """DEC-098: the registry's catalog_version pins what the scenario's assessments are
    assessed against; absent means the loader's current version, exactly as before."""
    from trace_ai.domain.assessment import Assessment

    scenario = _scenario(tmp_path)
    pinned = Scenario(
        slug=scenario.slug,
        name=scenario.name,
        path=scenario.path,
        status=scenario.status,
        catalog_version="0.2",
    )
    stage_extract(
        pinned,
        profile_name=PROFILE,
        live=_recorded("extraction"),
        data_root=tmp_path / "capture-data",
    )
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService

    with AssessmentStore.at_root(tmp_path / "capture-data") as store:
        handle = AssessmentService(store, artifact_root=tmp_path / "capture-data").handle("asm-001")
        assessment = handle.objects.get(Assessment, "asm-001")
    assert assessment.requirements_catalog_version == "0.2"


def test_baseline_capture_records_the_replayable_shape_and_scores_it(tmp_path: Path) -> None:
    """DEC-100: one call, one staged file, shaped exactly as recorded/baselines/ holds it —
    and scored against the truth set immediately, because a recording nobody judged is a
    recording nobody can trust."""
    import json

    from trace_ai.domain.proposals.baseline import BaselineFindings
    from trace_ai.services.evaluation.capture import stage_baseline

    entry = Scenario(
        slug="rag-support-bot",
        name="Relay Answers",
        path=PROJECT_ROOT / "benchmarks" / "rag-support-bot",
        status="authored",
        catalog_version="0.2",
    )
    committed = json.loads(
        (entry.recorded_dir / "baselines" / "baseline-structured.json").read_text(encoding="utf-8")
    )
    response = BaselineFindings.model_validate(committed)
    staged = entry.path / "capture" / "baselines" / "baseline-structured.json"
    try:
        stage_baseline(
            entry,
            baseline="structured",
            profile_name="primary-development",
            response=response,
        )
        assert staged.is_file()
        assert json.loads(staged.read_text(encoding="utf-8")) == committed

        with pytest.raises(CaptureRefusedError, match="re-spend"):
            stage_baseline(
                entry,
                baseline="structured",
                profile_name="primary-development",
                response=response,
            )
    finally:
        import shutil

        shutil.rmtree(entry.path / "capture", ignore_errors=True)


def test_baseline_capture_refuses_the_fake_profile(tmp_path: Path) -> None:
    from trace_ai.services.evaluation.capture import stage_baseline

    entry = Scenario(
        slug="rag-support-bot",
        name="Relay Answers",
        path=PROJECT_ROOT / "benchmarks" / "rag-support-bot",
        status="authored",
        catalog_version="0.2",
    )
    with pytest.raises(CaptureError, match="fake"):
        stage_baseline(entry, baseline="structured", profile_name="offline-fake")
    assert not (entry.path / "capture").exists()
