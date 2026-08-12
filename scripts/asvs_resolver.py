"""Resolve every ASVS citation in the requirements catalog against the pinned ASVS export.

Survey item A1. ASVS publishes a stable flat JSON export at each release tag, keyed by `req_id`
(e.g. ``V6.1.3``). Every ``source_frameworks`` entry in ``requirements/0.1/*.yaml`` that names
``OWASP ASVS`` carries the reference token ASVS's own README prescribes for external documents,
``v5.0.0-6.1.3`` (issue #222, survey item A2); the export keys the same requirement as ``V6.1.3``,
so resolution is a version check and a lookup. A typo'd or stale identifier is otherwise silent
(the survey verified the 11 original citations by hand); this resolves every citation by lookup
against a cached export, so CI needs no network. A token pinning any version other than the cached
export's is unresolved by definition — the resolver can only vouch for the release it holds.

The export is cached at ``requirements/_external/asvs/v5.0.0.flat.json``. OWASP ASVS 5.0.0 is
licensed CC BY-SA 4.0; the cache carries that license and a pointer to the source tag, and the
catalog cites identifiers only -- it reproduces no ASVS wording (see ``requirements/README.md``).

When the AISVS decision (M0) lands, the same mechanism should extend to ``v1.0-Cx.y.z``
identifiers; the resolver is written so that adding a second export is a new path and a new
framework name, not a rework.

    uv run python scripts/asvs_resolver.py            # print unresolved citations
    uv run python scripts/asvs_resolver.py --check    # exit non-zero if any are unresolved
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.requirements.loader import current_version, load_catalog

# Cached OWASP Application Security Verification Standard 5.0.0 flat JSON export.
# Source tag: https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/docs_en
# License: CC BY-SA 4.0 -- see requirements/_external/asvs/LICENSE.txt
ASVS_EXPORT: Final = PROJECT_ROOT / "requirements" / "_external" / "asvs" / "v5.0.0.flat.json"

ASVS_FRAMEWORK: Final = "OWASP ASVS"

ASVS_EXPORT_VERSION: Final = "5.0.0"


def load_req_ids(path: str) -> frozenset[str]:
    """The set of ``req_id`` values in the pinned ASVS export at ``path``."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    requirements = document["requirements"]
    return frozenset(str(row["req_id"]) for row in requirements)


def asvs_req_id(token: str) -> str | None:
    """``v5.0.0-6.1.3`` -> ``V6.1.3``; ``None`` if the token is malformed or pins another release.

    The token is the reference form ASVS's README prescribes: ``v<version>-<requirement>``. The
    export keys the requirement with a ``V`` prefix the token does not carry. A token naming a
    version other than the cached export's cannot be resolved here, whatever its requirement id.
    """
    prefix = f"v{ASVS_EXPORT_VERSION}-"
    if not token.startswith(prefix):
        return None
    return f"V{token.removeprefix(prefix)}"


def unresolved_citations(export_path: str = str(ASVS_EXPORT)) -> list[tuple[str, str]]:
    """Every ``(requirement id, citation)`` pair whose ASVS control id is not in the export.

    Non-ASVS citations are skipped: this resolver is ASVS-only, and a NIST or OWASP Top 10
    citation has no row in the ASVS export to resolve against.
    """
    valid = load_req_ids(export_path)
    catalog = load_catalog(current_version())
    unresolved: list[tuple[str, str]] = []
    for requirement in catalog.requirements:
        for citation in requirement.source_frameworks:
            framework, separator, token = citation.partition(": ")
            if not separator or framework != ASVS_FRAMEWORK:
                continue
            req_id = asvs_req_id(token.strip())
            if req_id is None or req_id not in valid:
                unresolved.append((requirement.id, citation))
    return unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit non-zero if any citation is unresolved"
    )
    arguments = parser.parse_args()

    unresolved = unresolved_citations()
    if not unresolved:
        return 0

    print("unresolved ASVS citations:", file=sys.stderr)
    for req_id, citation in unresolved:
        print(f"  {req_id}: {citation!r}", file=sys.stderr)

    if arguments.check:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
