## Context

`docs/architecture/data-model.md` section 2.2 states that important conclusions should link to
specific source locations and that a source document alone is not sufficiently precise.
Section 8 defines EvidenceReference and its validation rules; section 32 places it second in
the lineage chain running from source document to final report; section 40 makes it the fourth
object to implement. Ten other objects in the model carry `evidence_ids`, so this is the joint
the project's traceability argument turns on, and it is defined before the loader because the
loader's output is ultimately measured in evidence references.

**Blocked on DX-03** (evidence location representation, what normalization does, and whether
line numbers index original or normalized content). Section 8 provides five location fields —
`section_title`, `chunk_index`, `start_line`, `end_line`, `page_number` — and says only that
at least one usable location field should be present when available. That is workable for a
Markdown heading and insufficient for a YAML mapping key, and nothing states which document
`start_line` indexes.

## Scope

- Add `src/trace_ai/domain/evidence.py` with `EvidenceReference`, deriving from `DomainModel`.
- Fields, exactly as data-model.md section 8 types them: `id`, `source_document_id`,
  `assessment_id`, `section_title`, `chunk_index`, `start_line`, `end_line`, `page_number`,
  `quoted_text`, `normalized_text`, `content_hash`, `source_origin` (`SourceOrigin`),
  `created_at`, `metadata`.
- Implement section 8's validation rules as schema validators:
  - `quoted_text` must not be empty, which includes whitespace-only
  - at least one usable source-location field must be present
  - `source_document_id` carries the `src` prefix and `assessment_id` the `asm` prefix
- Apply the location representation DX-03 decides: what `chunk_index` counts, what
  `section_title` holds for a format with no headings, and which `metadata` keys carry a
  structured-format location. The decision must not add a field to the object; section 8 is
  authoritative and a new field is a design change.
- Document the immutability rule on the class rather than leaving the frozen config looking
  incidental. Section 8 states that evidence text is not modified after creation and that
  corrections create a new evidence reference.
- Validate `start_line <= end_line`, both positive, and `chunk_index` non-negative.
- Constrain `content_hash` to the `sha256:<hex>` form, reusing the hashing helper.
- Add `tests/unit/test_evidence_reference.py`.

## Acceptance criteria

- [ ] Every field in data-model.md section 8 is present with the documented type and
      required/optional status; the conformance guard covers it.
- [ ] Empty or whitespace-only `quoted_text` is rejected.
- [ ] An EvidenceReference carrying no location field at all is rejected, with a message
      naming the acceptable location fields.
- [ ] `start_line > end_line` is rejected.
- [ ] The model is frozen; an attempt to change `quoted_text` raises. The test docstring names
      the section 8 rule.
- [ ] The example in data-model.md section 8 — `evd-014`, `section_title: Authentication`,
      lines 41 to 46, `source_origin: uploaded_document` — constructs successfully as written.
- [ ] A location expressed in the DX-03 representation for a YAML source validates, and one
      that omits every location field does not.
- [ ] There is no field, flag, or convention by which an EvidenceReference expresses the
      absence of something. Evidence cites text that exists. Under DEC-009, "the document does
      not say" is a `DocumentationGap` or a `Question`, which are separate objects in sections
      23 and 22. A test asserts that no construction path yields an evidence reference with
      empty `quoted_text`.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Producing evidence references from a document; that is the indexing issue.
- Verifying that quoted text still matches its source; that is the evidence index issue.
- `EvidenceAssessment` (section 20), deferred by section 40 until the main workflow operates.
- `EvidenceStrength` (section 4.3). The type exists but no field in section 8 carries it, and
  adding one would be a schema change.
- Whether evidence text is duplicated into the database or resolved from normalized files
  (open question 2). The object is the same either way.

## References

- `docs/architecture/data-model.md` sections 8 (EvidenceReference), 2.2 (Evidence must be
  addressable), 22 (Question), 23 (DocumentationGap), 32 (Object Lineage), 39 questions 2 and
  3, 40
- `docs/architecture/decision-log.md` DEC-009, and DX-03 once recorded
- `docs/architecture/current-architecture.md` sections 2.1 (Evidence over assumptions),
  19 question 4
- `docs/product/roadmap.md`, Stage 2, "Ingestion and evidence indexing"
