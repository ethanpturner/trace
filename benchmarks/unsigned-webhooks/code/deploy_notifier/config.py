"""Runtime settings, read from the environment once at import."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    chat_api_url: str
    chat_channel: str
    chat_token: str | None
    ci_signing_secret: str | None
    ledger_capacity: int


def load_settings() -> Settings:
    capacity = int(os.environ.get("DELIVERY_LEDGER_CAPACITY", "4096"))
    return Settings(
        chat_api_url=os.environ.get(
            "CHAT_API_URL", "https://chat.example.internal/api/v1/messages"
        ),
        chat_channel=os.environ.get("CHAT_CHANNEL", "#deploys"),
        chat_token=os.environ.get("CHAT_TOKEN") or None,
        ci_signing_secret=os.environ.get("CI_SIGNING_SECRET") or None,
        ledger_capacity=capacity,
    )
