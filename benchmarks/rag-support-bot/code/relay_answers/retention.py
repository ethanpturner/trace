"""Deletion propagation from the support platform to the index."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from relay_answers.index import RetrievalIndex
    from relay_answers.ingestion import ResolvedTicket


def propagate_deletions(index: RetrievalIndex, export: Iterable[ResolvedTicket]) -> int:
    """Remove the chunks of every ticket the export marks deleted.

    The support platform records a deletion by setting `deleted_at` on the ticket's export row.
    Each such ticket's chunks, and with them its embeddings, are removed from the index. Returns
    how many sources were removed.
    """
    removed = 0
    for ticket in export:
        if ticket.deleted_at is None:
            continue
        if index.remove_source(f"tickets/{ticket.ticket_id}"):
            removed += 1
    return removed
