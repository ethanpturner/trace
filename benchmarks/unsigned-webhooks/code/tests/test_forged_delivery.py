"""The service runs, and a delivery nobody signed is accepted and posted."""

from __future__ import annotations

import json

import pytest
from deploy_notifier import main
from deploy_notifier.signing import SIGNATURE_HEADER, compute_signature
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    main.notifier.outbox.messages.clear()
    return TestClient(main.app)


def _event(delivery_id: str = "d-1") -> bytes:
    return json.dumps(
        {
            "delivery_id": delivery_id,
            "repository": "acme/checkout",
            "environment": "production",
            "commit": "0123456789abcdef",
            "status": "succeeded",
        }
    ).encode()


def test_service_is_alive(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_unsigned_delivery_is_accepted_and_posted(client: TestClient) -> None:
    response = client.post(
        "/events", content=_event(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 202
    assert response.json()["sent"] == "outbox"
    assert main.notifier.outbox.messages == [
        {"channel": "#deploys", "text": "acme/checkout deployed to production at 0123456789ab"}
    ]


def test_wrongly_signed_delivery_is_accepted_too(client: TestClient) -> None:
    forged = compute_signature("not-the-shared-secret", _event("d-2"))
    response = client.post(
        "/events",
        content=_event("d-2"),
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: forged},
    )
    assert response.status_code == 202
    assert len(main.notifier.outbox.messages) == 1


def test_repeated_delivery_identifier_is_not_reposted(client: TestClient) -> None:
    first = client.post("/events", content=_event("d-3"))
    second = client.post("/events", content=_event("d-3"))
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert len(main.notifier.outbox.messages) == 1


def test_malformed_body_is_rejected(client: TestClient) -> None:
    response = client.post("/events", content=b"not json")
    assert response.status_code == 400
