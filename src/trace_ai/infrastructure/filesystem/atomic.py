"""Atomic file writes: write a sibling temporary file, then rename it into place.

A crash, a full disk, or a kill mid-write must never leave a half-written file where a whole one
belongs. Two files in this project make that failure expensive:

* the workflow **state file** is rewritten on every phase; a truncated one is unresumable, because
  `load_state` raises on malformed JSON, and the run it described becomes impossible to continue.
* a stored **artifact** whose bytes were truncated no longer matches the `content_hash` recorded for
  it, and the store then refuses to re-store the correct bytes -- wedging the assessment.

`os.replace` is atomic when the source and destination are on the same filesystem, which a sibling
temporary in the destination directory guarantees. A reader therefore sees either the old file or
the new one, never a partial write.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["write_bytes_atomic", "write_text_atomic"]


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write `data` to `path` atomically, overwriting any existing file.

    The temporary carries the process id so two processes writing the same path do not clobber each
    other's in-progress temporary; the rename that follows is what is atomic.
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write `text` to `path` atomically, overwriting any existing file."""
    write_bytes_atomic(path, text.encode(encoding))
