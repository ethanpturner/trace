"""The benchmark package manifest (DEC-146, #574): assembled from the corpus, checked against it.

What these pin is that the manifest cannot quietly describe a corpus that is not there. The
committed file matches what the generator produces; a changed file moves the digest that covers it;
a renamed file moves it too, because the manifest describes an inventory rather than a bag of
bytes; and the model attribution comes from the recorded envelopes rather than from prose (DEC-136),
so an authored recording attributes to nothing instead of borrowing a name.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.services.evaluation.package import (
    MANIFEST_PATH,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    build_manifest,
    render_manifest,
)
from trace_ai.services.evaluation.registry import Scenario, load_registry

if TYPE_CHECKING:
    from pathlib import Path


def _entry(manifest: dict[str, Any], slug: str) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = manifest["scenarios"]
    return next(entry for entry in scenarios if entry["slug"] == slug)


def test_the_committed_manifest_matches_the_corpus() -> None:
    """The check CI runs: regenerating the manifest reproduces the committed bytes.

    This is the whole mechanism. A promoted capture that does not regenerate leaves the package
    describing a corpus that no longer exists, and this fails rather than letting it ship.
    """
    assert MANIFEST_PATH.read_text(encoding="utf-8") == render_manifest(), (
        "the committed benchmark manifest is stale; run "
        "`uv run python scripts/build_benchmark_manifest.py`"
    )


def test_the_manifest_covers_every_registered_scenario() -> None:
    manifest = build_manifest()
    package: dict[str, Any] = manifest["package"]
    registered = [entry.slug for entry in load_registry()]

    scenarios: list[dict[str, Any]] = manifest["scenarios"]
    assert [entry["slug"] for entry in scenarios] == registered
    assert package["scenario_count"] == len(registered)
    assert package["name"] == PACKAGE_NAME
    assert package["version"] == PACKAGE_VERSION


def test_model_attribution_is_read_from_the_recordings_never_invented() -> None:
    """DEC-136: the envelopes say which model produced them, or nothing does.

    ForgeFlow's capture predates the usage format that carries attribution, so it attributes to
    nothing; the gateway captures name the model the provider reported.
    """
    manifest = build_manifest()
    assert _entry(manifest, "forgeflow")["models"] == []
    assert _entry(manifest, "reply-tuner")["models"] == ["openai/gpt-5.1"]
    assert _entry(manifest, "husky-ai")["models"] == ["claude-opus-5"]


def test_the_catalog_pin_is_reported_as_an_assessment_resolves_it() -> None:
    """A pinned scenario reports its pin; an unpinned one reports the loader's current version,
    which is what its assessments actually run against (DEC-098) — and says which it is."""
    manifest = build_manifest()

    pinned = _entry(manifest, "reply-tuner")
    assert pinned["catalog_version_pinned"] is True
    assert pinned["catalog_version"] == "0.3"

    unpinned = _entry(manifest, "forgeflow")
    assert unpinned["catalog_version_pinned"] is False
    assert unpinned["catalog_version"]


def test_a_condition_reports_its_own_workflow_pin() -> None:
    """DEC-134 as amended: a condition's recording replays under its own shape, so the manifest
    reports the pin per condition rather than one pin for the entry."""
    versions = _entry(build_manifest(), "unsigned-webhooks")["workflow_versions"]
    assert versions == {"clean": "0.2", "adversarial": "0.1"}


def test_an_edited_file_moves_the_group_digest(tmp_path: Path) -> None:
    """The digest is over content, so an edit anywhere in a group moves it."""
    corpus = tmp_path / "scenario"
    shutil.copytree(load_registry()[0].path, corpus)
    entry = Scenario(slug="s", name="S", path=corpus, status="authored")

    before = build_manifest([entry])
    target = next(iter(sorted((corpus / "input").iterdir())))
    target.write_text(target.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
    after = build_manifest([entry])

    assert _entry(before, "s")["files"]["input"] != _entry(after, "s")["files"]["input"]
    assert _entry(before, "s")["digest"] != _entry(after, "s")["digest"]


def test_a_renamed_file_moves_the_group_digest(tmp_path: Path) -> None:
    """Path and content, not content alone: the manifest describes an inventory, and a rename
    changes it even though every byte in the group survives."""
    corpus = tmp_path / "scenario"
    shutil.copytree(load_registry()[0].path, corpus)
    entry = Scenario(slug="s", name="S", path=corpus, status="authored")

    before = build_manifest([entry])
    target = next(iter(sorted((corpus / "input").iterdir())))
    target.rename(target.with_name("renamed" + target.suffix))
    after = build_manifest([entry])

    assert (
        _entry(before, "s")["files"]["input"]["count"]
        == (_entry(after, "s")["files"]["input"]["count"])
    )
    assert (
        _entry(before, "s")["files"]["input"]["digest"]
        != (_entry(after, "s")["files"]["input"]["digest"])
    )


def test_baselines_are_counted_beside_the_recordings_not_inside_them() -> None:
    """`recorded/baselines/` sits under `recorded/`; counting it in both would double-report the
    corpus's size."""
    manifest = build_manifest()
    files = _entry(manifest, "reply-tuner")["files"]
    assert files["baselines"]["count"] == 3
    recorded_names = {
        path.name for path in (load_registry()[0].path / "recorded").rglob("*") if path.is_file()
    }
    assert "baseline-generic.json" in recorded_names  # the corpus really does nest them
    assert files["recorded"]["digest"] != files["baselines"]["digest"]


def test_the_manifest_is_yaml_a_consumer_can_read() -> None:
    parsed = yaml.safe_load(render_manifest())
    assert parsed["package"]["corpus_digest"].startswith("sha256:")
    assert all(entry["digest"].startswith("sha256:") for entry in parsed["scenarios"])
