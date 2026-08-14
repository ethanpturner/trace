"""The scenario registry: `benchmarks/scenarios.yaml`, read, never scanned (DEC-027, DEC-073).

The registry is the authoritative list of benchmark scenarios. The harness reads it and refuses
a slug it does not carry; a scenario directory the registry does not name simply never runs,
which is a stated fact rather than a silent omission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml

from trace_ai.config import PROJECT_ROOT

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["REGISTRY_PATH", "Scenario", "UnknownScenarioError", "load_registry", "scenario"]

REGISTRY_PATH = PROJECT_ROOT / "benchmarks" / "scenarios.yaml"


class UnknownScenarioError(ValueError):
    """A slug the registry does not carry."""

    def __init__(self, slug: str, known: list[str]) -> None:
        super().__init__(
            f"{slug!r} is not a registered scenario; the registry carries {', '.join(known)}. "
            f"Scenarios are discovered from benchmarks/scenarios.yaml and never by scanning."
        )


CLEAN_CONDITION = "clean"


@dataclass(frozen=True, slots=True)
class Scenario:
    """One registry entry, with the paths the harness needs derived once.

    A scenario may declare conditions (DEC-075) — `clean` is implicit, and each named condition is
    a variant under `conditions/<name>/` holding an input overlay and, where the truth differs, an
    expected overlay and its own recording. The base `input/`, `expected/`, and `recorded/` are the
    clean condition.
    """

    slug: str
    name: str
    path: Path
    status: str
    conditions: tuple[str, ...] = ()
    category: str | None = None
    """The roadmap Stage 5 coverage category this scenario exercises (issue #328). Informative:
    nothing routes on it, and scenarios may share one — the registry states which categories are
    covered rather than the filesystem implying it."""

    @property
    def input_dir(self) -> Path:
        return self.path / "input"

    @property
    def expected_dir(self) -> Path:
        return self.path / "expected"

    @property
    def recorded_dir(self) -> Path:
        return self.path / "recorded"

    def condition_dir(self, condition: str) -> Path:
        return self.path / "conditions" / condition

    def input_documents(self, condition: str = CLEAN_CONDITION) -> list[Path]:
        """The documents a run under this condition sees: the clean set, overlaid by the
        condition's own files (a same-named file replaces the clean one, DEC-075)."""
        by_name = {path.name: path for path in sorted(self.input_dir.iterdir()) if path.is_file()}
        if condition != CLEAN_CONDITION:
            overlay = self.condition_dir(condition) / "input"
            if overlay.is_dir():
                for path in sorted(overlay.iterdir()):
                    if path.is_file():
                        by_name[path.name] = path
        return [by_name[name] for name in sorted(by_name)]

    def expected_dir_for(self, condition: str = CLEAN_CONDITION) -> Path:
        """The truth-set directory for a condition: its own if authored, else the clean set."""
        if condition != CLEAN_CONDITION:
            overlay = self.condition_dir(condition) / "expected"
            if overlay.is_dir():
                return overlay
        return self.expected_dir

    def recorded_dir_for(self, condition: str = CLEAN_CONDITION) -> Path:
        """The recording directory for a condition: its own if present, else the clean one."""
        if condition != CLEAN_CONDITION:
            overlay = self.condition_dir(condition) / "recorded"
            if overlay.is_dir():
                return overlay
        return self.recorded_dir

    @property
    def has_recording(self) -> bool:
        """Whether the scenario carries response recordings the harness can replay.

        A bare `recorded/` directory is not a recording: it must hold response JSON files. The
        harness refuses a scenario without one by name, and `--all` reports it skipped.
        """
        return self.recorded_dir.is_dir() and any(self.recorded_dir.rglob("[0-9]*.json"))

    def has_recording_for(self, condition: str = CLEAN_CONDITION) -> bool:
        recorded = self.recorded_dir_for(condition)
        return recorded.is_dir() and any(recorded.rglob("[0-9]*.json"))

    @property
    def has_outcome_truth(self) -> bool:
        """Whether the outcome-side truth files the benchmark metrics read are authored."""
        return (self.expected_dir / "expected-findings.yaml").is_file() and (
            self.expected_dir / "expected-documentation-gaps.yaml"
        ).is_file()


def load_registry(registry_path: Path | None = None) -> list[Scenario]:
    path = registry_path if registry_path is not None else REGISTRY_PATH
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = path.parent.parent
    return [
        Scenario(
            slug=str(entry["slug"]),
            name=str(entry["name"]),
            path=root / str(entry["path"]),
            status=str(entry["status"]),
            conditions=tuple(str(name) for name in entry.get("conditions", ())),
            category=str(entry["category"]) if entry.get("category") else None,
        )
        for entry in parsed["scenarios"]
    ]


def scenario(slug: str, *, registry_path: Path | None = None) -> Scenario:
    scenarios = load_registry(registry_path)
    for entry in scenarios:
        if entry.slug == slug:
            return entry
    raise UnknownScenarioError(slug, [entry.slug for entry in scenarios])
