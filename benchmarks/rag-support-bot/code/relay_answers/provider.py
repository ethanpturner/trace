"""The hosted model provider, and what leaves for it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from relay_answers.prompt import Passage

_IDENTIFIER_FIELDS = ("workspace_id", "user_id", "session_id")


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    max_tokens: int = 512


def strip_identifiers(request: dict[str, object]) -> dict[str, object]:
    """The request without workspace, user, or session identifiers. Applied to every outbound
    request so nothing that names the caller reaches the provider."""
    return {key: value for key, value in request.items() if key not in _IDENTIFIER_FIELDS}


class ModelProvider:
    """One completion call per answer. Without a key, answers come from a stub that names the
    passages it was given, so the service runs in tests."""

    def __init__(self, url: str, key: str | None, client: httpx.Client | None = None) -> None:
        self._url = url
        self._key = key
        self._client = client or httpx.Client(timeout=30.0)

    def answer(self, request: ProviderRequest, passages: list[Passage]) -> str:
        outbound = strip_identifiers({"prompt": request.prompt, "max_tokens": request.max_tokens})
        if self._key is None:
            cited = ", ".join(passage.reference for passage in passages) or "no passages"
            return f"[stub answer] Based on {cited}."
        response = self._client.post(
            self._url, json=outbound, headers={"Authorization": f"Bearer {self._key}"}
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("text", ""))
