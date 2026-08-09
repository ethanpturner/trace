## Context

`docs/architecture/agent-design.md` section 22 specifies that agents receive evidence through
an application-controlled retrieval interface — retrieve evidence by identifier is the first
capability listed — and that agents receive no arbitrary filesystem access, no shell, and no
database writes. `docs/architecture/data-model.md` section 35 states that the database stores
references and content hashes for filesystem artifacts, which is only useful if something
checks them, and section 8 requires that evidence references point to a valid source document
and that evidence text is not modified after creation. Without a retrieval and verification
layer, every later component reads files directly and the tool-access constraint has no
enforcement point to sit behind.

## Scope

- Add `src/trace_ai/services/evidence/index.py`.
- Implement an `EvidenceIndex` scoped to one assessment, over its evidence references and
  source documents, with:
  - `get(evidence_id) -> EvidenceReference`
  - `for_document(source_document_id) -> list[EvidenceReference]`
  - `verify(evidence_id) -> VerificationResult`, re-reading the artifact at the recorded
    location and comparing the recorded `content_hash` against the text found there
  - `verify_all()` returning the references that no longer match
- Distinguish three verification outcomes: matches, artifact missing, and content changed. A
  single boolean would collapse "the file is gone" into "the quote is stale", and those need
  different responses.
- Reject a lookup for an identifier belonging to another assessment, rather than returning a
  result. This is the enforcement point for the assessment-data boundary on the read path.
- Implement `render_for_prompt(evidence_ids)` returning a plain data structure — identifier,
  location, quoted text, source filename — carrying no filesystem path. This is the shape
  evidence takes when it reaches a model-assisted step, and it exists so that no future agent
  code opens a file. It returns data; it assembles no prompt and imports nothing from a
  provider SDK.
- Add `tests/unit/test_evidence_index.py`.

## Acceptance criteria

- [ ] `get` returns the reference for a known identifier and raises a named error for an
      unknown one.
- [ ] A lookup crossing assessments raises. Asserted directly.
- [ ] `verify` reports a match for a freshly indexed document.
- [ ] `verify` reports content changed after the artifact is edited under the reference. This
      is the stale-evidence case and is the reason `content_hash` is stored.
- [ ] `verify` reports artifact missing, distinctly from content changed, when the file is
      removed.
- [ ] `verify_all` over `demo/forgeflow/input/` reports no mismatches immediately after
      indexing.
- [ ] `render_for_prompt` output contains no absolute path, no `original_path`, and no
      `normalized_path`. Asserted by searching the serialized output.
- [ ] `render_for_prompt` output is JSON-serializable and reproduces `quoted_text` unmodified,
      including for the injection fixture, which is passed through as data rather than altered.
- [ ] The module imports nothing from `anthropic`, `openai`, `langchain`, `langgraph`, or
      `instructor`. Asserted by a test, because the module's purpose is to be the boundary that
      later agent code sits behind.
- [ ] Tests need no API key and run under a bare `uv run pytest`.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Prompt assembly and the trusted/untrusted delimiting in `agent-design.md` section 24, which
  belongs with the first agent.
- Evidence ranking, relevance scoring, or similarity retrieval. `current-architecture.md`
  section 17 defers vector infrastructure.
- Deciding whether evidence text is duplicated into the database or resolved from normalized
  files (`data-model.md` open question 2). The index works either way; only its construction
  changes.
- `EvidenceAssessment` (section 20), deferred by section 40.
- Automatic re-indexing when verification fails. The index reports; it does not repair.

## References

- `docs/architecture/agent-design.md` sections 22 (Tool Access Model), 23 (Retrieval Design),
  24 (Prompt Structure)
- `docs/architecture/data-model.md` sections 8 (EvidenceReference validation rules),
  35 (Data Persistence), 39 question 2, 32 (Object Lineage)
- `docs/architecture/current-architecture.md` sections 12 (Security Boundaries), 5.16, 17
- `CLAUDE.md`, "Binding design constraints"
