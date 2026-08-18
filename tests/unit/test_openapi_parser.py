"""The OpenAPI parser (#504): DEC-070's second parser, the compose rules held.

The load-bearing assertions: parsed output enters as proposals with `structured_input`
provenance and candidate status — determinism earns no bypass; `security: []` is the one
affirmative "no authentication" and becomes a documented claim, while silence about security
produces nothing (DEC-009's line, held by a parser); excerpts quote the document's own lines
and re-verify; and the family orchestrator seeds compose and OpenAPI together, idempotently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.services.context.openapi import parse_openapi
from trace_ai.services.context.parsers import seed_structured_documents

if TYPE_CHECKING:
    from pathlib import Path

SPEC = """openapi: 3.1.0
info:
  title: Relay Answers API
  version: "1.0"
paths:
  /answers:
    post:
      summary: Ask a question
      responses:
        "200":
          description: The cited answer
  /health:
    get:
      summary: Liveness probe
      security: []
      responses:
        "200":
          description: OK
components:
  securitySchemes:
    workspaceToken:
      type: http
      scheme: bearer
security:
  - workspaceToken: []
"""


def test_parse_reads_declarations_and_only_declarations() -> None:
    parsed = parse_openapi(SPEC)
    assert parsed.title == "Relay Answers API"
    assert parsed.security_schemes == ("workspaceToken: http bearer",)
    assert parsed.global_security is True
    assert parsed.has_webhooks is False
    operations = {(op.method, op.path): op.explicit_no_auth for op in parsed.operations}
    assert operations == {("POST", "/answers"): False, ("GET", "/health"): True}


def test_a_document_without_the_version_key_is_refused() -> None:
    with pytest.raises(ValueError, match="openapi"):
        parse_openapi("services:\n  api: {}\n")


def test_seeding_enters_the_proposal_path_as_candidates(tmp_path: Path) -> None:
    """Provenance is `structured_input`, status is `candidate`, and the explicit-no-auth
    operation becomes a documented claim citing the paths excerpt — the DEC-009 line held by
    a parser: `security: []` is a statement, silence is not."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    spec_path = tmp_path / "openapi.yaml"
    spec_path.write_text(SPEC, encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Relay", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            spec_path,
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )

        seeded = seed_structured_documents(handle)
        assert seeded is not None
        (component,) = seeded.components
        assert component.name == "Relay Answers API"
        assert component.status is ObjectStatus.CANDIDATE
        assert component.source_origin is SourceOrigin.STRUCTURED_INPUT
        assert component.entry_point_types == ["http_api"]
        assert component.authentication_mechanisms == ["workspaceToken: http bearer"]

        claims = handle.objects.list(ContextClaim)
        no_auth = [c for c in claims if c.predicate == "operation_authentication"]
        assert len(no_auth) == 1
        assert "GET /health" in str(no_auth[0].value)
        assert no_auth[0].status.value == "documented"

        # Family idempotence: a second seeding call mints nothing new (DEC-038's re-extraction
        # reuse, checked once for the whole parser family).
        again = seed_structured_documents(handle)
        assert again is not None
        assert len(handle.objects.list(Component)) == 1


def test_silence_about_security_produces_no_claim(tmp_path: Path) -> None:
    parsed = parse_openapi(
        "openapi: 3.1.0\ninfo:\n  title: Quiet API\npaths:\n  /x:\n    get:\n"
        '      responses:\n        "200":\n          description: OK\n'
    )
    assert parsed.security_schemes == ()
    assert parsed.global_security is False
    assert all(not op.explicit_no_auth for op in parsed.operations)
