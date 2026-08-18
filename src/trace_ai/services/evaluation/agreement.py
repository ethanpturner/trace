"""Inter-annotator agreement over a scenario's truth set (#530, DEC-112).

Every truth set is one person's judgment, and until now the benchmark measured runs against
that judgment while nothing measured the judgment itself — self-agreement wearing a metric's
clothes. This module compares two independently authored annotation sets for one scenario: the
authoritative `expected/` directory, and a second set at `annotations/second/` mirroring the
same file shapes. The identity forms are the matcher's own (DEC-056): a finding is its
`requirement_id` plus normalized `affected_component`, a documentation gap is its
`requirement_id`, a question is its normalized text. Wording is never compared, exactly as the
run-side matcher never compares it.

**The statistic is set agreement, and it gates nothing.** For each artifact the two sets are
compared as identity sets and reported as Jaccard agreement — intersection over union — with the
raw counts beside it, pooled across artifacts for the headline number. Chance-corrected kappa
is deliberately not computed: kappa needs a negative universe, and an open-world truth set has
no enumerable set of findings the annotators both declined. Where a second set does not exist
the scenario measures nothing here — unmeasured, never zero — and the first set remains
authoritative regardless of the number (DEC-112): disagreement is a review question for the
truth set's owner, not an automatic edit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["AgreementOutcome", "ArtifactAgreement", "compute_agreement", "second_annotation_dir"]

SECOND_DIRNAME = "second"


def second_annotation_dir(scenario_path: Path) -> Path:
    """Where a scenario's second annotation set lives: `annotations/second/` beside `expected/`."""
    return scenario_path / "annotations" / SECOND_DIRNAME


def _normalized(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _entries(directory: Path, filename: str, key: str) -> list[dict[str, Any]] | None:
    path = directory / filename
    if not path.is_file():
        return None
    parsed: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list((parsed or {}).get(key) or [])


def _finding_identities(entries: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (str(entry["requirement_id"]), _normalized(entry["affected_component"]))
        for entry in entries
    }


def _gap_identities(entries: list[dict[str, Any]]) -> set[str]:
    return {str(entry["requirement_id"]) for entry in entries}


def _question_identities(entries: list[dict[str, Any]]) -> set[str]:
    # The corpus field for a question's text is `asks` — every committed
    # `expected-questions.yaml` uses it. The instrument shipped reading `question`, a field no
    # truth set carries, and no test noticed because none exercised the questions artifact; a
    # real second set would have crashed the metric (#565). The conformance test over the
    # committed truth sets now pins the field names this module reads.
    return {_normalized(entry["asks"]) for entry in entries}


@dataclass(frozen=True, slots=True)
class ArtifactAgreement:
    """One artifact's two identity sets, compared."""

    artifact: str
    in_both: int
    only_first: int
    only_second: int

    @property
    def union(self) -> int:
        return self.in_both + self.only_first + self.only_second

    @property
    def jaccard(self) -> float | None:
        """`None` when both sets are empty: two annotators agreeing there is nothing to say is
        vacuous for a ratio, and reported as the counts instead."""
        return self.in_both / self.union if self.union else None


@dataclass(slots=True)
class AgreementOutcome:
    """The comparison across artifacts, with the pooled headline."""

    artifacts: list[ArtifactAgreement] = field(default_factory=list)

    @property
    def pooled(self) -> float | None:
        union = sum(entry.union for entry in self.artifacts)
        if not union:
            return None
        return sum(entry.in_both for entry in self.artifacts) / union


_ARTIFACTS: tuple[tuple[str, str, str, Any], ...] = (
    ("findings", "expected-findings.yaml", "findings", _finding_identities),
    (
        "documentation_gaps",
        "expected-documentation-gaps.yaml",
        "documentation_gaps",
        _gap_identities,
    ),
    ("questions", "expected-questions.yaml", "questions", _question_identities),
)


def compute_agreement(expected_dir: Path, second_dir: Path) -> AgreementOutcome | None:
    """Compare the two annotation sets, or `None` when the second does not exist.

    An artifact file absent from the second set is skipped rather than read as an empty
    annotation: a second pass that has not covered questions yet has said nothing about
    questions, and silence is not an empty set (the DEC-009 posture, applied to annotators).
    """
    if not second_dir.is_dir():
        return None
    outcome = AgreementOutcome()
    for artifact, filename, key, identities in _ARTIFACTS:
        first_entries = _entries(expected_dir, filename, key)
        second_entries = _entries(second_dir, filename, key)
        if first_entries is None or second_entries is None:
            continue
        first_ids = identities(first_entries)
        second_ids = identities(second_entries)
        outcome.artifacts.append(
            ArtifactAgreement(
                artifact=artifact,
                in_both=len(first_ids & second_ids),
                only_first=len(first_ids - second_ids),
                only_second=len(second_ids - first_ids),
            )
        )
    return outcome if outcome.artifacts else None
