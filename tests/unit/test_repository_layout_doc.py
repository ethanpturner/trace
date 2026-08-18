"""Section 15 of current-architecture.md and the repository agree, in both directions.

The section's tree was the proposed organization long after the real one diverged — a shareable
architecture document whose repository map was fiction (#540). Correcting the text once would
only start the next divergence, so the tree is parsed and compared to the filesystem the same
way `test_data_model_conformance.py` holds the field tables to the code: a declared directory
that does not exist fails, and so does a directory the section omits within its declared scope —
top-level directories, the packages under `src/trace_ai`, and the subdirectories of `tests/`
and `docs/`.

`data/` and everything below it is the gitignored runtime data root, and `site/` is the
gitignored rendered documentation site (DEC-104); both are named in the section's prose rather
than its tree, and they are the two deliberate exclusions here.
"""

from __future__ import annotations

from pathlib import Path

from trace_ai.config import PROJECT_ROOT

DOCUMENT = PROJECT_ROOT / "docs" / "architecture" / "current-architecture.md"


def _tree_lines() -> list[str]:
    text = DOCUMENT.read_text(encoding="utf-8")
    _, marker, after = text.partition("## 15. Repository Structure")
    assert marker, "current-architecture.md no longer has a section 15"
    body = after.partition("\n## ")[0]
    assert "```text" in body, "section 15 no longer carries a fenced tree"
    fence = body.partition("```text")[2].partition("```")[0]
    return [line for line in fence.splitlines() if line.strip()]


def _declared() -> set[Path]:
    """Every directory the tree names, as a repo-relative path."""
    ancestry: list[tuple[int, str]] = []
    declared: set[Path] = set()
    for line in _tree_lines():
        indent = len(line) - len(line.lstrip(" "))
        assert indent % 2 == 0, f"tree indentation is two spaces per level: {line!r}"
        name = line.strip()
        assert name.endswith("/"), f"every tree entry is a directory: {name!r}"
        ancestry = [entry for entry in ancestry if entry[0] < indent]
        ancestry.append((indent, name.rstrip("/")))
        declared.add(Path(*(part for _, part in ancestry)))
    return declared


def _actual() -> set[Path]:
    """The directories the declared scope holds it to: top level, the package, tests, docs."""
    actual: set[Path] = set()
    for child in PROJECT_ROOT.iterdir():
        if child.name.startswith(".") or child.name in ("data", "site") or not child.is_dir():
            continue
        actual.add(Path(child.name))
    package = PROJECT_ROOT / "src" / "trace_ai"
    actual.add(Path("src"))
    actual.add(Path("src") / "trace_ai")
    for path in package.rglob("*"):
        if path.is_dir() and "__pycache__" not in path.parts:
            actual.add(path.relative_to(PROJECT_ROOT))
    for scope in ("tests", "docs"):
        for child in (PROJECT_ROOT / scope).iterdir():
            if child.is_dir() and child.name != "__pycache__":
                actual.add(Path(scope) / child.name)
    return actual


def test_every_declared_directory_exists() -> None:
    phantoms = sorted(
        str(directory) for directory in _declared() if not (PROJECT_ROOT / directory).is_dir()
    )
    assert not phantoms, f"section 15 names directories that do not exist: {phantoms}"


def test_every_directory_in_scope_is_declared() -> None:
    omitted = sorted(str(directory) for directory in _actual() - _declared())
    assert not omitted, f"section 15 omits: {omitted}"
