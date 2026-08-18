"""Evidence retrieval and integrity verification: the interface agents sit behind.

`agent-design.md` section 22 gives agents an application-controlled retrieval interface and denies
them arbitrary filesystem access, shell access, and database writes. This is that interface. It
exists now, before any agent, because a boundary added after the code that should have been behind
it is a boundary with exceptions — every component written in the meantime reads files directly,
and the constraint becomes a thing to remember rather than a thing that holds.

**Verification distinguishes three outcomes, not two.** `data-model.md` section 35 stores content
hashes for filesystem artifacts, which is only useful if something checks them, and a boolean would
collapse *the file is gone* into *the quotation is stale*. Those need different responses: a missing
artifact means the assessment's own storage is damaged, while changed content means the material
under review moved on and the conclusions drawn from it need re-examining.

**`render_for_prompt` returns data and no paths.** It is the shape evidence takes when it reaches a
model-assisted step, and it carries an identifier, a location, a quotation, and a source filename —
never `original_path`, never `normalized_path`, never anything absolute. Two reasons: a filesystem
path in a prompt is an invitation to a model that has no filesystem, and a path is the one field
whose leakage would tell a document where it lives on the reviewer's machine. It assembles no
prompt and imports nothing from a provider SDK; `agent-design.md` section 24's delimiting belongs
with the first agent.

Nothing here repairs anything. The index reports; re-indexing is a decision someone makes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from trace_ai.domain.evidence import JSON_POINTER_KEY, EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import SourceDocument
from trace_ai.infrastructure.filesystem.artifact_store import ArtifactStoreError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "CheckedBy",
    "EvidenceIndex",
    "EvidenceNotFoundError",
    "VerificationOutcome",
    "VerificationResult",
]


class VerificationOutcome(StrEnum):
    """What re-reading the artifact found."""

    MATCHES = "matches"
    """The recorded quotation is still at the recorded location."""

    CONTENT_CHANGED = "content_changed"
    """The artifact is present and no longer says what the reference quotes.

    The material under review moved on. Every conclusion resting on this reference needs
    re-examining, and DEC-015 forbids editing the reference to agree -- a correction is a new
    reference.
    """

    ARTIFACT_MISSING = "artifact_missing"
    """The artifact is gone. The assessment's own storage is damaged, not the source material."""


class CheckedBy(StrEnum):
    """How the check was performed, because the two are not equally strong."""

    LINE_RANGE = "line_range"
    """The recorded lines were re-read and hashed. This verifies location as well as text."""

    TEXT_SEARCH = "text_search"
    """The quotation was found somewhere in the document. Weaker: it confirms the text survives,
    not that it is still where the reference says. Used only when no line range was recorded."""


@dataclass(frozen=True, slots=True)
class VerificationResult:
    evidence_id: str
    outcome: VerificationOutcome
    checked_by: CheckedBy | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is VerificationOutcome.MATCHES


class EvidenceNotFoundError(LookupError):
    """No such evidence reference in this assessment.

    Raised rather than returning `None`, and raised identically whether the identifier is unknown
    or belongs to another assessment. A caller that could tell those apart could enumerate another
    assessment's identifiers by asking.
    """

    def __init__(self, evidence_id: str, assessment_id: str) -> None:
        super().__init__(f"no evidence reference {evidence_id!r} in {assessment_id}")
        self.evidence_id = evidence_id


