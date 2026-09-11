"""An external tool's findings, hand-mapped and scored as a non-authoritative arm (DEC-155).

A code reviewer such as Google's Mantis or OpenAI's Codex Security cannot run through the seam:
it is a program or a prompt suite driving its own agent, over source code rather than the
documents Trace reads. DEC-074 keeps such a tool out of the baseline set for exactly that reason
— a wrapper would measure the wrapper. What *can* be scored is what the tool produced: a person
maps each of its validated findings to a catalogue requirement and a component name under the
DEC-056 rule, records the mapping and its reasoning in a feed file, and the harness scores the
rows by the same structural matcher the baselines are scored by, ties resolved in the external
tool's favour.

**The feed is hand-authored and says so.** `results/<arm>/<slug>-run-<N>.yaml` carries the arm, the
tool and its version or commit, the snapshot of code it reviewed, the model attribution DEC-136
requires, the provenance DEC-152 requires (`captured` or `authored`), and three lists: `findings`
the mapper tied to a requirement, `unverified` findings the tool itself left unproven
(`failed_to_reproduce`, `not_attempted` — recorded as unverified, never as a miss or a match,
which is the tool's own rule stated back to it), and `spurious` findings that name no catalogue
requirement at all and are spurious by definition. A row carries identifiers and a locator, never
the tool's prose: the mapper's reasoning stays in the feed file and does not reach any rendered
page (DEC-076).

**The row is non-authoritative and is never a proposal.** Nothing here enters an assessment.
Six agents are the cap, and a parser that promoted another model's conclusions into
`documented` claims would be the fabrication DEC-118 and DEC-140 refused. The only path by
which such a tool's output reaches Trace's pipeline is as an untrusted source document, where
Evidence Validation must still test what it says.

**Citation fidelity is ported to code (DEC-151).** A baseline cites a passage; an external tool
cites `path:line`. Given the worktree at the snapshot the tool reviewed, each locator either
resolves — the file exists and the line is in range — or it does not, and the resolvable fraction
is reported as counts with their denominator. Without a worktree the metric is not emitted
(DEC-150): unmeasured, never zero.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.baselines import score_produced
from trace_ai.services.evaluation.registry import scenario as load_scenario

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = [
    "EXTERNAL_FEEDS_ROOT",
    "FEED_VERSION",
    "PROVENANCE_VALUES",
    "ExternalFeed",
    "ExternalFeedError",
    "ExternalOutcome",
    "LocatorOutcome",
    "MappedFinding",
    "discover_feeds",
    "external_condition",
    "load_feed",
    "resolve_locators",
    "score_feed",
]

FEED_VERSION = "1"
EXTERNAL_FEEDS_ROOT = PROJECT_ROOT / "results"
"""Where hand-authored external feeds are committed: `results/<arm>/<slug>-run-<N>.yaml`. Distinct
from the gitignored `benchmarks/results/` tree the harness writes derived feeds into. An absent or
empty directory contributes nothing to any page."""

PROVENANCE_VALUES = ("captured", "authored")
_ARM = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA = re.compile(r"^[0-9a-f]{7,64}$")
_FILENAME = re.compile(r"^(?P<slug>[a-z0-9][a-z0-9-]*)-run-(?P<run>[1-9][0-9]*)\.ya?ml$")
_LOCATOR = re.compile(r"^(?P<path>[^:]+?)(?::(?P<start>[1-9][0-9]*)(?:-(?P<end>[1-9][0-9]*))?)?$")

_TOP_KEYS = {
    "feed_version",
    "arm",
    "scenario",
    "run",
    "tool",
    "models",
    "snapshot_sha",
    "provenance",
    "mapped_by",
    "findings",
    "unverified",
    "spurious",
}
_ROW_KEYS = {"raw_signature", "requirement_id", "component", "evidence_locator", "mapper_reasoning"}
_ASIDE_KEYS = {"raw_signature", "reason"}


class ExternalFeedError(ValueError):
    """A feed file the loader refuses, with the reason stated."""


@dataclass(frozen=True, slots=True)
class MappedFinding:
    """One tool finding a person tied to a catalogue requirement and a component (DEC-056)."""

    raw_signature: str
    requirement_id: str
    component: str
    evidence_locator: str
    mapper_reasoning: str

    # The attribute names the baseline scorer reads, so one scorer serves both arms.
    @property
    def affected_component(self) -> str:
        return self.component

    @property
    def title(self) -> str:
        return self.raw_signature


@dataclass(frozen=True, slots=True)
class ExternalFeed:
    """A validated feed file. Identifiers, locators, and provenance; no tool prose."""

    arm: str
    scenario: str
    run: int
    tool_name: str
    tool_version: str
    models: tuple[str, ...]
    snapshot_sha: str
    provenance: str
    mapped_by: str
    findings: tuple[MappedFinding, ...]
    unverified: tuple[tuple[str, str], ...]
    """`(raw_signature, reason)` for each finding the tool left unproven."""
    spurious: tuple[tuple[str, str], ...]
    """`(raw_signature, reason)` for each finding naming no catalogue requirement."""
    path: Path

    @property
    def condition(self) -> str:
        return external_condition(self.arm)

    @property
    def label(self) -> str:
        return f"run-{self.run}"


def external_condition(arm: str) -> str:
    """The feed condition an external arm's runs are keyed under."""
    return f"external-{arm}"


