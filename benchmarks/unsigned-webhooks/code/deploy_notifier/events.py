"""The deployment event the CI platform delivers, and the message it becomes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeploymentEvent(BaseModel):
    """One deployment event as delivered. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    delivery_id: str = Field(min_length=1, max_length=128)
    repository: str = Field(min_length=1, max_length=256)
    environment: str = Field(min_length=1, max_length=64)
    commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    status: Literal["started", "succeeded", "failed"] = "succeeded"


_STATUS_WORDS = {
    "started": "is deploying to",
    "succeeded": "deployed to",
    "failed": "failed to deploy to",
}


def format_message(event: DeploymentEvent) -> str:
    """The chat message naming the repository, environment, and commit.

    Plain text in one JSON field of the chat API request; nothing downstream interprets it as
    markup or a template.
    """
    verb = _STATUS_WORDS[event.status]
    return f"{event.repository} {verb} {event.environment} at {event.commit[:12]}"
