"""The service runs, and one workspace's ticket content reaches another workspace's answer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from relay_answers import main
from relay_answers.embeddings import embed
from relay_answers.index import RetrievalIndex
from relay_answers.ingestion import HelpArticle, ResolvedTicket, run_nightly

RESOLVED = datetime(2026, 1, 15, tzinfo=UTC)


@pytest.fixture
def client() -> TestClient:
    main.index = RetrievalIndex()
    run_nightly(
        main.index,
        [HelpArticle("webhooks", "Configuring webhooks", "Webhooks post JSON to your endpoint.")],
        [
            ResolvedTicket(
                "t-100",
                "ws-acme",
                "Our webhook failed. Config: ACME_WEBHOOK_SECRET=hunter2 endpoint=hooks.acme.test "
                "contact ops@acme.test",
                RESOLVED,
            ),
            ResolvedTicket(
                "t-200", "ws-globex", "Billing page shows the wrong currency.", RESOLVED
            ),
        ],
        now=RESOLVED,
    )
    return TestClient(main.app)


def test_service_is_alive(client: TestClient) -> None:
    assert client.get("/v1/health").json() == {"status": "ok"}


def test_answers_require_a_workspace_token(client: TestClient) -> None:
    assert client.post("/v1/answers", json={"question": "hi"}).status_code == 401


def test_another_workspaces_ticket_reaches_the_answer(client: TestClient) -> None:
    response = client.post(
        "/v1/answers",
        json={"question": "webhook failed ACME_WEBHOOK_SECRET endpoint config"},
        headers={"Authorization": "Bearer dev-token-globex"},
    )
    assert response.status_code == 200
    cited = {citation["source_ref"] for citation in response.json()["citations"]}
    assert "tickets/t-100" in cited


def test_email_addresses_are_masked_in_the_index(client: TestClient) -> None:
    texts = " ".join(hit.chunk.text for hit in main.index.search(embed("contact"), k=8))
    assert "ops@acme.test" not in texts
    assert "[email]" in texts


def test_a_tombstoned_ticket_leaves_the_index(client: TestClient) -> None:
    run_nightly(
        main.index,
        [],
        [ResolvedTicket("t-100", "ws-acme", "", RESOLVED, deleted_at=RESOLVED)],
        now=RESOLVED,
    )
    assert "tickets/t-100" not in main.index.source_refs()
