"""The retrieval index: embeddings of help-center articles and resolved support tickets.

One index serves every workspace. Each chunk records its source reference, the kind of source,
the workspace it came from where it came from one, and the time it was indexed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from relay_answers.embeddings import cosine

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_ref: str
    source_kind: str
    workspace_id: str | None
    text: str
    indexed_at: datetime
    embedding: list[float]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class RetrievalIndex:
    """An in-memory vector index keyed by chunk identifier."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}

    def __len__(self) -> int:
        return len(self._chunks)

    def replace_source(self, source_ref: str, chunks: list[Chunk]) -> None:
        """Replace every chunk carrying `source_ref` with `chunks`."""
        self.remove_source(source_ref)
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk

    def remove_source(self, source_ref: str) -> int:
        """Remove every chunk carrying `source_ref`; returns how many were removed."""
        doomed = [key for key, chunk in self._chunks.items() if chunk.source_ref == source_ref]
        for key in doomed:
            del self._chunks[key]
        return len(doomed)

    def source_refs(self) -> set[str]:
        return {chunk.source_ref for chunk in self._chunks.values()}

    def search(self, query_embedding: list[float], k: int) -> list[Hit]:
        """The top `k` chunks by embedding similarity across the whole index."""
        scored = [
            Hit(chunk=chunk, score=cosine(query_embedding, chunk.embedding))
            for chunk in self._chunks.values()
        ]
        scored.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return scored[:k]
