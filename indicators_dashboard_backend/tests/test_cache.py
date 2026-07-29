"""Cache behaviour: TTL, LRU, single-flight, stale-while-error, persistence."""

from __future__ import annotations

import asyncio
import time

import pytest

from indicators_dashboard_backend.cache import TTLCache, make_key


@pytest.fixture
def cache(tmp_path) -> TTLCache:
    return TTLCache(ttl_seconds=60, max_entries=4, stale_grace_seconds=600)


async def test_first_call_fetches_and_second_call_hits(cache: TTLCache):
    calls = 0

    async def fetch() -> str:
        nonlocal calls
        calls += 1
        return "value"

    first = await cache.get_or_fetch("k", fetch)
    second = await cache.get_or_fetch("k", fetch)

    assert calls == 1
    assert (first.cached, first.stale) == (False, False)
    assert (second.cached, second.stale) == (True, False)
    assert second.value == "value"


async def test_expired_entry_triggers_a_refetch(cache: TTLCache):
    calls = 0

    async def fetch() -> int:
        nonlocal calls
        calls += 1
        return calls

    await cache.get_or_fetch("k", fetch)
    # Rewind the stored timestamp instead of sleeping.
    cache.peek("k").stored_at = time.time() - 3600

    result = await cache.get_or_fetch("k", fetch)
    assert calls == 2
    assert result.value == 2
    assert result.cached is False


async def test_force_refresh_bypasses_a_fresh_entry(cache: TTLCache):
    calls = 0

    async def fetch() -> int:
        nonlocal calls
        calls += 1
        return calls

    await cache.get_or_fetch("k", fetch)
    result = await cache.get_or_fetch("k", fetch, force_refresh=True)
    assert calls == 2
    assert result.value == 2


async def test_concurrent_misses_share_one_fetch(cache: TTLCache):
    """Ten simultaneous requests for one key must cost one upstream call."""
    calls = 0

    async def fetch() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return "shared"

    results = await asyncio.gather(*(cache.get_or_fetch("k", fetch) for _ in range(10)))

    assert calls == 1
    assert all(r.value == "shared" for r in results)


async def test_distinct_keys_do_not_block_each_other(cache: TTLCache):
    order: list[str] = []

    async def slow() -> str:
        await asyncio.sleep(0.05)
        order.append("slow")
        return "slow"

    async def quick() -> str:
        order.append("quick")
        return "quick"

    await asyncio.gather(cache.get_or_fetch("a", slow), cache.get_or_fetch("b", quick))
    assert order == ["quick", "slow"]


async def test_expired_entry_is_served_when_the_fetch_fails(cache: TTLCache):
    async def ok() -> str:
        return "good"

    async def boom() -> str:
        raise RuntimeError("upstream down")

    await cache.get_or_fetch("k", ok)
    cache.peek("k").stored_at = time.time() - 300  # past the 60s TTL

    result = await cache.get_or_fetch("k", boom)

    assert result.value == "good"
    assert result.stale is True
    assert result.cached is True
    assert result.age_seconds >= 300
    assert cache.stats.stale_hits == 1


async def test_failure_propagates_when_nothing_is_cached(cache: TTLCache):
    async def boom() -> str:
        raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError, match="upstream down"):
        await cache.get_or_fetch("cold", boom)


async def test_entry_beyond_the_stale_grace_is_not_served():
    cache = TTLCache(ttl_seconds=10, stale_grace_seconds=30)

    async def ok() -> str:
        return "old"

    async def boom() -> str:
        raise RuntimeError("nope")

    await cache.get_or_fetch("k", ok)
    cache.peek("k").stored_at = time.time() - 1000

    with pytest.raises(RuntimeError):
        await cache.get_or_fetch("k", boom)


async def test_stale_serving_can_be_disabled():
    cache = TTLCache(ttl_seconds=10, stale_grace_seconds=0)

    async def ok() -> str:
        return "old"

    async def boom() -> str:
        raise RuntimeError("nope")

    await cache.get_or_fetch("k", ok)
    cache.peek("k").stored_at = time.time() - 100

    with pytest.raises(RuntimeError):
        await cache.get_or_fetch("k", boom)


async def test_lru_eviction_respects_max_entries(cache: TTLCache):
    async def fetch() -> str:
        return "v"

    for index in range(6):
        await cache.get_or_fetch(f"k{index}", fetch)

    assert len(cache) == 4
    assert cache.peek("k0") is None
    assert cache.peek("k5") is not None
    assert cache.stats.evictions == 2


async def test_clear_removes_everything(cache: TTLCache):
    async def fetch() -> str:
        return "v"

    await cache.get_or_fetch("k", fetch)
    removed = await cache.clear()
    assert removed == 1
    assert len(cache) == 0


async def test_entries_survive_a_restart_via_disk(tmp_path):
    """A reload must not spend the daily quota re-fetching what it already had."""
    calls = 0

    async def fetch() -> dict:
        nonlocal calls
        calls += 1
        return {"data": [{"date": "2026-01-01", "value": "1.0"}]}

    first = TTLCache(ttl_seconds=600, persist_dir=tmp_path / "cache")
    await first.get_or_fetch("k", fetch, serialize=lambda v: v)
    assert calls == 1
    assert list((tmp_path / "cache").glob("*.json"))

    reborn = TTLCache(ttl_seconds=600, persist_dir=tmp_path / "cache")
    result = await reborn.get_or_fetch("k", fetch, serialize=lambda v: v)

    assert calls == 1, "restored entry should have prevented a second fetch"
    assert result.cached is True
    assert result.value == {"data": [{"date": "2026-01-01", "value": "1.0"}]}


async def test_disk_entries_past_their_horizon_are_discarded(tmp_path):
    async def fetch() -> dict:
        return {"v": 1}

    first = TTLCache(ttl_seconds=10, stale_grace_seconds=10, persist_dir=tmp_path / "c")
    await first.get_or_fetch("k", fetch, serialize=lambda v: v)

    # Age the file well past ttl + grace.
    entry_file = next((tmp_path / "c").glob("*.json"))
    import json

    payload = json.loads(entry_file.read_text())
    payload["stored_at"] = time.time() - 10_000
    entry_file.write_text(json.dumps(payload))

    reborn = TTLCache(ttl_seconds=10, stale_grace_seconds=10, persist_dir=tmp_path / "c")
    assert len(reborn) == 0


async def test_corrupt_disk_entries_are_ignored(tmp_path):
    cache_dir = tmp_path / "c"
    cache_dir.mkdir()
    (cache_dir / "garbage.json").write_text("{not json")

    cache = TTLCache(ttl_seconds=60, persist_dir=cache_dir)

    assert len(cache) == 0
    assert not (cache_dir / "garbage.json").exists()


async def test_stats_snapshot_reports_hit_rate(cache: TTLCache):
    async def fetch() -> str:
        return "v"

    await cache.get_or_fetch("k", fetch)  # miss
    await cache.get_or_fetch("k", fetch)  # hit
    stats = cache.snapshot_stats()

    assert stats["entries"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5


def test_make_key_is_order_sensitive_and_stable():
    assert make_key("a", 1) == make_key("a", 1)
    assert make_key("a", 1) != make_key(1, "a")
