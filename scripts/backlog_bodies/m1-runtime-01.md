## Context

`src/trace_ai/__init__.py` installs a root logging configuration at the configured level, with
a plain format string. `docs/architecture/current-architecture.md` section 5.17 requires the
trace and audit service to record run identifiers, node names, versions, timings, errors,
retries, and status transitions, and states that sensitive prompt content and source data
should not automatically be sent to an external tracing provider. Two categories of content
must never reach a log line: provider credentials, which
`src/trace_ai/config.py` already holds as `SecretStr` so they cannot leak through `repr()`,
and source-document content, which is untrusted under
`current-architecture.md` section 12 and may contain sensitive information. The current
formatter offers no defense for either once a caller passes the wrong object to `%s`.

## Scope

- Add `src/trace_ai/logging.py` with a structured formatter emitting key-value or JSON records
  carrying at minimum: timestamp, level, logger, message, and any bound context.
- Add a redaction filter that:
  - renders a `SecretStr` as a fixed placeholder rather than its value, wherever it appears in
    a message argument or in bound context
  - refuses to emit a field whose name marks it as source-derived, replacing it with an
    identifier and a length
- Add helpers for binding assessment-scoped context (`assessment_id`, `source_document_id`,
  `workflow_run_id`) so that a log line can be traced to an assessment without a caller
  formatting the identifier into every message.
- Establish the rule in one place: source-document content is referenced by
  `EvidenceReference.id` or `SourceDocument.id`, never quoted into a log record. Document it in
  the module docstring.
- Update `configure_logging` in `src/trace_ai/__init__.py` to install the formatter and the
  filter, preserving the existing `force=True` behavior and the level from `Settings`.
- Extend `tests/unit/test_entrypoint.py` or add `tests/unit/test_logging.py`.

## Acceptance criteria

- [ ] A log record carrying a `SecretStr` emits a placeholder; the secret value does not appear
      in the formatted output. Asserted with `caplog` for a value that would be conspicuous.
- [ ] A log record carrying a raw provider key string in a field marked as secret is redacted.
- [ ] A log record carrying source-document content in a field marked as source-derived is
      replaced by an identifier and a length.
- [ ] Bound context appears in the emitted record and is scoped per record, not leaked between
      records.
- [ ] `configure_logging` continues to apply the level from `Settings`, and the existing
      assertion in `tests/unit/test_entrypoint.py` still passes.
- [ ] The output of `main()` still reports configured credentials as booleans only and never
      the key material, as `tests/unit/test_entrypoint.py` already asserts.
- [ ] Logging adds no runtime dependency.
- [ ] `uv run mypy` passes strict.

## Out of scope

- External tracing. `current-architecture.md` section 5.17 allows LangSmith during development
  subject to a data-handling review, and DEC-007 leaves the orchestrator unaccepted; local
  audit records remain the authoritative execution record either way.
- The execution ledger itself, which is a separate issue.
- Deciding whether `AssessmentConfiguration.enable_external_tracing` or
  `Settings.langsmith_tracing` is authoritative.
- Log shipping, rotation, or retention.

## References

- `docs/architecture/current-architecture.md` sections 5.17 (Trace and Audit Service),
  12 (Security Boundaries), 2.5 (Explainability by design)
- `docs/architecture/data-model.md` sections 27 (ExecutionRecord, `error_message` is a "Safe
  error message"), 36 (Data Retention)
- `src/trace_ai/config.py`, `src/trace_ai/__init__.py`
- `tests/unit/test_config.py`, `tests/unit/test_entrypoint.py`
