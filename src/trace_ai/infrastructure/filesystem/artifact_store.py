"""The local artifact store: where an assessment's files live, and what may not escape it.

`current-architecture.md` section 5.16 makes the MVP artifact store a controlled local directory
with an assessment-specific structure, and `data-model.md` section 35 splits storage between it
and the database -- original and normalized documents on the filesystem, references and content
hashes in rows. Section 12 names the assessment-data boundary as a trust boundary in its own
right, and that is the sentence this module implements rather than merely honours.

**A store is bound to one assessment.** It is constructed with an assessment identifier and every
path it produces is under that assessment's directory. There is no method that takes another
assessment's identifier, so crossing the boundary is not a mistake a caller can make by passing
the wrong argument; it is a different object they would have to construct.

**Filenames are untrusted.** `SourceDocument.filename` is the original name of a file supplied for
review, which makes it caller-supplied data reaching a path expression. Path traversal is refused
by shape -- no separators, no `..`, no absolute paths -- and then again by resolution, because a
name can be clean while the directory it lands in is a symlink pointing somewhere else. Both
checks run before anything is written.

**Content is stored byte-identical.** Section 5.4 requires the original to be preserved, DEC-019
hashes a source document over its raw bytes, and DEC-015 makes evidence a verbatim excerpt of the
original. A normalization applied at write time would quietly break all three, and the breakage
would not surface until an evidence hash failed to verify against a document nobody had edited.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.identifiers import parse_id

__all__ = ["AREAS", "DEFAULT_ROOT", "ArtifactStore", "ArtifactStoreError", "UnsafeFilenameError"]

# The five subdirectories section 5.16 lists, in the order it lists them.
AREAS: Final = ("sources", "normalized", "outputs", "traces", "evaluation")

# `.gitignore` carries an anchored `/data/` rule so nothing written here is ever offered to a
# commit. The store is deliberately not configurable through `Settings`: nothing in this milestone
# needs to relocate it, tests pass a root directly, and an environment variable whose empty value
# would silently resolve to the current working directory is a worse default than a fixed path.
DEFAULT_ROOT: Final = PROJECT_ROOT / "data"

# Owner-only. The store holds copies of material under review, which may be confidential to the
# organization that supplied it, on a machine DEC-004 assumes is shared with nothing.
_DIRECTORY_MODE: Final = 0o700


class ArtifactStoreError(RuntimeError):
    """Something was asked of the store that it must refuse."""


class UnsafeFilenameError(ArtifactStoreError):
    """A filename that would write outside the assessment directory."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            f"refusing to store {filename!r}: {reason}. Source filenames are untrusted input "
            f"and may not address anything outside the assessment directory."
        )
        self.filename = filename


class ArtifactStore:
    """The files belonging to one assessment.

    Directories are created on demand rather than at construction, so building a store to read
    from does not leave five empty directories behind for an assessment that has none.
    """

    def __init__(self, assessment_id: str, *, root: Path | None = None) -> None:
        parsed = parse_id(assessment_id)
        if parsed.prefix != "asm":
            raise ArtifactStoreError(
                f"an artifact store is bound to an Assessment; {assessment_id!r} names a "
                f"{parsed.object_type}"
            )
        self.assessment_id = assessment_id
        self.root = (root or DEFAULT_ROOT).resolve()

    @property
    def assessment_root(self) -> Path:
        """The directory holding this assessment, named by its identifier.

        Section 5.16's example writes `assessment-001`. The directory is named for the real
        identifier instead -- `asm-001` -- because DEC-018 settled the scheme after that example
        was written, and a directory name that is not the identifier is a second naming convention
        to keep in sync with the first.
        """
        return self.root / "assessments" / self.assessment_id

    def area(self, name: str) -> Path:
        """The path of one subdirectory, created if it does not exist."""
        if name not in AREAS:
            raise ArtifactStoreError(
                f"{name!r} is not one of the areas section 5.16 lists: {AREAS}"
            )
        path = self.assessment_root / name
        path.mkdir(parents=True, exist_ok=True, mode=_DIRECTORY_MODE)
        return path

    def contains(self, path: Path) -> bool:
        """Whether `path` belongs to this assessment, symlinks resolved.

        The direct expression of the section 12 boundary. `resolve()` is what makes it an answer
        about the real location rather than about the spelling of the path.
        """
        try:
            return path.resolve().is_relative_to(self.assessment_root.resolve())
        except OSError:  # pragma: no cover -- an unresolvable path is not inside anything
            return False

    def _safe_path(self, area: str, filename: str) -> Path:
        """Resolve `filename` inside `area`, refusing anything that leaves the assessment.

        Two checks, because either alone is insufficient. The shape check rejects a name that
        addresses another directory. The resolution check rejects a name that is clean but lands
        somewhere else anyway, which is what a symlinked area directory does.
        """
        if not filename or filename in {".", ".."}:
            raise UnsafeFilenameError(filename, "it names no file")
        candidate = Path(filename)
        if candidate.is_absolute() or filename.startswith(("/", "\\")):
            raise UnsafeFilenameError(filename, "it is an absolute path")
        if len(candidate.parts) != 1:
            raise UnsafeFilenameError(filename, "it contains a path separator")
        if ".." in candidate.parts:
            raise UnsafeFilenameError(filename, "it contains a parent-directory component")

        target = self.area(area) / filename
        if not self.contains(target):
            raise UnsafeFilenameError(
                filename, "it resolves outside the assessment directory, likely through a symlink"
            )
        return target

    def _write(self, area: str, filename: str, content: bytes) -> Path:
        """Write bytes, refusing to replace different content under the same name.

        Re-storing identical bytes is idempotent, which is what a re-run does. Storing *different*
        bytes under a name already used would silently replace material under review while every
        `EvidenceReference` into the old content kept its now-unverifiable hash, so it raises.
        """
        target = self._safe_path(area, filename)
        if target.exists():
            existing = target.read_bytes()
            if content_hash(existing) != content_hash(content):
                raise ArtifactStoreError(
                    f"{filename!r} is already stored in {area} for {self.assessment_id} with "
                    f"different content. Storing over it would leave every evidence reference "
                    f"into the original pointing at bytes that no longer exist."
                )
            return target
        target.write_bytes(content)
        return target

    def store_source(self, filename: str, content: bytes) -> Path:
        """Store an original document verbatim. Populates `SourceDocument.original_path`."""
        return self._write("sources", filename, content)

    def store_normalized(self, filename: str, content: bytes) -> Path:
        """Store normalized text. Populates `SourceDocument.normalized_path`."""
        return self._write("normalized", filename, content)

    def read(self, area: str, filename: str) -> bytes:
        """Read back a stored artifact, refusing anything outside this assessment."""
        target = self._safe_path(area, filename)
        if not target.is_file():
            raise ArtifactStoreError(
                f"{filename!r} is not stored in {area} for {self.assessment_id}"
            )
        return target.read_bytes()

    def hash_of(self, area: str, filename: str) -> str:
        """The `sha256:<hex>` of a stored artifact, computed by the one hashing utility."""
        return content_hash(self.read(area, filename))

    def __repr__(self) -> str:
        return f"ArtifactStore(assessment_id={self.assessment_id!r}, root={str(self.root)!r})"
