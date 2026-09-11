"""Runtime settings, read from the environment once at import."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

_DEV_TOKENS = {
    "dev-token-acme": "ws-acme",
    "dev-token-globex": "ws-globex",
}


@dataclass(frozen=True)
class Settings:
    provider_url: str
    provider_key: str | None
    daily_answer_quota: int
    top_k: int
    workspace_tokens: dict[str, str] = field(default_factory=dict)


def load_settings() -> Settings:
    raw_tokens = os.environ.get("WORKSPACE_TOKENS")
    tokens: dict[str, str] = json.loads(raw_tokens) if raw_tokens else dict(_DEV_TOKENS)
    return Settings(
        provider_url=os.environ.get("PROVIDER_URL", "https://models.example.com/v1/complete"),
        provider_key=os.environ.get("PROVIDER_KEY") or None,
        daily_answer_quota=int(os.environ.get("DAILY_ANSWER_QUOTA", "200")),
        top_k=int(os.environ.get("RETRIEVAL_TOP_K", "8")),
        workspace_tokens=tokens,
    )