class EvidenceIndex:
    """Retrieval and verification for one assessment's evidence.

    One index serves one operation -- a node's run, a `trace verify` -- and caches within that
    lifetime: the source documents it resolves, the source files it reads, and the full reference
    list. Evidence and its documents are immutable after ingestion (DEC-015), so the caches cannot
    go stale under the index; a later operation builds a fresh index and sees fresh data.
    """

    def __init__(self, handle: AssessmentHandle) -> None:
        self.handle = handle
        self._document_cache: dict[str, SourceDocument | None] = {}
        self._source_text_cache: dict[str, str | None] = {}
        self._references: list[EvidenceReference] | None = None

    def _document(self, source_document_id: str) -> SourceDocument | None:
        """The source document, resolved once. `_rendered` and `verify` both need it per reference,
        and reading it from the store each time is a query per reference for a filename."""
        if source_document_id not in self._document_cache:
            self._document_cache[source_document_id] = self.handle.objects.find(
                SourceDocument, source_document_id
            )
        return self._document_cache[source_document_id]

    def _source_text(self, document: SourceDocument) -> str | None:
        """The addressable text of the stored source, read once per document. `verify_all` over K
        references into one document read that file K times; memoizing makes it one read. For a
        PDF this is the extraction of the stored bytes (DEC-123) — the same text indexing
        addressed, so verification and citation share one definition of line *n*. `None` when
        the artifact is gone or unreadable, which the caller reports as `ARTIFACT_MISSING`."""
        from trace_ai.services.ingestion.pdf import PdfExtractionError, addressable_text

        if document.id not in self._source_text_cache:
            try:
                raw = self.handle.artifacts.read("sources", document.filename)
                text: str | None = addressable_text(raw, document.media_type)[0]
            except ArtifactStoreError, OSError, UnicodeDecodeError, PdfExtractionError:
                text = None
            self._source_text_cache[document.id] = text
        return self._source_text_cache[document.id]

    def _all_references(self) -> list[EvidenceReference]:
        if self._references is None:
            self._references = self.handle.objects.list(EvidenceReference)
        return self._references

    def get(self, evidence_id: str) -> EvidenceReference:
        """One reference, or a named error. The read-path enforcement of the section 12 boundary."""
        found = self.handle.objects.find(EvidenceReference, evidence_id)
        if found is None:
            raise EvidenceNotFoundError(evidence_id, self.handle.assessment_id)
        return found

    def for_document(self, source_document_id: str) -> list[EvidenceReference]:
        """Every reference into one document, in chunk order."""
        references = [
            reference
            for reference in self._all_references()
            if reference.source_document_id == source_document_id
        ]
        return sorted(references, key=lambda reference: reference.chunk_index or 0)

    def verify(self, evidence_id: str) -> VerificationResult:
        """Re-read the artifact and compare what is there against what was recorded."""
        return self._verify(self.get(evidence_id))

    def _verify(self, reference: EvidenceReference) -> VerificationResult:
        document = self._document(reference.source_document_id)
        if document is None:
            return VerificationResult(
                reference.id,
                VerificationOutcome.ARTIFACT_MISSING,
                detail=f"source document {reference.source_document_id} is not stored",
            )

        original = self._source_text(document)
        if original is None:
            return VerificationResult(
                reference.id,
                VerificationOutcome.ARTIFACT_MISSING,
                detail=f"the stored source {document.filename!r} could not be read",
            )

        if reference.start_line is not None and reference.end_line is not None:
            lines = original.splitlines()
            found = "\n".join(lines[reference.start_line - 1 : reference.end_line])
            matches = content_hash(found.encode("utf-8")) == reference.content_hash
            return VerificationResult(
                reference.id,
                VerificationOutcome.MATCHES if matches else VerificationOutcome.CONTENT_CHANGED,
                checked_by=CheckedBy.LINE_RANGE,
                detail=None if matches else "the recorded lines no longer hash to the same value",
            )

        matches = reference.quoted_text in original
        return VerificationResult(
            reference.id,
            VerificationOutcome.MATCHES if matches else VerificationOutcome.CONTENT_CHANGED,
            checked_by=CheckedBy.TEXT_SEARCH,
            detail=None if matches else "the quoted text is not present in the document",
        )

    def verify_all(self) -> list[VerificationResult]:
        """Every reference that no longer matches. An empty list is the healthy answer.

        Verifies the references it already listed rather than re-fetching each by id, and reads each
        source file once (memoized), so K references into one document cost one read, not K.
        """
        results = [self._verify(reference) for reference in self._all_references()]
        return [result for result in results if not result.ok]

    def render_for_prompt(self, evidence_ids: Sequence[str]) -> list[dict[str, Any]]:
        """The shape evidence takes when it reaches a model-assisted step.

        Plain JSON-serializable data, in the order asked for. No path of any kind: a model has no
        filesystem, and a path is the one field whose leakage would tell a document where it lives
        on the reviewer's machine.
        """
        return [self._rendered(self.get(evidence_id)) for evidence_id in evidence_ids]

    def render_document(self, source_document_id: str) -> list[dict[str, Any]]:
        """The same shape for every reference into one document, in chunk order."""
        return [self._rendered(reference) for reference in self.for_document(source_document_id)]

    def _rendered(self, reference: EvidenceReference) -> dict[str, Any]:
        document = self._document(reference.source_document_id)
        location: dict[str, Any] = {
            "section_title": reference.section_title,
            "chunk_index": reference.chunk_index,
            "start_line": reference.start_line,
            "end_line": reference.end_line,
        }
        pointer = reference.metadata.get(JSON_POINTER_KEY)
        if isinstance(pointer, str):
            location["json_pointer"] = pointer

        return {
            "evidence_id": reference.id,
            "source_document_id": reference.source_document_id,
            "source_filename": document.filename if document else None,
            "location": location,
            "quoted_text": reference.quoted_text,
            "content_hash": reference.content_hash,
        }

    def resolve(self, evidence_ids: Iterable[str]) -> list[EvidenceReference]:
        """Several references at once, failing on the first unknown identifier."""
        return [self.get(evidence_id) for evidence_id in evidence_ids]
