"""The deterministic half of scripts/check_catalog_freeze.py.

The guard reads released versions from requirements/versions.yaml and fails a change that touches
one (DEC-057). Its self-guard — "no released versions, nothing frozen" — is a real path, but if
the real registry ever resolved to that path the whole guard would silently pass on every change.
This pins that the committed registry does declare a frozen version, and that a blanked or
malformed registry is caught by the test rather than quietly disarming the guard in CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from trace_ai.config import PROJECT_ROOT


def _load() -> ModuleType:
    path = PROJECT_ROOT / "scripts" / "check_catalog_freeze.py"
    spec = importlib.util.spec_from_file_location("check_catalog_freeze", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_catalog_freeze"] = module
    spec.loader.exec_module(module)
    return module


freeze = _load()


def test_the_real_registry_declares_a_frozen_version() -> None:
    """The committed versions.yaml has at least one non-draft version, so the guard actually
    guards something. A registry that resolved to no frozen versions would pass every change."""
    assert freeze.frozen_versions(), "versions.yaml declares no frozen version; the guard is inert"


def test_a_missing_registry_reports_nothing_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(freeze, "REGISTRY", tmp_path / "absent.yaml")

    assert freeze.frozen_versions() == []


def test_a_draft_only_registry_freezes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = tmp_path / "versions.yaml"
    registry.write_text("versions:\n  '0.1':\n    status: draft\n", encoding="utf-8")
    monkeypatch.setattr(freeze, "REGISTRY", registry)

    assert freeze.frozen_versions() == []


def test_a_released_version_is_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry = tmp_path / "versions.yaml"
    registry.write_text(
        "versions:\n  '0.1':\n    status: active\n  '0.2':\n    status: draft\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(freeze, "REGISTRY", registry)

    assert freeze.frozen_versions() == ["0.1"]
