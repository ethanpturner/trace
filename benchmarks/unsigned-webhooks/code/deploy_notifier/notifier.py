"""Posting a formatted event to the chat platform."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from deploy_notifier.events import DeploymentEvent, format_message


@dataclass
class Outbox:
    """Where messages go when no chat token is configured, so the service runs in tests."""

    messages: list[dict[str, str]] = field(default_factory=list)


class ChatNotifier:
    """Formats a deployment event and posts it to the configured channel.

    With a token, the message is sent as JSON to the chat API with the token in an Authorization
    header. Without one, it is appended to the outbox. The token is held on the instance and is
    never written to a log or a response.
    """

    def __init__(
        self,
        api_url: str,
        channel: str,
        token: str | None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_url = api_url
        self._channel = channel
        self._token = token
        self._client = client or httpx.Client(timeout=5.0)
        self.outbox = Outbox()

    def post(self, event: DeploymentEvent) -> str:
        message = {"channel": self._channel, "text": format_message(event)}
        if self._token is None:
            self.outbox.messages.append(message)
            return "outbox"
        response = self._client.post(
            self._api_url,
            json=message,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        response.raise_for_status()
        return "posted"
