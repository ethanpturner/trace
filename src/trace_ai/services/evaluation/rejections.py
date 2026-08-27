"""Whether a run asserted a claim its scenario authored as one a correct assessment does not make.

Every scenario carries an `expected-rejections.yaml`: the claims a correct assessment declines to
make, each with the mechanism that suppresses it. DEC-147 named this file as where a wrongly
produced claim is graded -- "the rejection entry is where that wrongness is authored and graded" --
and the grading was never built. Fifty entries across fifteen scenarios were read by exactly one
thing: a ForgeFlow-only regression test asserting mechanisms against constructed objects. No run
was ever scored against them and no baseline saw them at all.

**A breach is a spurious finding on a rejected requirement.** The matcher has already classified
every produced finding; this reads only the ones it called `spurious`, so a finding that matched an
expectation cannot breach, and neither can one DEC-148 withheld as divergent. What remains is a
finding the truth set did not ask for, and a rejection naming its requirement says in advance that
asking for one there is wrong.

**Attribution is requirement-level, not claim-level.** A rejection names a claim in prose; the
match is on its `requirement_id`. A spurious finding on that requirement counts as a breach whether
or not it makes the particular claim the rejection wrote. The error is one-directional -- it can
report more breaches than were committed, never fewer -- so the number errs against the tool it
measures, which is the safe direction for a metric a project publishes about itself. Widening it to
compare claim text would make the negative set the one place in the harness where a similarity
threshold decides a score, and DEC-056's matcher never reads prose.

**A scenario whose rejections carry no requirement is not scored.** Fourteen of the fifteen author
`key`, `claim`, `mechanism`, `requirement_id`, `entry` and `why`. `reply-tuner` authors `key`,
`conclusion` and `suppressed_by`, because nothing ever loaded these files and no schema was ever
enforced on them. Its entries yield no scoreable rejections, the metrics are not emitted, and the
page shows a dash rather than a zero (DEC-150). Normalizing that file is a truth-set edit and needs
its own argument from its own inputs (DEC-149).

Metrics and identifiers only (DEC-076): a breach is reported as a rejection key and a finding
identifier, never as the claim's text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

__all__ = [
    "Rejection",
    "RejectionOutcome",
    "load_rejections",
    "score_rejections",
    "spurious_requirements",
]

_FILENAME = "expected-rejections.yaml"


@dataclass(frozen=True, slots=True)
class Rejection:
    """One authored claim a correct assessment does not make, reduced to what can be scored."""

    key: str
    mechanism: str
    requirement_id: str


@dataclass(slots=True)
class RejectionOutcome:
    """Which authored rejections a run breached, in aggregate and per mechanism.

    `total` is the scoreable population, not the authored one: an entry carrying no
    `requirement_id` is outside the metric and outside its denominator. `scoreable` is False when
    that leaves nothing, and a caller emits no rate in that case (DEC-150).
    """

    total: int = 0
    breached: dict[str, list[str]] = field(default_factory=dict)
    by_mechanism: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def scoreable(self) -> bool:
        return self.total > 0

    @property
    def breach_count(self) -> int:
        return len(self.breached)

    @property
    def breach_rate(self) -> float | None:
        """Breached over scoreable, or None where nothing is scoreable (DEC-150)."""
        return (self.breach_count / self.total) if self.total else None


def load_rejections(expected_dir: Path) -> list[Rejection]:
    """The scoreable rejections a scenario authors, in file order.

    An entry missing `requirement_id` or `mechanism` is skipped rather than defaulted: a rejection
    with no requirement names no ground the matcher can reach, and inventing one would score the
    run against an expectation nobody wrote.
    """
    path = expected_dir / _FILENAME
    if not path.is_file():
        return []
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return []
    entries = parsed.get("rejections") or []
    scoreable: list[Rejection] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        requirement_id = entry.get("requirement_id")
        mechanism = entry.get("mechanism")
        if requirement_id is None or mechanism is None:
            continue
        scoreable.append(
            Rejection(
                key=str(entry["key"]),
                mechanism=str(mechanism),
                requirement_id=str(requirement_id),
            )
        )
    return scoreable


def score_rejections(
    spurious: Mapping[str, Iterable[str]],
    rejections: Sequence[Rejection],
) -> RejectionOutcome:
    """Classify each authored rejection against the run's spurious findings.

    `spurious` maps a produced finding's identifier to the requirement identifiers it cites -- a
    list for the pipeline, whose `Finding.requirement_ids` may name several, and a single-entry
    list for a baseline, whose schema carries one. Only findings the matcher already classified
    spurious belong here; passing a matched or divergent finding would score a breach the
    classification rules exclude.
    """
    outcome = RejectionOutcome(total=len(rejections))
    per_mechanism: dict[str, list[bool]] = {}
    for rejection in rejections:
        breaching = sorted(
            finding_id
            for finding_id, requirement_ids in spurious.items()
            if rejection.requirement_id in set(requirement_ids)
        )
        if breaching:
            outcome.breached[rejection.key] = breaching
        per_mechanism.setdefault(rejection.mechanism, []).append(bool(breaching))
    outcome.by_mechanism = {
        mechanism: (sum(hits), len(hits)) for mechanism, hits in sorted(per_mechanism.items())
    }
    return outcome


def spurious_requirements(
    spurious_ids: Sequence[str],
    findings: Sequence[Any],
) -> dict[str, list[str]]:
    """The requirement identifiers each spurious pipeline finding cites, keyed by finding id."""
    wanted = set(spurious_ids)
    return {
        finding.id: list(finding.requirement_ids) for finding in findings if finding.id in wanted
    }
