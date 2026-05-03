import asyncio
import time

import pytest

from src.dedup import DedupCache


@pytest.mark.asyncio
async def test_health_endpoint_unblocked_during_bulk_insert(tmp_path):
    """A 100-item dedup batch must not block other coroutines for more than 100ms."""
    cache = DedupCache(db_path=str(tmp_path / "test.db"))

    async def fake_health():
        # Simulates the /health endpoint: must respond quickly even under load.
        return {"status": "ok"}

    async def bulk_insert():
        for i in range(100):
            await cache.insert(
                f"id-{i}", f"https://x.com/{i}", f"Title {i}", "src", "feed"
            )

    start = time.monotonic()
    bulk_task = asyncio.create_task(bulk_insert())
    health_results = []
    # Hit "health" 5 times during the bulk insert window
    for _ in range(5):
        await asyncio.sleep(0.05)
        health_start = time.monotonic()
        result = await fake_health()
        health_results.append(time.monotonic() - health_start)
        assert result == {"status": "ok"}
    await bulk_task
    total = time.monotonic() - start

    # Each health probe should complete in well under 100ms even while bulk_insert runs
    assert max(health_results) < 0.1, f"health probe took {max(health_results)}s under load"
    assert total < 5.0, f"bulk insert took {total}s"