def _require(mapping: dict[str, Any], key: str, path: Path) -> Any:
    if key not in mapping:
        raise ExternalFeedError(f"{path}: missing required key {key!r}")
    return mapping[key]


def _text(value: Any, key: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExternalFeedError(f"{path}: {key!r} must be a non-empty string")
    return value.strip()


def _refuse_extra(mapping: dict[str, Any], allowed: set[str], where: str, path: Path) -> None:
    extra = sorted(set(mapping) - allowed)
    if extra:
        raise ExternalFeedError(f"{path}: {where} carries keys the feed does not admit: {extra}")


def _rows(payload: Any, key: str, path: Path) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ExternalFeedError(f"{path}: {key!r} must be a list of mappings")
    return payload


def load_feed(path: Path) -> ExternalFeed:
    """Read and validate one hand-authored feed. Anything the schema does not admit is refused.

    The file name carries the scenario and run number and must agree with the body: a feed
    filed under one scenario and claiming another is the kind of drift a reader cannot see on
    the rendered page.
    """
    name = _FILENAME.match(path.name)
    if name is None:
        raise ExternalFeedError(f"{path}: file name must be <scenario>-run-<N>.yaml")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ExternalFeedError(f"{path}: the feed must be a mapping")
    _refuse_extra(parsed, _TOP_KEYS, "the feed", path)

    if str(_require(parsed, "feed_version", path)) != FEED_VERSION:
        raise ExternalFeedError(f"{path}: feed_version must be {FEED_VERSION!r}")
    arm = _text(_require(parsed, "arm", path), "arm", path)
    if not _ARM.match(arm):
        raise ExternalFeedError(f"{path}: arm {arm!r} must be a lowercase slug")
    scenario = _text(_require(parsed, "scenario", path), "scenario", path)
    if scenario != name.group("slug"):
        raise ExternalFeedError(f"{path}: scenario {scenario!r} disagrees with the file name")
    run = _require(parsed, "run", path)
    if not isinstance(run, int) or isinstance(run, bool) or run < 1:
        raise ExternalFeedError(f"{path}: run must be a positive integer")
    if run != int(name.group("run")):
        raise ExternalFeedError(f"{path}: run {run} disagrees with the file name")

    tool = _require(parsed, "tool", path)
    if not isinstance(tool, dict):
        raise ExternalFeedError(f"{path}: tool must be a mapping of name and version")
    _refuse_extra(tool, {"name", "version"}, "tool", path)
    tool_name = _text(_require(tool, "name", path), "tool.name", path)
    tool_version = _text(_require(tool, "version", path), "tool.version", path)

    models_raw = _require(parsed, "models", path)
    if not isinstance(models_raw, list) or not all(isinstance(m, str) for m in models_raw):
        raise ExternalFeedError(
            f"{path}: models must be a list of model identifiers (may be empty)"
        )
    models = tuple(m.strip() for m in models_raw if m.strip())

    snapshot = _text(_require(parsed, "snapshot_sha", path), "snapshot_sha", path).lower()
    if not _SHA.match(snapshot):
        raise ExternalFeedError(f"{path}: snapshot_sha must be a hex digest")
    provenance = _text(_require(parsed, "provenance", path), "provenance", path)
    if provenance not in PROVENANCE_VALUES:
        raise ExternalFeedError(
            f"{path}: provenance must be one of {', '.join(PROVENANCE_VALUES)} (DEC-152)"
        )
    mapped_by = _text(_require(parsed, "mapped_by", path), "mapped_by", path)

    seen: set[str] = set()

    def _signature(row: dict[str, Any], where: str) -> str:
        signature = _text(_require(row, "raw_signature", path), f"{where}.raw_signature", path)
        if signature in seen:
            raise ExternalFeedError(f"{path}: raw_signature {signature!r} appears twice")
        seen.add(signature)
        return signature

    findings: list[MappedFinding] = []
    for row in _rows(parsed.get("findings"), "findings", path):
        _refuse_extra(row, _ROW_KEYS, "a findings row", path)
        signature = _signature(row, "findings")
        locator = _text(_require(row, "evidence_locator", path), "evidence_locator", path)
        if _LOCATOR.match(locator) is None:
            raise ExternalFeedError(
                f"{path}: evidence_locator {locator!r} is not path[:line[-line]]"
            )
        findings.append(
            MappedFinding(
                raw_signature=signature,
                requirement_id=_text(_require(row, "requirement_id", path), "requirement_id", path),
                component=_text(_require(row, "component", path), "component", path),
                evidence_locator=locator,
                mapper_reasoning=_text(
                    _require(row, "mapper_reasoning", path), "mapper_reasoning", path
                ),
            )
        )

    def _aside(key: str) -> tuple[tuple[str, str], ...]:
        entries: list[tuple[str, str]] = []
        for row in _rows(parsed.get(key), key, path):
            _refuse_extra(row, _ASIDE_KEYS, f"a {key} row", path)
            signature = _signature(row, key)
            entries.append((signature, _text(_require(row, "reason", path), "reason", path)))
        return tuple(entries)

    return ExternalFeed(
        arm=arm,
        scenario=scenario,
        run=run,
        tool_name=tool_name,
        tool_version=tool_version,
        models=models,
        snapshot_sha=snapshot,
        provenance=provenance,
        mapped_by=mapped_by,
        findings=tuple(findings),
        unverified=_aside("unverified"),
        spurious=_aside("spurious"),
        path=path,
    )


def discover_feeds(root: Path | None = None) -> list[Path]:
    """Every committed external feed under `results/<arm>/`, sorted. Absent root: nothing."""
    base = root if root is not None else EXTERNAL_FEEDS_ROOT
    if not base.is_dir():
        return []
    return sorted(
        path
        for arm_dir in base.iterdir()
        if arm_dir.is_dir()
        for path in arm_dir.iterdir()
        if path.is_file() and _FILENAME.match(path.name)
    )


@dataclass(slots=True)
class LocatorOutcome:
    """How many cited `path:line` locators resolve in the reviewed worktree (DEC-151, on code)."""

    total: int = 0
    resolved: int = 0
    unresolved: list[str] = field(default_factory=list)
    """The raw signatures whose locator did not resolve — identifiers, not the locators."""

    @property
    def rate(self) -> float | None:
        return (self.resolved / self.total) if self.total else None


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def resolve_locators(findings: Sequence[MappedFinding], worktree: Path) -> LocatorOutcome:
    """Check each locator against the worktree at the snapshot the tool reviewed.

    A locator resolves when its path is relative, stays inside the worktree, names a file, and
    any line range it carries lies within that file. Nothing here reads the file's content
    beyond counting lines; the check is resolvability, not correctness of the citation.
    """
    outcome = LocatorOutcome(total=len(findings))
    root = worktree.resolve()
    for finding in findings:
        match = _LOCATOR.match(finding.evidence_locator)
        if match is None:
            outcome.unresolved.append(finding.raw_signature)
            continue
        relative = match.group("path")
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            outcome.unresolved.append(finding.raw_signature)
            continue
        start = match.group("start")
        if start is not None:
            lines = _line_count(candidate)
            first = int(start)
            last = int(match.group("end") or start)
            if first > lines or last > lines or last < first:
                outcome.unresolved.append(finding.raw_signature)
                continue
        outcome.resolved += 1
    return outcome


@dataclass(slots=True)
class ExternalOutcome:
    """What scoring one external feed produced, and where the derived feed landed."""

    feed: ExternalFeed
    matched: dict[str, list[str]] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)
    divergent: dict[str, list[str]] = field(default_factory=dict)
    spurious: list[str] = field(default_factory=list)
    """Raw signatures the matcher classified spurious plus those spurious by definition."""
    conditional_unreached: list[str] = field(default_factory=list)
    rejections: dict[str, Any] = field(default_factory=dict)
    locators: LocatorOutcome | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    feed_path: Path | None = None


