"""The benchmark package: the corpus described as a versioned artifact (DEC-146, #574).

The corpus — fifteen scenarios, their truth sets, their recordings, and the live baselines beside
them — is consumable today only by someone standing inside this repository. A manifest makes it an
artifact: every scenario named with the files it carries, the versions it pins, and a digest over
each group, so a consumer can tell whether the corpus they hold is the corpus a number was reported
against.

The manifest is assembled, never authored (DEC-076). Nothing here restates a fact that lives
somewhere else: the scenario list comes from the registry, the catalog pin from the registry entry
or the loader's current version exactly as an assessment resolves it, and the model attribution from
the recorded envelopes rather than from provenance prose (DEC-136). `--check` fails when the
committed manifest and the corpus disagree, which is what keeps the description true as captures are
promoted.

The package *version* is the one authored value, because only a person can say whether a change
leaves previously reported scores comparable. DEC-146 states the rule; `PACKAGE_VERSION` records the
answer.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.registry import CLEAN_CONDITION, load_registry
from trace_ai.services.evaluation.stamps import DETERMINISTIC_STAMP

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from trace_ai.services.evaluation.registry import Scenario

__all__ = [
    "MANIFEST_PATH",
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "build_manifest",
    "render_manifest",
]

MANIFEST_PATH = PROJECT_ROOT / "benchmarks" / "manifest.yaml"

PACKAGE_NAME = "trace-benchmark-corpus"

# The corpus's first stamped version. DEC-146 fixes what a bump means: MAJOR when previously
# reported scores stop being comparable (a truth set's expectations change, a scenario leaves, the
# identity rule moves), MINOR when the change is additive or provenance-only (a scenario arrives, a
# recording is re-captured under an unchanged truth set). A person decides it; the manifest below
# is generated.
PACKAGE_VERSION = "1.0"

_GROUPS = ("input", "expected", "recorded", "baselines", "conditions")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _files_under(root: Path) -> list[Path]:
    """Every file under `root`, sorted, or nothing when the directory is absent."""
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _group_digest(paths: Sequence[Path], *, relative_to: Path) -> str:
    """A digest over a group of files: each file's scenario-relative path and content hash, sorted.

    Path-and-content rather than content alone, so a renamed file moves the digest — the manifest
    describes an inventory, and a rename is a change to it.

    Scenario-relative rather than repo-relative, so the digest describes the scenario's own
    contents and not where the checkout happens to sit. A consumer comparing digests against a
    clone at a different path gets the same answer, and a scenario that moves within the tree
    reports the move in its `path` rather than as a content change.
    """
    lines = [f"{path.relative_to(relative_to).as_posix()} {_sha256_file(path)}" for path in paths]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _group_entry(paths: Sequence[Path], *, relative_to: Path) -> dict[str, Any]:
    return {
        "count": len(paths),
        "digest": f"sha256:{_group_digest(paths, relative_to=relative_to)}",
    }


def _repo_relative(path: Path) -> str:
    """The scenario's location as the manifest states it: repo-relative for the registered corpus,
    absolute for a scenario constructed outside the tree (a test fixture)."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _recorded_models(recordings: Iterable[Path]) -> list[str]:
    """The distinct models the recordings say produced them (DEC-136).

    A captured envelope carries the provider's reported model in its usage block; an authored
    envelope carries no usage at all, so it attributes to nothing and the list is empty rather than
    naming a model no call reached. `harness._recorded_models` applies the same rule for the
    scorecard; this reads the corpus without importing the live path.
    """
    models: set[str] = set()
    for path in recordings:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        usage = envelope.get("usage") if isinstance(envelope, dict) else None
        model = usage.get("model") if isinstance(usage, dict) else None
        if isinstance(model, str) and model:
            models.add(model)
    return sorted(models)


def _offline_pin(recorded: Path) -> str | None:
    """The scenario's committed offline report hash, where it pins one (#505)."""
    pin = recorded / "report-hash-offline.txt"
    if not pin.is_file():
        return None
    return pin.read_text(encoding="utf-8").strip() or None


def _scenario_entry(entry: Scenario) -> dict[str, Any]:
    from trace_ai.services.requirements.loader import current_version

    recorded = entry.recorded_dir
    baseline_files = _files_under(recorded / "baselines")
    # `recorded` counts the pipeline envelopes, the decision files, the pins, and the provenance
    # note; the baselines sit under it and are reported separately, so they are excluded here
    # rather than counted twice.
    baselines = set(baseline_files)
    recorded_files = [path for path in _files_under(recorded) if path not in baselines]

    groups = {
        "input": _files_under(entry.input_dir),
        "expected": _files_under(entry.expected_dir),
        "recorded": recorded_files,
        "baselines": baseline_files,
        "conditions": _files_under(entry.path / "conditions"),
    }

    conditions = [CLEAN_CONDITION, *entry.conditions]
    workflow_versions = {
        condition: entry.workflow_version_for(condition) for condition in conditions
    }

    body: dict[str, Any] = {
        "slug": entry.slug,
        "name": entry.name,
        "path": _repo_relative(entry.path),
        "category": entry.category,
        "catalog_version": entry.catalog_version or current_version(),
        "catalog_version_pinned": entry.catalog_version is not None,
        "workflow_versions": workflow_versions,
        "conditions": conditions,
        # DEC-136: read from the recordings, never from prose. An empty list is an authored
        # recording attributing to nothing, not an unknown model.
        "models": _recorded_models(recorded.rglob("[0-9]*.json")),
        "report_hash_offline": _offline_pin(recorded),
        "files": {name: _group_entry(groups[name], relative_to=entry.path) for name in _GROUPS},
    }
    body["digest"] = (
        "sha256:"
        + hashlib.sha256(
            "\n".join(f"{name}={body['files'][name]['digest']}" for name in _GROUPS).encode("utf-8")
        ).hexdigest()
    )
    return body


def build_manifest(scenarios: list[Scenario] | None = None) -> dict[str, Any]:
    """The manifest as data: the package header, then one entry per registered scenario."""
    entries = scenarios if scenarios is not None else load_registry()
    bodies = [_scenario_entry(entry) for entry in entries]
    corpus = hashlib.sha256(
        "\n".join(f"{body['slug']}={body['digest']}" for body in bodies).encode("utf-8")
    ).hexdigest()
    registry = yaml.safe_load(
        (PROJECT_ROOT / "benchmarks" / "scenarios.yaml").read_text(encoding="utf-8")
    )
    return {
        "package": {
            "name": PACKAGE_NAME,
            "version": PACKAGE_VERSION,
            "registry_version": str(registry["registry_version"]),
            "generated_at": DETERMINISTIC_STAMP.isoformat(),
            "scenario_count": len(bodies),
            "corpus_digest": f"sha256:{corpus}",
        },
        "scenarios": bodies,
    }


_HEADER = f"""\
# The benchmark package manifest (DEC-146, #574).
#
# Generated by `uv run python scripts/build_benchmark_manifest.py` -- do not edit by hand. CI runs
# the same script with `--check` and fails when this file and the corpus disagree, so a promoted
# capture that does not regenerate the manifest is caught rather than silently described wrong.
#
# `{PACKAGE_NAME}` version is authored: DEC-146 fixes when it bumps and what the bump promises a
# consumer. Everything below it is read from the corpus -- the scenario list from the registry, the
# catalog pin as an assessment resolves it, the models from the recorded envelopes (DEC-136).
"""


def render_manifest(manifest: dict[str, Any] | None = None) -> str:
    body = manifest if manifest is not None else build_manifest()
    return _HEADER + yaml.safe_dump(body, sort_keys=False, default_flow_style=False, width=100)
