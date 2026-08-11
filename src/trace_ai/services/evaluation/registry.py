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


@dataclass(frozen=True, slots=True)
class Scenario:
    """One registry entry, with the paths the harness needs derived once."""

    slug: str
    name: str
    path: Path
    status: str

    @property
    def input_dir(self) -> Path:
        return self.path / "input"

    @property
    def expected_dir(self) -> Path:
        return self.path / "expected"

    @property
    def recorded_dir(self) -> Path:
        return self.path / "recorded"

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
        )
        for entry in parsed["scenarios"]
    ]


def scenario(slug: str, *, registry_path: Path | None = None) -> Scenario:
    scenarios = load_registry(registry_path)
    for entry in scenarios:
        if entry.slug == slug:
            return entry
    raise UnknownScenarioError(slug, [entry.slug for entry in scenarios])
