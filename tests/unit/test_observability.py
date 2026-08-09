"""Tests for structured logging and the redaction filter.

These are written against the **formatted output**, not against the filter's return value. A
redaction test that inspects an intermediate structure proves the filter did something; it does
not prove the secret is absent from the bytes that reach the log. The whole point is the bytes,
so every assertion here parses what the handler actually wrote.

The two conspicuous values -- `sk-ant-do-not-log-me` and the fake source passage -- are chosen so
a partial failure is obvious in the diff rather than requiring a careful read. Issue #48.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from pydantic import SecretStr

from trace_ai.observability import (
    SECRET_PLACEHOLDER,
    RedactionFilter,
    StructuredFormatter,
    bind,
    bound_context,
    install,
)

SECRET = "sk-ant-do-not-log-me"
SOURCE_PASSAGE = "All webhook requests are validated against a shared secret before processing."


@pytest.fixture
def emitted(
    caplog: pytest.LogCaptureFixture,
) -> Any:
    """Emit through a real handler and return the parsed JSON of each record.

    `caplog` alone captures records before formatting, which is exactly the gap these tests exist
    to close, so the formatter and filter are attached to a handler and its output is read back.
    """
    import io

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(RedactionFilter())

    logger = logging.getLogger("trace_ai.test")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    def read() -> list[dict[str, Any]]:
        return [json.loads(line) for line in stream.getvalue().splitlines() if line]

    try:
        yield logger, read
    finally:
        logger.handlers = []
        logger.propagate = True


def test_a_record_is_json_with_the_expected_keys(emitted: Any) -> None:
    logger, read = emitted
    logger.info("node completed")

    (record,) = read()
    assert record["level"] == "INFO"
    assert record["logger"] == "trace_ai.test"
    assert record["message"] == "node completed"
    assert record["timestamp"].endswith("+00:00"), "timestamps are UTC and say so"


def test_bound_context_appears_in_the_record(emitted: Any) -> None:
    """Section 5.17's fields, carried as keys rather than formatted into a sentence."""
    logger, read = emitted
    with bind(assessment_id="asm-001", workflow_run_id="run-001"):
        logger.info("node started", extra={"node": "context_validation", "attempt": 1})

    (record,) = read()
    assert record["assessment_id"] == "asm-001"
    assert record["workflow_run_id"] == "run-001"
    assert record["node"] == "context_validation"
    assert record["attempt"] == 1


def test_context_does_not_leak_between_records(emitted: Any) -> None:
    """The reason binding is scoped: the next assessment must not inherit the last one's id."""
    logger, read = emitted
    with bind(assessment_id="asm-001"):
        logger.info("inside")
    logger.info("outside")

    inside, outside = read()
    assert inside["assessment_id"] == "asm-001"
    assert "assessment_id" not in outside


def test_nested_binding_merges_with_the_inner_value_winning(emitted: Any) -> None:
    logger, read = emitted
    with bind(assessment_id="asm-001", node="ingest"), bind(node="normalize"):
        logger.info("nested")

    (record,) = read()
    assert record["assessment_id"] == "asm-001"
    assert record["node"] == "normalize"


def test_binding_is_restored_after_an_exception() -> None:
    """A node that raises must not leave its identifiers bound for everything after it."""
    with pytest.raises(RuntimeError), bind(assessment_id="asm-001"):
        raise RuntimeError("node failed")
    assert bound_context() == {}


def test_a_secret_str_in_context_is_replaced(emitted: Any) -> None:
    logger, read = emitted
    logger.info("configured", extra={"provider_credential": SecretStr(SECRET)})

    output = json.dumps(read())
    assert SECRET not in output
    assert SECRET_PLACEHOLDER in output


def test_a_secret_str_in_a_message_argument_is_replaced(emitted: Any) -> None:
    """`%s` on a SecretStr renders `**********`; this covers the case regardless."""
    logger, read = emitted
    logger.info("key is %s", SecretStr(SECRET))

    (record,) = read()
    assert SECRET not in json.dumps(record)


def test_a_raw_key_string_in_a_secret_named_field_is_replaced(emitted: Any) -> None:
    """The case `SecretStr` cannot cover: a plain string that never went through `Settings`."""
    logger, read = emitted
    logger.info("client built", extra={"anthropic_api_key": SECRET})

    (record,) = read()
    assert record["anthropic_api_key"] == SECRET_PLACEHOLDER
    assert SECRET not in json.dumps(record)


@pytest.mark.parametrize(
    "field",
    ["api_key", "anthropic_api_key", "auth_token", "client_secret", "password", "authorization"],
)
def test_every_secret_named_field_is_replaced(emitted: Any, field: str) -> None:
    logger, read = emitted
    logger.info("built", extra={field: SECRET})

    assert SECRET not in json.dumps(read())


