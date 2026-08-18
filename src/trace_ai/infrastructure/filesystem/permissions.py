"""Owner-only creation for the data root, shared by the two things that write into it.

Both the SQLite database and the artifact store hold copies of material under review -- including
verbatim excerpts (`EvidenceReference.quoted_text`) and the deliberate prompt-injection fixture --
on a machine DEC-004 assumes is shared with nothing. Section 5.16's intent is that none of it is
world-readable, and two mkdir footguns defeat that intent unless handled explicitly:

* `Path.mkdir(parents=True, mode=...)` applies `mode` to the *leaf* only; every ancestor it creates
  takes `0o777 & ~umask`, which is `0o755` under the usual umask. So the assessment directory ends
  up owner-only while `data/` and `data/assessments/` above it are world-readable.
* SQLite creates its database file (and the `-wal`/`-shm` companions) at `0o644` regardless of how
  the directory was created.

`mkdir_owner_only` walks the missing ancestors and creates each at `0o700`; `restrict_to_owner`
tightens a file and its SQLite companions to `0o600`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["mkdir_owner_only", "restrict_to_owner"]

_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


def mkdir_owner_only(path: Path) -> None:
    """Create `path` and any missing ancestors, each `0o700`.

    Unlike `Path.mkdir(parents=True, mode=0o700)`, which would leave the ancestors world-readable,
    this creates every missing directory in the chain owner-only. An already-existing directory is
    left untouched -- its permissions are its owner's business, and a `tmp_path` root in a test must
    not be chmod'd out from under pytest.
    """
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=_DIRECTORY_MODE)


def restrict_to_owner(path: Path) -> None:
    """Tighten `path` and its `-wal`/`-shm` companions to `0o600` if they exist.

    The companions are created lazily on the first WAL write, so they may or may not be present when
    this runs; each is chmod'd only if it exists. `stat.S_IMODE` masks off the file-type bits so the
    result is a plain permission comparison in tests.
    """
    for candidate in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        if candidate.exists():
            candidate.chmod(_FILE_MODE)