def score_feed(
    path: Path,
    *,
    results_root: Path,
    worktree: Path | None = None,
    registry_path: Path | None = None,
) -> ExternalOutcome:
    """Score one hand-authored feed against its scenario's truth set and export a derived feed.

    The mapped rows go through `score_produced` — the baseline scorer — so matched, missed,
    divergent (DEC-148), conditional-unreached (DEC-133), spurious, and the DEC-154 rejection
    breaches are classified under the rule every other arm is classified under. The findings the
    feed lists as `spurious` (no catalogue requirement) are added to the spurious count and can
    breach nothing, because they cite no requirement. The `unverified` list is carried on the
    feed as identifiers and enters no metric.
    """
    feed = load_feed(path)
    entry = load_scenario(feed.scenario, registry_path=registry_path)
    if not entry.has_outcome_truth:
        raise ExternalFeedError(
            f"scenario {feed.scenario!r} has no outcome-side truth to score an external arm against"
        )
    scored = score_produced(entry, list(feed.findings))
    outcome = ExternalOutcome(feed=feed)
    outcome.matched = scored["matched"]
    outcome.missed = scored["missed"]
    outcome.divergent = scored.get("divergent") or {}
    outcome.spurious = [row["title"] for row in scored["spurious"]] + [
        signature for signature, _ in feed.spurious
    ]
    outcome.conditional_unreached = scored.get("conditional_unreached") or []
    outcome.rejections = scored["rejections"]
    outcome.metrics = {
        "false_negative_rate": float(scored["metrics"]["false_negative_rate"]),
        "spurious_finding_count": float(len(outcome.spurious)),
    }
    if worktree is not None:
        outcome.locators = resolve_locators(feed.findings, worktree)
        if outcome.locators.total:
            outcome.metrics["locator_resolvability"] = float(outcome.locators.rate or 0.0)
    outcome.feed_path = _export(feed, outcome, results_root=results_root)
    return outcome


