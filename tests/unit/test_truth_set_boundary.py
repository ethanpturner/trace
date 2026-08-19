"""The finding/gap/question boundary, held disjoint across every truth set (DEC-133).

Born of a recorded self-disagreement: the forgeflow truth set expected FND-002 and FND-003 as
findings while its own mapping layer recorded the same ground as `expected_outcome: question`
until the scenario's contradictions resolve — and the matcher, which reads only
`expected-findings.yaml`, graded a no-resolution run's correct questions as missed findings
(DEC-116 recorded the tension). DEC-133's rule: when the same DEC-056 identity appears in both
the findings file and the questions file, the finding entry must declare the dependency by
naming its paired question in `requires_resolution`, and the pair must agree on the
requirement. An undeclared overlap is the disagreement class recurring silently, and this test
is what refuses it — over every registered scenario and every condition that carries its own
truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from trace_ai.services.evaluation.matching import partition_conditional
from trace_ai.services.evaluation.registry import load_registry


def _load(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    parsed: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(parsed.get(key) or [])


def _truth_dirs() -> list[tuple[str, Path]]:
    dirs: list[tuple[str, Path]] = []
    for entry in load_registry():
        dirs.append((entry.slug, entry.expected_dir))
        for condition in entry.conditions:
            conditioned = entry.expected_dir_for(condition)
            if conditioned != entry.expected_dir and conditioned.is_dir():
                dirs.append((f"{entry.slug}[{condition}]", conditioned))
    return dirs


def test_finding_and_question_identities_are_disjoint_unless_declared() -> None:
    """A requirement shared between the two files is the recorded disagreement class; it is
    permitted only through an explicit `requires_resolution` pairing."""
    violations: list[str] = []
    for label, expected_dir in _truth_dirs():
        findings = _load(expected_dir / "expected-findings.yaml", "findings")
        questions = _load(expected_dir / "expected-questions.yaml", "questions")
        question_requirements = {
            str(question.get("requirement_id")): str(question.get("key"))
            for question in questions
            if question.get("requirement_id")
        }
        for finding in findings:
            requirement = str(finding.get("requirement_id"))
            declared = finding.get("requires_resolution")
            if requirement in question_requirements and declared is None:
                violations.append(
                    f"{label}: {finding.get('key')} shares {requirement} with question "
                    f"{question_requirements[requirement]} and declares no requires_resolution"
                )
            if declared is not None:
                paired = next(
                    (
                        question
                        for question in questions
                        if str(question.get("key")) == str(declared)
                    ),
                    None,
                )
                if paired is None:
                    violations.append(
                        f"{label}: {finding.get('key')} names {declared}, which "
                        f"expected-questions.yaml does not hold"
                    )
                elif str(paired.get("requirement_id")) != requirement:
                    violations.append(
                        f"{label}: {finding.get('key')} ({requirement}) names {declared} "
                        f"({paired.get('requirement_id')}); a pair that disagrees on the "
                        f"requirement pairs nothing"
                    )
    assert not violations, "; ".join(violations)


def test_conditional_entries_partition_by_resolution() -> None:
    entries = [
        {"key": "A", "requirement_id": "req-X-001"},
        {"key": "B", "requirement_id": "req-X-002", "requires_resolution": "Q-01"},
    ]
    reachable, unreached = partition_conditional(entries, resolution_supplied=False)
    assert [entry["key"] for entry in reachable] == ["A"]
    assert unreached == ["B"]

    reachable, unreached = partition_conditional(entries, resolution_supplied=True)
    assert [entry["key"] for entry in reachable] == ["A", "B"]
    assert unreached == []


def test_the_forgeflow_pair_is_declared() -> None:
    """The two recorded tensions carry their declarations; a truth-set edit that drops one
    regresses to the pre-DEC-133 disagreement."""
    findings = _load(Path("demo/forgeflow/expected/expected-findings.yaml").resolve(), "findings")
    by_key = {str(entry["key"]): entry for entry in findings}
    assert by_key["FND-002"]["requires_resolution"] == "Q-07"
    assert by_key["FND-003"]["requires_resolution"] == "Q-08"
    assert "requires_resolution" not in by_key["FND-004"]
