from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> Any:
        expires_at = time.time() + max(ttl_seconds, 1)
        with self._lock:
            self._data[key] = CacheEntry(value=value, expires_at=expires_at)
        return value

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [item for item in self._data if item.startswith(prefix)]:
                self._data.pop(key, None)
