"""Wrap the bare agent recordings in the #461 envelope, once.

The recorded agent responses were bare proposal JSON; `recorded.py` now reads an envelope
`{"schema": <ProposalName>, "response": {...}}` (and an optional `usage`, which only a live capture
can fill). This rewrites each bare recording in place as an envelope, taking the schema from the
filename — every recording is named for its agent (`08-mapping-thr-003.json`,
`28-critical-review.json`) — and cross-checking that the response validates against that schema
before writing, so a misnamed file fails here rather than at replay.

    uv run python scripts/migrate_recordings.py           # rewrite bare recordings
    uv run python scripts/migrate_recordings.py --check    # exit non-zero if any is still bare

Idempotent: an already-enveloped file is left untouched. Baseline recordings (`baselines/`) are not
agent proposals and are read through a different path, so they are out of scope. No `usage` is
written: no live run has been measured (see the README), so the offline ledger stays at zero until a
capture writes real usage — this migration changes the format, not the numbers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import TYPE_CHECKING

from trace_ai.config import PROJECT_ROOT
from trace_ai.infrastructure.model.recorded import RESPONSE_SCHEMAS

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

_SCHEMA_BY_NAME: dict[str, type[BaseModel]] = {
    schema.__name__: schema for schema in RESPONSE_SCHEMAS
}

# The agent slug a recording's filename carries, mapped to the schema its response must be.
_SCHEMA_BY_SLUG: dict[str, type[BaseModel]] = {
    "context-extraction": _SCHEMA_BY_NAME["ContextExtractionProposal"],
    "threat-analysis": _SCHEMA_BY_NAME["ThreatAnalysisProposal"],
    "mapping": _SCHEMA_BY_NAME["MappingProposal"],
    "evidence-validation": _SCHEMA_BY_NAME["EvidenceValidationProposal"],
    "critical-review": _SCHEMA_BY_NAME["CriticalReviewProposal"],
    "report-sections": _SCHEMA_BY_NAME["ReportSections"],
}

# The recorded trees, and the pattern that selects agent recordings while skipping `baselines/`
# (whose names do not start with a digit) and any non-recording file.
_ROOTS = (PROJECT_ROOT / "demo" / "forgeflow", PROJECT_ROOT / "benchmarks")


def _recording_files() -> list[Path]:
    files: list[Path] = []
    for root in _ROOTS:
        files.extend(
            path
            for path in root.rglob("[0-9]*.json")
            if "recorded" in path.parts and "baselines" not in path.parts
        )
    return sorted(files)


def _slug_of(path: Path) -> str:
    """The agent slug in a recording's filename, e.g. `08-mapping-thr-003` -> `mapping`."""
    stem = re.sub(r"^\d+-", "", path.stem)
    return re.sub(r"-thr-\d+$", "", stem)


def _is_envelope(data: object) -> bool:
    return isinstance(data, dict) and "schema" in data and "response" in data


def _enveloped(path: Path) -> str | None:
    """The envelope text for a bare recording, or `None` if it is already one. Raises on a file
    whose filename slug is unknown or whose response does not validate against that schema."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if _is_envelope(data):
        return None

    slug = _slug_of(path)
    schema = _SCHEMA_BY_SLUG.get(slug)
    if schema is None:
        raise SystemExit(f"{path}: unrecognised agent slug {slug!r}; cannot name its schema")
    try:
        schema.model_validate(data)
    except Exception as error:
        raise SystemExit(
            f"{path}: response does not validate as {schema.__name__}: {error}"
        ) from error

    envelope = {"schema": schema.__name__, "response": data}
    return json.dumps(envelope, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--check", action="store_true", help="exit non-zero if any recording is still bare"
    )
    args = parser.parse_args(argv)

    bare: list[Path] = []
    for path in _recording_files():
        enveloped = _enveloped(path)
        if enveloped is None:
            continue
        bare.append(path)
        if not args.check:
            path.write_text(enveloped, encoding="utf-8")

    if args.check:
        if bare:
            print(f"{len(bare)} recording(s) are still bare; run scripts/migrate_recordings.py")
            for path in bare:
                print(f"  {path.relative_to(PROJECT_ROOT)}")
            return 1
        print("every agent recording is an envelope")
        return 0

    print(f"wrapped {len(bare)} recording(s) in the #461 envelope")
    return 0


if __name__ == "__main__":
    sys.exit(main())
