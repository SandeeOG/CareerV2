"""The knowledge cache: expensive generations are cached, never re-derived.

Career summaries, regional analyses, salary lookups and comparisons are cached
under namespaced keys with a configurable TTL. The cache is clock-injected so
expiry is testable, and it is the *only* place Layer 2 (dynamic) knowledge
lives — expiry is what forces a refresh instead of the platform ever treating
volatile facts as permanent truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar

from ...application.ports import Clock

T = TypeVar("T")


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CacheEntry:
    value: object
    stored_at: datetime
    ttl_seconds: int

    def expires_at(self) -> datetime:
        return self.stored_at + timedelta(seconds=self.ttl_seconds)


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    entries: int


class KnowledgeCache:
    """A TTL cache with namespaced keys (``"regional:data-scientist:assam"``)."""

    def __init__(self, clock: Clock | None = None, default_ttl_seconds: int = 3600) -> None:
        if default_ttl_seconds <= 0:
            raise ValueError("default_ttl_seconds must be positive")
        self._clock = clock or _SystemClock()
        self._default_ttl = default_ttl_seconds
        self._entries: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def key(namespace: str, *parts: str) -> str:
        return ":".join((namespace, *parts))

    def get(self, key: str) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        if self._clock.now() >= entry.expires_at():
            del self._entries[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def put(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._entries[key] = CacheEntry(value, self._clock.now(), ttl)

    def get_or_compute(
        self, key: str, factory: Callable[[], T], ttl_seconds: int | None = None
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        value = factory()
        if value is not None:
            self.put(key, value, ttl_seconds)
        return value

    def invalidate(self, prefix: str = "") -> int:
        """Drop entries whose key starts with ``prefix`` (all when empty)."""
        doomed = [k for k in self._entries if k.startswith(prefix)]
        for k in doomed:
            del self._entries[k]
        return len(doomed)

    def stats(self) -> CacheStats:
        return CacheStats(self._hits, self._misses, len(self._entries))