def _export(feed: ExternalFeed, outcome: ExternalOutcome, *, results_root: Path) -> Path:
    """Write the derived feed in the harness's shape, keyed by `external-<arm>` (DEC-076)."""
    metrics: dict[str, dict[str, float | int | None]] = {
        name: {"value": value} for name, value in outcome.metrics.items()
    }
    if outcome.locators is not None and outcome.locators.total:
        metrics["locator_resolvability"]["sample_size"] = outcome.locators.total
    payload: dict[str, Any] = {
        "feed_version": FEED_VERSION,
        "scenario": feed.scenario,
        "condition": feed.condition,
        "label": feed.label,
        "authoritative": False,
        "models": list(feed.models),
        "provenance": feed.provenance,
        "external": {
            "arm": feed.arm,
            "tool": {"name": feed.tool_name, "version": feed.tool_version},
            "snapshot_sha": feed.snapshot_sha,
            "run": feed.run,
            "mapped_by": feed.mapped_by,
            "unverified": len(feed.unverified),
            "unmapped": len(feed.spurious),
            "locators": (
                {"resolved": outcome.locators.resolved, "total": outcome.locators.total}
                if outcome.locators is not None
                else None
            ),
        },
        "metrics": metrics,
        "items": {
            "findings": {
                "matched": outcome.matched,
                "missed": outcome.missed,
                "divergent": outcome.divergent,
                "spurious": outcome.spurious,
                "conditional_unreached": outcome.conditional_unreached,
                "unverified": [signature for signature, _ in feed.unverified],
            },
            "rejections": outcome.rejections,
        },
    }
    target = results_root / feed.scenario / feed.condition / f"{feed.label}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
