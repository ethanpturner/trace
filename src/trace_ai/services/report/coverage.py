"""DEC-071's coverage ledger: every source document in exactly one bucket, with its reason.

A reader cannot weigh conclusions without knowing what was never read, and a document silently
dropped is the invisible failure this ledger converts into a visible row. The ledger is derived
at render time from persisted state — the document's `ingestion_status`, and the budget
exclusions the agent nodes record on their execution metadata — because a ledger with a memory
hole is worse than none.

Exactly-one-bucket holds by construction: the buckets partition on `IngestionStatus`, with the
budget case splitting `ingested` in two. A status this module does not know is a loud failure,
never an unlisted document, and the renderer separately refuses a ledger that does not account
for every `SourceDocument`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from trace_ai.domain.source_document import IngestionStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.execution import ExecutionRecord
    from trace_ai.domain.source_document import SourceDocument

__all__ = [
    "EXCLUDED_EVIDENCE_METADATA_KEY",
    "CoverageBucket",
    "CoverageEntry",
    "coverage_ledger",
]

# Where the agent nodes record the evidence a budget overrun excluded, by identifier — the fence
# rule's naming obligation (DEC-025), persisted so the ledger can carry it to the reader.
EXCLUDED_EVIDENCE_METADATA_KEY: Final = "excluded_evidence_ids"


class CoverageBucket(StrEnum):
    """DEC-071's four dispositions. A document lands in exactly one."""

    REVIEWED = "reviewed"
    """Ingested, and its evidence was available to every stage."""

    REVIEWED_WITH_EXCLUSIONS = "reviewed_with_exclusions"
    """Reviewed, but an evidence budget excluded named excerpts; the ledger names them."""

    COULD_NOT_PROCESS = "could_not_process"
    """Supplied but not ingestable — format, corruption — with the recorded error class."""

    EXCLUDED_BY_RULE = "excluded_by_rule"
    """Deliberately out of scope, with the rule stated."""


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    """One document's disposition, with the justification a reader can check."""

    document_id: str
    filename: str
    bucket: CoverageBucket
    justification: str
    excluded_evidence_ids: tuple[str, ...] = ()


def _excluded_by_document(
    evidence_references: Sequence[EvidenceReference],
    execution_records: Sequence[ExecutionRecord],
) -> dict[str, list[str]]:
    """Budget-excluded evidence identifiers, grouped by the document each excerpt came from."""
    excluded_ids: set[str] = set()
    for record in execution_records:
        named = record.metadata.get(EXCLUDED_EVIDENCE_METADATA_KEY)
        if isinstance(named, list):
            excluded_ids.update(str(value) for value in named)

    by_document: dict[str, list[str]] = {}
    for reference in evidence_references:
        if reference.id in excluded_ids:
            by_document.setdefault(reference.source_document_id, []).append(reference.id)
    return {document_id: sorted(ids) for document_id, ids in by_document.items()}


def _failure_reason(document_id: str, execution_records: Sequence[ExecutionRecord]) -> str:
    """The recorded error class for a failed ingestion, where a record names this document."""
    for record in execution_records:
        if record.error_type and document_id in (
            *record.input_object_ids,
            *record.output_object_ids,
        ):
            return f"ingestion failed: {record.error_type}"
    return "ingestion was attempted and did not complete; the run's execution record has the error"


def coverage_ledger(
    *,
    documents: Sequence[SourceDocument],
    evidence_references: Sequence[EvidenceReference],
    execution_records: Sequence[ExecutionRecord],
) -> tuple[CoverageEntry, ...]:
    """Derive the DEC-071 ledger. One entry per document, in identifier order."""
    excluded = _excluded_by_document(evidence_references, execution_records)

    entries: list[CoverageEntry] = []
    for document in sorted(documents, key=lambda item: item.id):
        if document.ingestion_status is IngestionStatus.INGESTED:
            names = excluded.get(document.id, [])
            if names:
                entries.append(
                    CoverageEntry(
                        document_id=document.id,
                        filename=document.filename,
                        bucket=CoverageBucket.REVIEWED_WITH_EXCLUSIONS,
                        justification=(
                            f"reviewed; an evidence budget excluded {', '.join(names)} "
                            f"from at least one agent's input"
                        ),
                        excluded_evidence_ids=tuple(names),
                    )
                )
            else:
                entries.append(
                    CoverageEntry(
                        document_id=document.id,
                        filename=document.filename,
                        bucket=CoverageBucket.REVIEWED,
                        justification="ingested; its evidence was available to every stage",
                    )
                )
        elif document.ingestion_status is IngestionStatus.FAILED:
            entries.append(
                CoverageEntry(
                    document_id=document.id,
                    filename=document.filename,
                    bucket=CoverageBucket.COULD_NOT_PROCESS,
                    justification=_failure_reason(document.id, execution_records),
                )
            )
        elif document.ingestion_status is IngestionStatus.REGISTERED:
            entries.append(
                CoverageEntry(
                    document_id=document.id,
                    filename=document.filename,
                    bucket=CoverageBucket.EXCLUDED_BY_RULE,
                    justification=(
                        "registered without indexing (`trace source add --no-index`); its bytes "
                        "are preserved and nothing read them"
                    ),
                )
            )
        else:  # pragma: no cover - a fourth status does not exist today
            raise ValueError(
                f"{document.id} carries ingestion_status "
                f"{document.ingestion_status!r}, which no coverage bucket maps (DEC-071). A "
                f"new disposition needs a bucket before it can render, because an unlisted "
                f"document is the failure the ledger exists to prevent."
            )
    return tuple(entries)
