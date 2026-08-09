"""Tests keeping the local artifact store out of version control.

`current-architecture.md` section 5.16 puts the MVP artifact store in a local `data/` directory
laid out as `data/assessments/<id>/{sources, normalized, outputs, traces, evaluation}`, and
`data-model.md` section 35 puts original documents, normalized documents, reports, debug artifacts,
and exported traces on the filesystem. `sources/` is designed to hold byte-for-byte copies of the
material under review -- including `demo/forgeflow/input/sample-repository-notes.md`, which carries
a deliberate prompt-injection payload.

Neither the loader nor the store is built. The rule lands first anyway: without it, the first run
of the loader would offer all of that to the next commit, which is trivial to prevent beforehand
and tedious to unwind afterwards. So the rule is asserted here rather than trusted to survive
edits by someone who has no reason to know what it protects.

The anchoring is the part that needs a test. An unanchored `data/` matches at any depth, which
would silently swallow a `data/` directory under `demo/`, `benchmarks/`, or `requirements/` -- all
of which hold version-controlled fixtures. The rule is `/data/`, and both halves of that claim are
checked: the root path is ignored, a nested one is not. Issue #42.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from trace_ai.config import PROJECT_ROOT

GITIGNORE = PROJECT_ROOT / ".gitignore"

# A path the artifact store will really produce, per section 5.16 and the DEC-018 identifier form.
STORE_PATH = "data/assessments/asm-001/sources/architecture-overview.md"

# Directories that hold version-controlled data and must stay tracked. If the ignore rule ever
# loses its anchor, a fixture tree under one of these is what it takes with it.
TRACKED_DATA_DIRS = ("demo", "benchmarks", "requirements", "prompts")


def git(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    """Run git in the repository root, returning the completed process rather than raising.

    A non-zero exit is an answer here, not a failure: `git check-ignore` exits 1 to mean
    "no rule matches", which several of these tests assert.
    """
    executable = shutil.which("git")
    assert executable is not None, "git is required to verify ignore rules"
    return subprocess.run(  # noqa: S603 -- fixed argument list, absolute executable, no shell
        [executable, *args],
        cwd=PROJECT_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_gitignore_has_an_anchored_data_rule() -> None:
    lines = [line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()]
    assert "/data/" in lines, (
        "the artifact store rule is missing from .gitignore. It must be `/data/`: the leading "
        "slash anchors it to the repository root so fixture directories keep any nested data/."
    )
    assert "data/" not in lines, (
        "an unanchored `data/` rule matches at any depth and would ignore a data/ directory "
        "under demo/, benchmarks/, or requirements/"
    )


def test_the_artifact_store_path_is_ignored() -> None:
    """The check the rule exists for, expressed as a path the store will really write."""
    result = git("check-ignore", "-v", STORE_PATH)
    assert result.returncode == 0, f"{STORE_PATH} is not ignored"
    assert "/data/" in result.stdout, (
        f"{STORE_PATH} is ignored by something other than the anchored rule: {result.stdout!r}"
    )


@pytest.mark.parametrize("directory", TRACKED_DATA_DIRS)
def test_a_nested_data_directory_is_not_ignored(directory: str) -> None:
    """Anchoring, stated as the thing it protects.

    `git check-ignore` exits 1 when no rule matches, and it answers about the path rather than
    the file, so nothing has to exist on disk for this to be meaningful.
    """
    nested = f"{directory}/data/fixture.yaml"
    result = git("check-ignore", "-v", nested)
    assert result.returncode == 1, (
        f"{nested} is ignored by {result.stdout.strip()!r}. Version-controlled fixtures live "
        f"under {directory}/, and the data/ rule must not reach them."
    )


@pytest.mark.parametrize("directory", TRACKED_DATA_DIRS)
def test_the_fixture_directories_are_still_tracked(directory: str) -> None:
    result = git("ls-files", "--", directory)
    assert result.stdout.strip(), f"{directory}/ has no tracked files"


def test_no_tracked_file_is_ignored() -> None:
    """A tracked file that matches an ignore rule is a trap: git keeps honouring the index.

    Nothing looks wrong until someone removes and re-adds the file, at which point it silently
    fails to come back. `--no-index` is what makes the question answerable: without it,
    check-ignore reports tracked files as un-ignored no matter what the rules say.
    """
    tracked = git("ls-files", "-z")
    assert tracked.returncode == 0
    assert tracked.stdout, "no tracked files found; is this a git working tree?"

    matched = git("check-ignore", "--stdin", "-z", "--no-index", stdin=tracked.stdout)
    offenders = [path for path in matched.stdout.split("\0") if path]

    assert not offenders, f"these tracked files now match an ignore rule: {offenders[:10]}"


def test_the_store_root_is_not_committed_as_a_placeholder() -> None:
    """The artifact store creates its directories on demand, so the rule needs no exception.

    A `.gitkeep` under `data/` would require a negation, and a negation is what turns a one-line
    ignore rule into something nobody can reason about later.
    """
    assert not (PROJECT_ROOT / "data" / ".gitkeep").exists()
    assert "!/data/" not in GITIGNORE.read_text(encoding="utf-8")


def test_the_store_root_is_untracked_if_it_exists() -> None:
    """A local run creates `data/`; that must not show up as a pending change."""
    if not (PROJECT_ROOT / "data").exists():
        pytest.skip("no local artifact store in this working tree")
    status = git("status", "--porcelain", "--", "data")
    assert not status.stdout.strip(), f"data/ is producing git status noise: {status.stdout!r}"


def test_gitignore_rules_are_documented() -> None:
    """The file comments every section; the anchor is the part a later editor would undo.

    Someone tidying an unfamiliar ignore file will read `/data/` as a stray slash and remove it.
    The comment is what stops that, so the comment is asserted too.
    """
    blocks = GITIGNORE.read_text(encoding="utf-8").split("\n\n")
    matching = [block for block in blocks if "/data/" in block.splitlines()]
    assert len(matching) == 1, "the /data/ rule should appear once, in its own commented block"

    block = matching[0]
    assert block.lstrip().startswith("#"), "the /data/ rule has no comment explaining it"
    assert "Anchored" in block, "the comment does not say why the rule is anchored"
