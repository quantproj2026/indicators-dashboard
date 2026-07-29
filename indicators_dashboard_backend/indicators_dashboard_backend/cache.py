"""An async TTL cache with single-flight, stale-while-error, and disk persistence.

The free Alpha Vantage tier allows 25 requests per day. Economic series are
revised monthly at best, so nearly every request the dashboard makes can and
should be answered from cache. This module provides:

* **TTL freshness** -- entries younger than ``ttl_seconds`` are served directly.
* **Single-flight** -- concurrent misses for the same key share one upstream call.
* **Stale-while-error** -- if the upstream fails or rate limits, an expired entry
  is served (flagged ``stale``) rather than surfacing an error to the user.
* **Disk persistence** -- entries survive a restart, so a dev server reload does
  not spend the daily quota again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Bumped when the on-disk entry format changes, to invalidate old cache files.
_DISK_FORMAT_VERSION = 1


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    """A stored value plus the wall-clock time it was produced."""

    value: T
    stored_at: float

    def age(self, *, now: float | None = None) -> float:
        return max(0.0, (now if now is not None else time.time()) - self.stored_at)


@dataclass(slots=True)
class CacheResult(Generic[T]):
    """What :meth:`TTLCache.get_or_fetch` produced, and where it came from."""

    value: T
    cached: bool
    stale: bool
    age_seconds: float
    stored_at: float


@dataclass(slots=True)
class CacheStats:
    hits: int = 0
    misses: int = 0
    stale_hits: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.stale_hits + self.misses
        return 0.0 if total == 0 else round((self.hits + self.stale_hits) / total, 4)


def make_key(*parts: object) -> str:
    """Build a stable cache key from ordered parts."""
    return "|".join(str(p) for p in parts)


class TTLCache:
    """Async-safe LRU + TTL cache keyed by string."""

    def __init__(
        self,
        *,
        ttl_seconds: int,
        max_entries: int = 512,
        stale_grace_seconds: int = 0,
        persist_dir: Path | None = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.stale_grace_seconds = stale_grace_seconds
        self.persist_dir = persist_dir
        self.stats = CacheStats()

        self._entries: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        # One lock per key so a miss on indicator A never blocks indicator B.
        self._key_locks: dict[str, asyncio.Lock] = {}

        if self.persist_dir is not None:
            self._load_from_disk()

    # -- introspection ------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entries)

    def snapshot_stats(self) -> dict[str, Any]:
        return {
            "entries": len(self._entries),
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "stale_hits": self.stats.stale_hits,
            "evictions": self.stats.evictions,
            "hit_rate": self.stats.hit_rate,
            "ttl_seconds": self.ttl_seconds,
            "stale_grace_seconds": self.stale_grace_seconds,
            "persisted": self.persist_dir is not None,
        }

    # -- core ---------------------------------------------------------------

    def peek(self, key: str) -> CacheEntry[Any] | None:
        """Return the raw entry without touching statistics or recency."""
        return self._entries.get(key)

    async def get_or_fetch(
        self,
        key: str,
        fetch: Callable[[], Awaitable[T]],
        *,
        serialize: Callable[[T], Any] | None = None,
        force_refresh: bool = False,
    ) -> CacheResult[T]:
        """Return a fresh value for ``key``, fetching only when necessary.

        Args:
            key: Cache key.
            fetch: Coroutine factory producing a fresh value on a miss.
            serialize: Converts the value to JSON-compatible data for disk
                persistence. Persistence is skipped when omitted.
            force_refresh: Bypass the freshness check and always call ``fetch``.
                A failure still falls back to a stale entry if one exists.

        Raises:
            Exception: whatever ``fetch`` raised, when no usable entry exists.
        """
        now = time.time()

        if not force_refresh:
            hit = await self._get_fresh(key, now=now)
            if hit is not None:
                return hit

        # Single-flight: only the first caller for this key performs the fetch.
        lock = await self._lock_for(key)
        async with lock:
            if not force_refresh:
                hit = await self._get_fresh(key)
                if hit is not None:
                    return hit
                # Counted here rather than in _get_fresh, which runs twice per
                # call (once before the lock, once after) on a cold key.
                async with self._lock:
                    self.stats.misses += 1

            try:
                value = await fetch()
            except Exception as exc:
                fallback = await self._get_stale(key)
                if fallback is not None:
                    logger.warning(
                        "Upstream fetch failed for %s (%s); serving cached copy aged %.0fs",
                        key,
                        type(exc).__name__,
                        fallback.age_seconds,
                    )
                    return fallback
                raise

            stored_at = await self.set(key, value, serialize=serialize)
            return CacheResult(
                value=value, cached=False, stale=False, age_seconds=0.0, stored_at=stored_at
            )

    async def set(
        self, key: str, value: T, *, serialize: Callable[[T], Any] | None = None
    ) -> float:
        """Store ``value`` under ``key`` and return its timestamp."""
        stored_at = time.time()
        async with self._lock:
            self._entries[key] = CacheEntry(value=value, stored_at=stored_at)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self.stats.evictions += 1

        if serialize is not None:
            self._write_to_disk(key, value, stored_at, serialize)
        return stored_at

    async def clear(self) -> int:
        """Drop every entry (in memory and on disk). Returns the count removed."""
        async with self._lock:
            removed = len(self._entries)
            self._entries.clear()
            self._key_locks.clear()
        if self.persist_dir is not None and self.persist_dir.exists():
            for path in self.persist_dir.glob("*.json"):
                path.unlink(missing_ok=True)
        return removed

    # -- internals ----------------------------------------------------------

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._lock:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._key_locks[key] = lock
            return lock

    async def _get_fresh(self, key: str, *, now: float | None = None) -> CacheResult[Any] | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            age = entry.age(now=now)
            if age > self.ttl_seconds:
                return None  # expired: the fetch may still fall back onto it
            self._entries.move_to_end(key)
            self.stats.hits += 1
            return CacheResult(
                value=entry.value,
                cached=True,
                stale=False,
                age_seconds=age,
                stored_at=entry.stored_at,
            )

    async def _get_stale(self, key: str) -> CacheResult[Any] | None:
        if self.stale_grace_seconds <= 0:
            return None
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            age = entry.age()
            if age > self.ttl_seconds + self.stale_grace_seconds:
                return None
            self.stats.stale_hits += 1
            return CacheResult(
                value=entry.value,
                cached=True,
                stale=True,
                age_seconds=age,
                stored_at=entry.stored_at,
            )

    # -- disk persistence ---------------------------------------------------

    def _path_for(self, key: str) -> Path:
        assert self.persist_dir is not None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.persist_dir / f"{digest}.json"

    def _write_to_disk(
        self, key: str, value: Any, stored_at: float, serialize: Callable[[Any], Any]
    ) -> None:
        if self.persist_dir is None:
            return
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": _DISK_FORMAT_VERSION,
                "key": key,
                "stored_at": stored_at,
                "value": serialize(value),
            }
            path = self._path_for(key)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(path)  # atomic: readers never see a half-written file
        except OSError as exc:
            logger.warning("Could not persist cache entry %s: %s", key, exc)

    def _load_from_disk(self) -> None:
        """Restore entries written by a previous process. Best effort."""
        assert self.persist_dir is not None
        if not self.persist_dir.exists():
            return
        horizon = self.ttl_seconds + self.stale_grace_seconds
        now = time.time()
        loaded = 0
        for path in sorted(self.persist_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                path.unlink(missing_ok=True)
                continue
            if payload.get("version") != _DISK_FORMAT_VERSION:
                path.unlink(missing_ok=True)
                continue
            stored_at = float(payload.get("stored_at", 0))
            if now - stored_at > horizon:
                path.unlink(missing_ok=True)
                continue
            self._entries[str(payload["key"])] = CacheEntry(
                value=payload["value"], stored_at=stored_at
            )
            loaded += 1
        if loaded:
            logger.info("Restored %d cache entries from %s", loaded, self.persist_dir)
