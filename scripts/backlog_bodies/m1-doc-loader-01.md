## Context

`docs/architecture/data-model.md` section 7 is authoritative for SourceDocument, the object
representing one original source supplied to an assessment. It is third in section 40's
implementation priority list, and the loader produces it. Section 7 enumerates four
`trust_level` values but leaves `ingestion_status` as a required string with no enumerated
values, so that vocabulary is settled here rather than invented at each call site.

## Scope

- Add `src/trace_ai/domain/source_document.py` with `SourceDocument`, deriving from
  `DomainModel`.
- Fields, exactly as section 7 types them: `id`, `assessment_id`, `filename`, `media_type`,
  `origin` (`SourceOrigin`), `original_path`, `normalized_path`, `content_hash`, `title`,
  `created_at`, `ingested_at`, `ingestion_status`, `trust_level`, `metadata`.
- Add a `TrustLevel` enum with exactly the four values in section 7: `untrusted`,
  `reviewer_supplied`, `system_fixture`, `trusted_catalog`. Default to `untrusted`. Section 7
  states that even reviewer-supplied documents should generally be treated as data rather than
  workflow instructions, and a default that has to be overridden to become unsafe is the point
  of the field.
- Add an `IngestionStatus` enum. Section 7 does not enumerate it, so propose the vocabulary
  here and record it as a sub-decision in the pull request description and in
  `docs/architecture/decision-log.md`. It must distinguish registered from normalized and must
  carry a failure state: section 7 makes `ingested_at` optional precisely because registration
  and successful ingestion are separate events.
- Constrain `content_hash` to `sha256:<hex>`, reusing the hashing helper.
- Constrain `media_type` to the four MVP input formats named in
  `docs/architecture/current-architecture.md` section 5.4: `text/markdown`, `text/plain`,
  `application/json`, `application/yaml`.
- Require `assessment_id` to carry the `asm` prefix and `id` the `src` prefix.
- Add `tests/unit/test_source_document.py`.

## Acceptance criteria

- [ ] Every field in data-model.md section 7 is present with the documented type and
      required/optional status; the conformance guard covers it.
- [ ] `trust_level` accepts only the four values in section 7.
- [ ] A SourceDocument constructed without an explicit `trust_level` is `untrusted`. Asserted
      directly, because the default is the control.
- [ ] `content_hash` rejects anything that is not `sha256:` followed by 64 lowercase hex
      characters.
- [ ] `media_type` rejects a format outside the four MVP inputs, with a message naming the
      supported set.
- [ ] `ingested_at` may be unset while `ingestion_status` indicates registration; a status
      indicating successful ingestion requires `ingested_at`.
- [ ] A failed ingestion is representable: the status carries a failure value and
      `normalized_path` stays unset.
- [ ] The `IngestionStatus` vocabulary and its rationale are recorded in
      `docs/architecture/decision-log.md`, because section 7 does not define it.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Reading a file. This issue is the object only.
- PDF and Office media types, deferred by `current-architecture.md` section 5.4.
- Persisting SourceDocument rows.
- Deciding which `SourceOrigin` applies to `demo/forgeflow/input/structured-system-input.yaml`;
  the loader issue settles that, because it is a question about how a file is supplied rather
  than about the schema.

## References

- `docs/architecture/data-model.md` sections 7 (SourceDocument), 4.4 (SourceOrigin),
  8 (`content_hash` format precedent), 40
- `docs/architecture/current-architecture.md` sections 5.4 (Document Ingestion),
  12 (Security Boundaries)
- `docs/architecture/agent-design.md` section 2.3 (Source content is data, not instruction)
