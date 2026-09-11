"""The ingestion pipeline: the only writer to the retrieval index.

Runs nightly. Reads two sources, the published help-center repository and the support platform's
resolved-tickets export, chunks and embeds them, and records the source reference and timestamp on
every indexed item. Changed chunks are replaced by source reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from relay_answers.embeddings import embed
from relay_answers.index import Chunk, RetrievalIndex
from relay_answers.retention import propagate_deletions

if TYPE_CHECKING:
    from collections.abc import Iterable

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CHUNK_WORDS = 120


@dataclass(frozen=True)
class HelpArticle:
    article_id: str
    title: str
    body: str


@dataclass(frozen=True)
class ResolvedTicket:
    """One row of the resolved-tickets export. `deleted_at` is the platform's tombstone."""

    ticket_id: str
    workspace_id: str
    body: str
    resolved_at: datetime
    deleted_at: datetime | None = None


def mask_emails(text: str) -> str:
    """Replace email addresses with a fixed marker. The export arrives with this already applied;
    it is applied again here so a source that skipped it cannot reach the index unmasked."""
    return _EMAIL.sub("[email]", text)


def chunk_text(text: str, words_per_chunk: int = CHUNK_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[start : start + words_per_chunk])
        for start in range(0, len(words), words_per_chunk)
    ]


def _chunks_for(
    source_ref: str,
    source_kind: str,
    workspace_id: str | None,
    text: str,
    indexed_at: datetime,
) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"{source_ref}#{position}",
            source_ref=source_ref,
            source_kind=source_kind,
            workspace_id=workspace_id,
            text=piece,
            indexed_at=indexed_at,
            embedding=embed(piece),
        )
        for position, piece in enumerate(chunk_text(text))
    ]


@dataclass
class IngestionReport:
    articles_indexed: int = 0
    tickets_indexed: int = 0
    sources_removed: int = 0


def run_nightly(
    index: RetrievalIndex,
    articles: Iterable[HelpArticle],
    tickets_export: Iterable[ResolvedTicket],
    now: datetime | None = None,
) -> IngestionReport:
    """One ingestion run over both sources, then deletion propagation."""
    indexed_at = now or datetime.now(UTC)
    report = IngestionReport()
    export = list(tickets_export)

    for article in articles:
        source_ref = f"help-center/{article.article_id}"
        text = f"{article.title}\n\n{article.body}"
        index.replace_source(
            source_ref, _chunks_for(source_ref, "help-center", None, text, indexed_at)
        )
        report.articles_indexed += 1

    for ticket in export:
        if ticket.deleted_at is not None:
            continue
        source_ref = f"tickets/{ticket.ticket_id}"
        text = mask_emails(ticket.body)
        index.replace_source(
            source_ref, _chunks_for(source_ref, "ticket", ticket.workspace_id, text, indexed_at)
        )
        report.tickets_indexed += 1

    report.sources_removed = propagate_deletions(index, export)
    return report
