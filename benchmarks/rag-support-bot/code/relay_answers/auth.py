"""Resolving the caller's workspace from the session token."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from collections.abc import Mapping


def workspace_for(authorization: str | None, tokens: Mapping[str, str]) -> str:
    """The workspace a bearer token is scoped to.

    Tokens are opaque: they are looked up, never parsed. A missing, malformed, or unknown token is
    a 401.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "workspace token required")
    token = authorization.removeprefix("Bearer ").strip()
    workspace = tokens.get(token)
    if workspace is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "workspace token not recognised")
    return workspace