def test_a_secret_nested_in_a_container_is_replaced(emitted: Any) -> None:
    """Context is not always flat; a dict of provider settings is the obvious case."""
    logger, read = emitted
    logger.info("providers", extra={"providers": {"anthropic": SecretStr(SECRET)}})

    assert SECRET not in json.dumps(read())


def test_source_content_is_replaced_by_a_length(emitted: Any) -> None:
    """The DEC-015 verbatim excerpt, which must never be quoted into a log line."""
    logger, read = emitted
    logger.info("evidence indexed", extra={"quoted_text": SOURCE_PASSAGE})

    (record,) = read()
    assert SOURCE_PASSAGE not in json.dumps(record)
    assert str(len(SOURCE_PASSAGE)) in record["quoted_text"]


def test_redacted_source_content_points_at_its_object(emitted: Any) -> None:
    """An identifier and a length are what make the record debuggable without the content."""
    logger, read = emitted
    with bind(evidence_id="evd-014"):
        logger.info("evidence indexed", extra={"quoted_text": SOURCE_PASSAGE})

    (record,) = read()
    assert "evd-014" in record["quoted_text"]


def test_the_reference_falls_back_through_the_available_identifiers(emitted: Any) -> None:
    logger, read = emitted
    with bind(source_document_id="src-002"):
        logger.info("normalized", extra={"normalized_text": SOURCE_PASSAGE})

    (record,) = read()
    assert "src-002" in record["normalized_text"]


@pytest.mark.parametrize(
    "field", ["quoted_text", "normalized_text", "raw_text", "document_content", "excerpt"]
)
def test_every_source_named_field_is_replaced(emitted: Any, field: str) -> None:
    logger, read = emitted
    logger.info("loaded", extra={field: SOURCE_PASSAGE})

    assert SOURCE_PASSAGE not in json.dumps(read())


def test_an_identifier_is_not_mistaken_for_source_content(emitted: Any) -> None:
    """Redaction has to leave the identifiers, or the record loses the thing it is for."""
    logger, read = emitted
    logger.info("indexed", extra={"source_document_id": "src-002", "evidence_id": "evd-014"})

    (record,) = read()
    assert record["source_document_id"] == "src-002"
    assert record["evidence_id"] == "evd-014"


def test_context_cannot_displace_the_record_fields(emitted: Any) -> None:
    """A bound `level` would make one record's severity mean something other than every other's."""
    logger, read = emitted
    with bind(level="TRACE", message="not the message"):
        logger.warning("the real message")

    (record,) = read()
    assert record["level"] == "WARNING"
    assert record["message"] == "the real message"


def test_an_exception_is_recorded(emitted: Any) -> None:
    logger, read = emitted
    try:
        raise ValueError("node failed")
    except ValueError:
        logger.exception("node raised")

    (record,) = read()
    assert "ValueError: node failed" in record["exception"]


def test_a_record_the_filter_cannot_help_with_is_documented_not_silently_passed(
    emitted: Any,
) -> None:
    """The stated limit, asserted so it is a known gap rather than an assumed defence.

    A secret interpolated into the message before `logging` sees it is a plain string with no
    field name and no type. Nothing distinguishes it from prose, and the module docstring says so.
    """
    logger, read = emitted
    logger.info(f"key is {SECRET}")  # pre-formatted on purpose; this is the case that leaks

    assert SECRET in json.dumps(read()), (
        "if this now passes, the filter gained a capability its docstring denies having"
    )


def test_install_replaces_root_handlers() -> None:
    """`basicConfig(force=True)` behaviour, kept for the reason that mattered.

    A handler another library installed on import would keep emitting records that never reach
    the redaction filter, which is worse than duplicate output.
    """
    root = logging.getLogger()
    original = list(root.handlers)
    original_level = root.level
    try:
        stray = logging.StreamHandler()
        root.addHandler(stray)

        install("WARNING")

        assert stray not in root.handlers
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, StructuredFormatter)
        assert any(isinstance(f, RedactionFilter) for f in root.handlers[0].filters)
        assert root.level == logging.WARNING
    finally:
        root.handlers = original
        root.setLevel(original_level)


def test_the_filter_sees_records_from_child_loggers() -> None:
    """Why the filter is on the handler and not on a logger.

    A logger-level filter sees only records logged directly to it, so a record from
    `trace_ai.services.ingestion` would bypass one attached to `trace_ai`.
    """
    import io

    root = logging.getLogger()
    original, original_level = list(root.handlers), root.level
    try:
        stream = io.StringIO()
        install("DEBUG")
        root.handlers[0].setStream(stream)  # type: ignore[attr-defined]

        logging.getLogger("trace_ai.services.ingestion.loader").warning(
            "loaded", extra={"quoted_text": SOURCE_PASSAGE}
        )

        assert SOURCE_PASSAGE not in stream.getvalue()
        assert "redacted source content" in stream.getvalue()
    finally:
        root.handlers = original
        root.setLevel(original_level)
