"""The per-workspace daily answer quota and the per-workspace feature flag."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime

from fastapi import HTTPException, status


class DailyQuota:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._day: date = datetime.now(UTC).date()
        self._used: defaultdict[str, int] = defaultdict(int)
        self._disabled: set[str] = set()

    def disable(self, workspace_id: str) -> None:
        self._disabled.add(workspace_id)

    def enable(self, workspace_id: str) -> None:
        self._disabled.discard(workspace_id)

    def charge(self, workspace_id: str, now: datetime | None = None) -> None:
        """Count one answer against the workspace; 403 when disabled, 429 when the day's quota is
        spent."""
        today = (now or datetime.now(UTC)).date()
        if today != self._day:
            self._day = today
            self._used.clear()
        if workspace_id in self._disabled:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "assistant disabled for workspace")
        if self._used[workspace_id] >= self._limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily answer quota reached")
        self._used[workspace_id] += 1
