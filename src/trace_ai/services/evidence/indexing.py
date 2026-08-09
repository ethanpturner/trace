"""Normalization and evidence indexing: the node that makes traceability true rather than intended.

`agent-design.md` sections 3 and 4 place this between document ingestion and context extraction and
classify it as deterministic, with no model involvement. `current-architecture.md` section 5.4
assigns it the responsibilities the loader does not cover — normalize text, divide long documents
into addressable sections, preserve source locations — and claims that every extracted claim can
link back to a source document, a section, its text, a content hash, and an ingestion timestamp.
This is the code that makes the claim checkable.

**`assessment_id` and `source_origin` are derived from the parent document, never passed in.** A
caller supplying them is a caller that can supply the wrong ones, and the assessment-data boundary
would then depend on argument discipline rather than on structure. Every reference this node
produces belongs to the same assessment as the document it came from, because there is no way to
express anything else.

**Each reference carries its own hash, over its own quoted text.** The document already has a hash
over its raw bytes; this one is separate on purpose. It makes a citation verifiable without
re-reading the whole document, and it is what detects a passage changing when the file it came from
did not — DEC-019 states the split and DEC-015 makes `quoted_text` verbatim so there is something
stable to hash.

The node writes the normalized artifact, then updates the document to `ingested` with its
`normalized_path` and `ingested_at`, in the same transaction that saves the references. A document
marked ingested with no references, or references belonging to a document that never finished, are
both states nothing downstream should have to consider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from trace_ai.domain.base import now
from trace_ai.domain.evidence import JSON_POINTER_KEY, EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import IngestionStatus, SourceDocument
from trace_ai.services.ingestion.normalize import line_count, normalize
from trace_ai.services.ingestion.segment import segment

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.execution_ledger import ExecutionLedger

__all__ = ["NODE_NAME", "NODE_VERSION", "IndexingError", "index_document"]

# See the loader's equivalent: section 27 records the node and the implementation version.
NODE_NAME: Final = "normalization_and_evidence_indexing"
NODE_VERSION: Final = "0.1"


class IndexingError(RuntimeError):
    """A document that cannot be indexed."""


def index_document(
    handle: AssessmentHandle,
    document: SourceDocument,
    *,
    ledger: ExecutionLedger | None = None,
) -> list[EvidenceReference]:
    """Normalize a registered document and produce one evidence reference per addressable unit.

    Returns the references in document order. The document is updated in place -- it keeps its
    identifier, gains its ingestion outputs, and its status becomes `ingested` (DEC-033).
    """
    if ledger is None:
        return _index(handle, document)
    with ledger.record(NODE_NAME, node_version=NODE_VERSION, consumes=[document.id]) as execution:
        references = _index(handle, document)
        execution.produced(*[reference.id for reference in references])
        return references


def _index(handle: AssessmentHandle, document: SourceDocument) -> list[EvidenceReference]:
    if document.assessment_id != handle.assessment_id:
        raise IndexingError(
            f"{document.id} belongs to {document.assessment_id}, not {handle.assessment_id}"
        )
    if document.ingestion_status is not IngestionStatus.REGISTERED:
        raise IndexingError(
            f"{document.id} is {document.ingestion_status}, not registered. Indexing a document "
            f"twice would mint a second set of evidence references for the same passages."
        )

    original = handle.artifacts.read("sources", document.filename).decode("utf-8")
    normalized = normalize(original)

    if line_count(normalized) != line_count(original):
        # DEC-015 makes this impossible by construction, and the check stays because the property
        # is what every evidence location depends on. A normalization that gained a step which
        # dropped a blank line would silently move every citation in the document.
        raise IndexingError(
            f"normalizing {document.filename!r} changed the line count from "
            f"{line_count(original)} to {line_count(normalized)}; DEC-015 forbids it"
        )

    normalized_path = handle.artifacts.store_normalized(
        document.filename, normalized.encode("utf-8")
    )
    normalized_lines = normalized.splitlines()

    segments = segment(original, document.media_type)
    if not segments:
        raise IndexingError(f"{document.filename!r} produced no addressable content")

    stamp = now()
    repository = handle.objects
    references: list[EvidenceReference] = []

    with repository.transaction():
        for index, unit in enumerate(segments):
            metadata: dict[str, object] = {}
            if unit.json_pointer is not None:
                metadata[JSON_POINTER_KEY] = unit.json_pointer

            references.append(
                EvidenceReference(
                    id=repository.allocate("evd"),
                    source_document_id=document.id,
                    assessment_id=document.assessment_id,
                    section_title=unit.section_title,
                    chunk_index=index,
                    start_line=unit.start_line,
                    end_line=unit.end_line,
                    quoted_text=unit.text,
                    normalized_text="\n".join(
                        normalized_lines[unit.start_line - 1 : unit.end_line]
                    ),
                    content_hash=content_hash(unit.text.encode("utf-8")),
                    source_origin=document.origin,
                    created_at=stamp,
                    metadata=metadata,
                )
            )

        for reference in references:
            repository.save(reference)

        repository.save(
            SourceDocument.model_validate(
                document.model_dump()
                | {
                    "normalized_path": str(normalized_path),
                    "ingested_at": stamp,
                    "ingestion_status": IngestionStatus.INGESTED,
                }
            )
        )

    return references
