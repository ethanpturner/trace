## Context

`docs/architecture/current-architecture.md` section 5.4 specifies the Document Ingestion
component and names its four MVP inputs — Markdown, plain text, JSON, YAML — with PDF, Office,
repository, and web-page ingestion deferred. `docs/architecture/agent-design.md` sections 3
and 4 classify Document Ingestion as a deterministic node with no model involvement.
`demo/forgeflow/input/` holds what it has to handle: seven Markdown files between 142 and 734
lines, and one YAML file. Ingestion is the first node in the workflow, and every object
downstream traces back to a SourceDocument it produced.

## Scope

- Add `src/trace_ai/services/ingestion/loader.py`.
- Implement `load_document(assessment, path, *, origin, trust_level) -> SourceDocument`,
  performing the section 5.4 responsibilities that do not depend on segmentation: accept the
  input file, validate the format, assign a stable identifier, preserve the original content
  through the artifact store, generate the content hash, and record ingestion metadata.
- Implement `load_directory(assessment, path) -> list[SourceDocument]` for the demo input
  directory, with deterministic ordering so two runs produce the same sequence.
- Determine `media_type` from the file extension against an explicit allowlist: `.md` and
  `.markdown`, `.txt`, `.json`, `.yaml` and `.yml`. Reject everything else with a message
  naming the supported set. Do not sniff content in order to widen the allowlist.
- Parse JSON with `json.loads` and YAML with `yaml.safe_load`. `safe_load` is not a style
  preference here: `yaml.load` with the default loader constructs arbitrary Python objects
  from document content, which is code execution driven by an untrusted input file.
  `tests/unit/test_requirements_catalog.py` sets the precedent, and the `S` ruff rules flag
  the alternative.
- Enforce a maximum file size, and reject input that is not valid UTF-8 with a named error
  rather than a decode traceback.
- Decide and pin which `SourceOrigin` applies to
  `demo/forgeflow/input/structured-system-input.yaml`. It is a file on disk like the others,
  which argues for `uploaded_document`, and it is the structured project definition named in
  `docs/architecture/project-scope.md` under "MVP Capabilities", which argues for
  `structured_input`. Record the choice in the module docstring; the loader must not answer it
  differently on different calls.
- Populate `metadata` with format-derived facts only: line count, byte length, heading count.
  No interpretation of what the content means.
- Set `ingestion_status` to the registered value and leave `normalized_path` and `ingested_at`
  unset; the indexing node fills them.
- Add `tests/unit/test_document_loader.py`, running against `demo/forgeflow/input/`.

## Acceptance criteria

- [ ] All eight files in `demo/forgeflow/input/` load, producing eight valid SourceDocument
      objects with distinct identifiers.
- [ ] `media_type` is `text/markdown` for the seven `.md` files and `application/yaml` for
      `structured-system-input.yaml`.
- [ ] A `.pdf`, a `.docx`, and an extensionless file are each rejected with a message naming
      the four supported formats. Rejecting them is the specified behavior under section 5.4,
      not a limitation.
- [ ] `content_hash` is reproducible: loading the same file twice yields the same hash, and a
      one-byte change yields a different one.
- [ ] The stored original content is byte-identical to the input file.
- [ ] A YAML document containing a `!!python/object/apply` tag is rejected rather than
      constructed. Asserted directly.
- [ ] A JSON document that is not an object or array parses or is rejected according to a
      stated rule, not by accident.
- [ ] A file over the size limit is rejected without being read into memory in full.
- [ ] Invalid UTF-8 produces a named error, not a `UnicodeDecodeError` traceback.
- [ ] `load_directory` returns the same order on repeated runs.
- [ ] The `SourceOrigin` choice for `structured-system-input.yaml` is documented and pinned by
      a test.
- [ ] The loader makes no model call and needs no API key; it runs under a bare
      `uv run pytest`, which deselects the `integration` and `evaluation` markers.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Normalization, segmentation, and evidence references. Those depend on DX-03 and are the
  indexing issue.
- Any inspection of document content for meaning, security relevance, or injection. The
  untrusted-source boundary issue covers why the loader deliberately does not do this.
- PDF, Office, repository, and web-page ingestion (`current-architecture.md` sections 5.4 and
  17).
- A `trace source add` command; the CLI issue calls this loader.

## References

- `docs/architecture/current-architecture.md` sections 5.4 (Document Ingestion),
  2.6 (Deterministic where practical), 12 (Security Boundaries), 17 (Deferred Capabilities)
- `docs/architecture/agent-design.md` sections 3 (Workflow Overview), 4 (Component
  Classification), 2.3 (Source content is data, not instruction)
- `docs/architecture/data-model.md` sections 7 (SourceDocument), 4.4 (SourceOrigin)
- `docs/architecture/project-scope.md`, "MVP Capabilities"
- `docs/product/roadmap.md`, Stage 2, "Ingestion and evidence indexing"
- `tests/unit/test_requirements_catalog.py` (`yaml.safe_load` precedent)
