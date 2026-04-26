from __future__ import annotations

import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Simple in-memory TTL cache for async results."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._data: T | None = None
        self._expires_at: float = 0.0

    def get(self) -> T | None:
        if self._data is not None and time.monotonic() < self._expires_at:
            return self._data
        return None

    def set(self, value: T) -> None:
        self._data = value
        self._expires_at = time.monotonic() + self._ttl

    def invalidate(self) -> None:
        self._data = None
        self._expires_at = 0.0


tariff_cache: TTLCache[list[dict[str, Any]]] = TTLCache(ttl_seconds=300)
