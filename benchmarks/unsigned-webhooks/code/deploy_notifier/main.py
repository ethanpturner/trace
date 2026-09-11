"""The event receiver: a public endpoint the CI platform calls with deployment events."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Request, Response, status
from pydantic import ValidationError

from deploy_notifier.config import load_settings
from deploy_notifier.events import DeploymentEvent
from deploy_notifier.notifier import ChatNotifier
from deploy_notifier.replay import DeliveryLedger

log = logging.getLogger("deploy_notifier")

settings = load_settings()
notifier = ChatNotifier(settings.chat_api_url, settings.chat_channel, settings.chat_token)
ledger = DeliveryLedger(settings.ledger_capacity)

app = FastAPI(title="Deploy Notifier", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def receive_event(request: Request, response: Response) -> dict[str, object]:
    """Accept a deployment event from the CI platform and post it to the chat channel.

    The body is parsed as JSON and validated against the event shape. A delivery identifier the
    ledger has already seen is acknowledged without posting again.
    """
    body = await request.body()
    try:
        event = DeploymentEvent.model_validate(json.loads(body))
    except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"accepted": False, "error": type(exc).__name__}

    if not ledger.record(event.delivery_id):
        log.info("duplicate delivery", extra={"delivery_id": event.delivery_id})
        return {"accepted": True, "duplicate": True, "delivery_id": event.delivery_id}

    outcome = notifier.post(event)
    log.info(
        "deployment event handled",
        extra={"delivery_id": event.delivery_id, "repository": event.repository},
    )
    return {
        "accepted": True,
        "duplicate": False,
        "delivery_id": event.delivery_id,
        "sent": outcome,
    }
