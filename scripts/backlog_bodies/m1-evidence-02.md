## Context

`docs/architecture/agent-design.md` sections 3 and 4 place a Normalization and Evidence
Indexing node between Document Ingestion and Context Extraction and classify it as
deterministic, with no model involvement. `docs/architecture/current-architecture.md` section
5.4 assigns it the responsibilities the loader does not cover: normalize text, divide long
documents into addressable sections, and preserve source locations. Roadmap Stage 2 requires
addressable evidence references carrying a source identifier, a section or line location,
quoted text, and a content hash. This node is what makes section 5.4's claim — that every
extracted claim can link back to source document, section or chunk, relevant text, content
hash, and ingestion timestamp — true rather than intended.

**Blocked on DX-03**, which settles what normalization does, whether `start_line` indexes the
original or the normalized artifact, how a location in JSON and YAML is expressed, and what a
chunk is.

## Scope

- Add `src/trace_ai/services/ingestion/normalize.py` and
  `src/trace_ai/services/ingestion/segment.py`, implementing exactly the rules DX-03 records.
- Add `src/trace_ai/services/evidence/indexing.py` with
  `index_document(source_document) -> list[EvidenceReference]`.
- Write the normalized artifact through the artifact store's `normalized/` directory, then set
  `normalized_path`, `ingested_at`, and `ingestion_status` on the SourceDocument. The loader
  leaves all three unset.
- Segment Markdown by heading, plain text by the rule DX-03 records, and JSON and YAML
  structurally, producing one EvidenceReference per addressable unit with `chunk_index`
  assigned in document order.
- Populate `quoted_text` from the source and `content_hash` over the quoted text, so an
  evidence reference is verifiable independently of the document hash.
- Derive `assessment_id` and `source_origin` from the parent SourceDocument rather than
  accepting them as arguments. Deriving them is what keeps the assessment-data boundary from
  depending on a caller passing the right string.
- Handle the shapes the demo corpus actually contains: `architecture-overview.md` uses 28
  second-level and 8 third-level headings across 734 lines, while
  `sample-repository-notes.md` uses first-level headings for the same purpose, so heading
  depth is not consistent across the corpus and the segmenter must not assume it is.
- Add `tests/unit/test_evidence_indexing.py`, running against `demo/forgeflow/input/`.

## Acceptance criteria

- [ ] Indexing all eight files in `demo/forgeflow/input/` produces EvidenceReference objects
      that all validate.
- [ ] Every reference's `assessment_id` equals its parent SourceDocument's `assessment_id`,
      and its `source_document_id` equals that document's `id`. Asserted directly; this is the
      assessment-data boundary in `current-architecture.md` section 12.
- [ ] `quoted_text` appears verbatim in the source at the recorded location, asserted by
      re-reading the file rather than by trusting the indexer's own bookkeeping.
- [ ] `chunk_index` is contiguous from zero and ordered by position within each document.
- [ ] Indexing is deterministic: two runs over the same file produce identical output apart
      from identifiers, including identical `content_hash` values.
- [ ] `architecture-overview.md` produces section titles matching its actual headings, at both
      heading levels.
- [ ] `sample-repository-notes.md`, whose headings are first-level, segments correctly rather
      than collapsing to one chunk.
- [ ] `structured-system-input.yaml` produces references whose locations resolve under the
      DX-03 representation, covering at least the nested `components` list and the
      `security_controls` mapping.
- [ ] A document with no headings at all produces at least one valid reference.
- [ ] Normalization is idempotent: normalizing an already-normalized artifact changes nothing.
- [ ] The injection block in `sample-repository-notes.md` is indexed like any other content and
      its text is preserved in `quoted_text`.
- [ ] The node makes no model call and needs no API key.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Selecting which evidence an agent receives. `agent-design.md` section 23 covers retrieval
  design and belongs with the agents.
- Semantic or embedding-based chunking. `current-architecture.md` section 17 defers vector
  database infrastructure.
- Deduplicating identical text across documents.
- PDF page numbers; `page_number` stays unpopulated until PDF ingestion exists.
- Extracting meaning from content. This node addresses text; it does not interpret it.

## References

- `docs/architecture/agent-design.md` sections 3 (Workflow Overview, the `CHUNK` node),
  4 (Component Classification), 23 (Retrieval Design)
- `docs/architecture/current-architecture.md` sections 5.4 (Document Ingestion, "Output"),
  2.6, 12, 17, 19 question 4
- `docs/architecture/data-model.md` sections 8 (EvidenceReference), 2.2, 32 (Object Lineage),
  39 question 3
- `docs/product/roadmap.md`, Stage 2, "Ingestion and evidence indexing"
- `docs/architecture/decision-log.md` DX-03 once recorded
