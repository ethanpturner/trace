"""The scenario registry: `benchmarks/scenarios.yaml`, read, never scanned (DEC-027, DEC-073).

The registry is the authoritative list of benchmark scenarios. The harness reads it and refuses
a slug it does not carry; a scenario directory the registry does not name simply never runs,
which is a stated fact rather than a silent omission.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from trace_ai.config import PROJECT_ROOT

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = [
    "REGISTRY_PATH",
    "SUPPORTED_REGISTRY_VERSIONS",
    "RegistryError",
    "Scenario",
    "UnknownScenarioError",
    "catalog_version_summary",
    "load_registry",
    "scenario",
]

REGISTRY_PATH = PROJECT_ROOT / "benchmarks" / "scenarios.yaml"

# Registry-file layouts this build understands. A future `2.0` reshapes the entries, and a build
# that read it as `1.0` would misparse silently; refusing an unsupported version is the DEC-010
# rule for the requirements catalog applied to the scenario registry.
SUPPORTED_REGISTRY_VERSIONS: Final = frozenset({"1.0"})


class UnknownScenarioError(ValueError):
    """A slug the registry does not carry."""

    def __init__(self, slug: str, known: list[str]) -> None:
        super().__init__(
            f"{slug!r} is not a registered scenario; the registry carries {', '.join(known)}. "
            f"Scenarios are discovered from benchmarks/scenarios.yaml and never by scanning."
        )


class RegistryError(ValueError):
    """The registry file is not the document this module reads: a missing or misspelled key, a
    non-list `scenarios`, an unsupported `registry_version`. Named, with the offending entry, rather
    than a `KeyError`/`TypeError` traceback from a raw dictionary index."""


class _ScenarioEntry(BaseModel):
    """One `scenarios:` entry. `extra="forbid"` so a misspelled key is named, not ignored."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    path: str
    status: str
    conditions: list[str] = Field(default_factory=list)
    category: str | None = None
    catalog_version: str | None = None
    """The requirements catalog version the scenario's assessments pin (DEC-098). Absent means
    the loader's current version, exactly as an interactive assessment defaults; a scenario
    exercising a draft catalog names it, and `load_catalog(version)` still refuses one that
    does not verify."""
    narrative: str | None = None
    """Informative: a pointer to a scenario's written narrative (ForgeFlow's feeds Stage 6). The
    registry loader accepts it so the field is not an unknown key, but nothing routes on it."""
    workflow_version: str = "0.1"
    """The workflow version the scenario's recording was captured or authored under (DEC-134).
    The replay pins its assessment to this, so the recording is consumed under the call shape
    that produced it. The default is `0.1` — the single-call evidence shape every recording
    committed before batching carries — and a promotion of a newer capture updates the pin."""

    condition_workflow_versions: dict[str, str] = Field(default_factory=dict)
    """Per-condition overrides of `workflow_version` (DEC-134, amended). The pin belongs to the
    recording, and a condition carries its own recording: promoting a newer clean capture must
    not silently re-shape the replay of a condition recording it did not touch. A condition
    absent here replays under the entry's `workflow_version`."""


class _RegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    scenarios: list[_ScenarioEntry]


def _render_registry_error(error: PydanticValidationError, path: Path) -> str:
    parts = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "(root)"
        kind = "unknown key" if detail["type"] == "extra_forbidden" else detail["type"]
        parts.append(f"{location}: {kind}")
    return f"{path} is not a valid scenario registry: " + "; ".join(parts)


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
    catalog_version: str | None = None
    """The roadmap Stage 5 coverage category this scenario exercises (issue #328). Informative:
    nothing routes on it, and scenarios may share one — the registry states which categories are
    covered rather than the filesystem implying it."""
    workflow_version: str = "0.1"
    """The workflow version this scenario's recording carries (DEC-134); the replay pins its
    assessment to it so the recording is consumed under the call shape that produced it."""

    condition_workflow_versions: Mapping[str, str] = field(default_factory=dict)
    """Per-condition pin overrides (DEC-134, amended): a condition's own recording replays under
    its own shape, independent of the clean recording's pin."""

    def workflow_version_for(self, condition: str = CLEAN_CONDITION) -> str:
        """The pin a replay of this condition's recording uses: the condition's own where one is
        declared, the entry's otherwise."""
        return self.condition_workflow_versions.get(condition, self.workflow_version)

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
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegistryError(f"{path} is not a mapping; a scenario registry is a YAML mapping")
    try:
        parsed = _RegistryFile.model_validate(raw)
    except PydanticValidationError as invalid:
        raise RegistryError(_render_registry_error(invalid, path)) from None
    if parsed.registry_version not in SUPPORTED_REGISTRY_VERSIONS:
        raise RegistryError(
            f"{path} declares registry_version {parsed.registry_version!r}; this build supports "
            f"{sorted(SUPPORTED_REGISTRY_VERSIONS)}. A newer registry reshapes the entries and must "
            f"not be read as an older one."
        )
    root = path.parent.parent
    return [
        Scenario(
            slug=entry.slug,
            name=entry.name,
            path=root / entry.path,
            status=entry.status,
            conditions=tuple(entry.conditions),
            category=entry.category,
            catalog_version=entry.catalog_version,
            workflow_version=entry.workflow_version,
            condition_workflow_versions=dict(entry.condition_workflow_versions),
        )
        for entry in parsed.scenarios
    ]


def scenario(slug: str, *, registry_path: Path | None = None) -> Scenario:
    scenarios = load_registry(registry_path)
    for entry in scenarios:
        if entry.slug == slug:
            return entry
    raise UnknownScenarioError(slug, [entry.slug for entry in scenarios])


def catalog_version_summary(scenarios: list[Scenario] | None = None) -> str:
    """The catalog versions the corpus actually assesses against, counted (#500).

    A scenario without a pin (DEC-098) assesses against the loader's current version, exactly
    as an interactive assessment defaults, so the summary resolves the absence the same way.
    One version reads as before ("0.1"); a mixed corpus names each with its scenario count
    ("0.1 (12), 0.2 (1)") — a single stamp over a mixed corpus was structurally incapable of
    being true.
    """
    from collections import Counter

    from trace_ai.services.requirements.loader import current_version

    entries = scenarios if scenarios is not None else load_registry()
    counts = Counter(entry.catalog_version or current_version() for entry in entries)
    if len(counts) == 1:
        return next(iter(counts))
    return ", ".join(f"{version} ({count})" for version, count in sorted(counts.items()))
