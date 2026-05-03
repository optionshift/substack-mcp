import threading


class TestDedupConcurrentAccess:
    """Test dedup cache handles concurrent access from multiple threads.

    These tests exercise the underlying sync sqlite path (which the async
    wrappers delegate to via asyncio.to_thread), so we call the _sync
    methods directly here.
    """

    def test_concurrent_inserts_no_duplicates(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        results = []

        def insert_article(article_id):
            result = cache._insert_sync(
                article_id, f"url_{article_id}", f"title_{article_id}", "source", "fyp"
            )
            results.append((article_id, result))

        threads = []
        for i in range(10):
            t = threading.Thread(target=insert_article, args=(f"article_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All should succeed since they have different IDs
        assert len(results) == 10
        assert all(r[1] is True for r in results)

    def test_concurrent_duplicate_inserts(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        results = []

        def insert_same_article():
            result = cache._insert_sync("same_id", "url", "title", "source", "fyp")
            results.append(result)

        threads = []
        for _ in range(5):
            t = threading.Thread(target=insert_same_article)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Exactly one should succeed
        assert results.count(True) == 1
        assert results.count(False) == 4


class TestDedupPersistence:
    """Test dedup cache data persistence within a session."""

    async def test_data_persists_across_operations(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        await cache.insert("persist_1", "url1", "title1", "source1", "fyp")
        await cache.insert("persist_2", "url2", "title2", "source2", "subscription")

        assert await cache.exists("persist_1") is True
        assert await cache.exists("persist_2") is True
        assert await cache.exists("persist_3") is False

        articles = await cache.list_by_feed("fyp")
        assert len(articles) == 1
        assert articles[0]["id"] == "persist_1"
