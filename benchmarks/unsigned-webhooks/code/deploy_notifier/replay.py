"""A bounded record of delivery identifiers already handled by this process."""

from __future__ import annotations

from collections import OrderedDict


class DeliveryLedger:
    """Remembers the most recent `capacity` delivery identifiers.

    `record` returns True the first time an identifier is seen and False on a repeat. When the
    ledger is full the oldest identifier is forgotten. The ledger lives in process memory.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("ledger capacity must be positive")
        self._capacity = capacity
        self._seen: OrderedDict[str, None] = OrderedDict()

    def record(self, delivery_id: str) -> bool:
        if delivery_id in self._seen:
            self._seen.move_to_end(delivery_id)
            return False
        self._seen[delivery_id] = None
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
        return True

    def __len__(self) -> int:
        return len(self._seen)
