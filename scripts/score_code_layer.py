"""Score a reviewer's findings against a scenario's code-level truth (DEC-156), RealVuln-style.

The code layer's truth file, `benchmarks/<slug>/expected/code-ground-truth.yaml`, lists the
vulnerable entries and the false-positive traps in RealVuln's shape. A reviewer's finding matches an
entry when it cites the entry's file and names a CWE in the entry's acceptable set; where two entries
share a file and a CWE family, the finding's cited line range decides between them by the entry's
function span, supplied here as `--span file:function=start-end`. An entry marked `non_scoring` is
excluded from both numerator and denominator, as RealVuln excludes it. A finding that matches no
entry is a false positive; one that matches a trap (`is_vulnerable: false`, scoring) is a trap hit
and a false positive. A finding that cites no file is unmatchable and is counted separately rather
than as either.

Input is one or more `feed.jsonl` files (one finding per line: `code_paths`, `cwe`, `signature`).
Output is counts with their denominators, one block per feed, as JSON on stdout. Offline; no model.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PATH_LINE = re.compile(r"^(?P<path>[^:]+?)(?::(?P<line>[0-9]+)(?:-[0-9]+)?)?$")


@dataclass(frozen=True)
class Entry:
    id: str
    file: str
    cwes: frozenset[str]
    vulnerable: bool
    scoring: bool
    span: tuple[int, int] | None


@dataclass
class FeedScore:
    feed: str
    findings: int = 0
    duplicates: int = 0
    true_positives: list[str] = field(default_factory=list)
    trap_hits: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    non_scoring: list[str] = field(default_factory=list)
    unmatchable: list[str] = field(default_factory=list)

    def summary(self, truth_positives: int) -> dict[str, object]:
        claimed = len(self.true_positives) + len(self.false_positives)
        return {
            "feed": self.feed,
            "findings_emitted": self.findings,
            "duplicates_collapsed": self.duplicates,
            "true_positives": len(self.true_positives),
            "false_positives": len(self.false_positives),
            "trap_hits": len(self.trap_hits),
            "non_scoring": len(self.non_scoring),
            "unmatchable_no_file": len(self.unmatchable),
            "precision": {"numerator": len(self.true_positives), "denominator": claimed},
            "recall": {"numerator": len(set(self.true_positives)), "denominator": truth_positives},
            "matched_entries": sorted(set(self.true_positives)),
        }


def load_truth(path: Path, spans: dict[str, tuple[int, int]]) -> list[Entry]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries: list[Entry] = []
    for raw in doc["findings"]:
        function = str((raw.get("location") or {}).get("function", ""))
        key = f"{raw['file']}:{function}"
        entries.append(
            Entry(
                id=str(raw["id"]),
                file=str(raw["file"]),
                cwes=frozenset(str(c) for c in raw.get("acceptable_cwes") or [raw["primary_cwe"]]),
                vulnerable=bool(raw["is_vulnerable"]),
                scoring=raw.get("scoring", "scoring") != "non_scoring",
                span=spans.get(key),
            )
        )
    return entries


def _cited(finding: dict[str, Any]) -> list[tuple[str, int | None]]:
    cited: list[tuple[str, int | None]] = []
    paths: list[Any] = list(finding.get("code_paths") or [])
    for item in paths:
        match = _PATH_LINE.match(str(item))
        if match is None:
            continue
        path = match.group("path")
        line = match.group("line")
        cited.append((path, int(line) if line else None))
    return cited


def _cwes(finding: dict[str, Any]) -> set[str]:
    raw = finding.get("cwe")
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    return {str(c) for c in raw}


def score(feed_path: Path, entries: list[Entry]) -> FeedScore:
    result = FeedScore(feed=str(feed_path))
    seen: set[str] = set()
    for line in feed_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        finding: dict[str, Any] = json.loads(line)
        result.findings += 1
        signature = str(finding.get("signature") or json.dumps(finding, sort_keys=True))
        if signature in seen:
            result.duplicates += 1
            continue
        seen.add(signature)
        cited = _cited(finding)
        files = {path for path, _ in cited if path.endswith(".py")}
        if not files:
            result.unmatchable.append(signature)
            continue
        cwes = _cwes(finding)
        candidates = [e for e in entries if e.file in files and (cwes & e.cwes)]
        if len(candidates) > 1:
            lines = [ln for path, ln in cited if ln is not None]
            narrowed = [
                e
                for e in candidates
                if e.span is not None and any(e.span[0] <= ln <= e.span[1] for ln in lines)
            ]
            candidates = narrowed or candidates
        if not candidates:
            result.false_positives.append(signature)
            continue
        entry = candidates[0]
        if not entry.scoring:
            result.non_scoring.append(signature)
        elif entry.vulnerable:
            result.true_positives.append(entry.id)
        else:
            result.trap_hits.append(entry.id)
            result.false_positives.append(signature)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("truth", type=Path, help="expected/code-ground-truth.yaml")
    parser.add_argument("feeds", type=Path, nargs="+", help="feed.jsonl files, one per run")
    parser.add_argument(
        "--span",
        action="append",
        default=[],
        metavar="FILE:FUNCTION=START-END",
        help="a function's line span, to separate two entries sharing a file and a CWE family",
    )
    args = parser.parse_args(argv)
    spans: dict[str, tuple[int, int]] = {}
    for spec in args.span:
        key, _, rng = spec.partition("=")
        start, _, end = rng.partition("-")
        spans[key] = (int(start), int(end))
    entries = load_truth(args.truth, spans)
    positives = sum(1 for e in entries if e.vulnerable and e.scoring)
    out = [score(feed, entries).summary(positives) for feed in args.feeds]
    json.dump({"truth_positives": positives, "runs": out}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
