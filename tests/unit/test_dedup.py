import pytest
from datetime import datetime, timezone


SAMPLE_ARTICLE = {
    "id": "post_12345",
    "url": "https://example.substack.com/p/test-article",
    "title": "Test Article",
    "source": "Test Publication",
    "source_feed": "fyp",
}


class TestDedupInsert:
    """Test inserting articles into dedup cache."""

    def test_insert_new_article(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        result = cache.insert(
            article_id=SAMPLE_ARTICLE["id"],
            url=SAMPLE_ARTICLE["url"],
            title=SAMPLE_ARTICLE["title"],
            source=SAMPLE_ARTICLE["source"],
            source_feed=SAMPLE_ARTICLE["source_feed"],
        )
        assert result is True

    def test_insert_duplicate_returns_false(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert(
            article_id=SAMPLE_ARTICLE["id"],
            url=SAMPLE_ARTICLE["url"],
            title=SAMPLE_ARTICLE["title"],
            source=SAMPLE_ARTICLE["source"],
            source_feed=SAMPLE_ARTICLE["source_feed"],
        )
        result = cache.insert(
            article_id=SAMPLE_ARTICLE["id"],
            url=SAMPLE_ARTICLE["url"],
            title=SAMPLE_ARTICLE["title"],
            source=SAMPLE_ARTICLE["source"],
            source_feed=SAMPLE_ARTICLE["source_feed"],
        )
        assert result is False


class TestDedupLookup:
    """Test looking up articles in dedup cache."""

    def test_lookup_existing_returns_true(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert(
            article_id=SAMPLE_ARTICLE["id"],
            url=SAMPLE_ARTICLE["url"],
            title=SAMPLE_ARTICLE["title"],
            source=SAMPLE_ARTICLE["source"],
            source_feed=SAMPLE_ARTICLE["source_feed"],
        )
        assert cache.exists(SAMPLE_ARTICLE["id"]) is True

    def test_lookup_missing_returns_false(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        assert cache.exists("nonexistent_id") is False


class TestDedupListByFeed:
    """Test listing articles by source feed."""

    def test_list_by_source_feed(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert("id1", "url1", "title1", "source1", "fyp")
        cache.insert("id2", "url2", "title2", "source2", "subscription")
        cache.insert("id3", "url3", "title3", "source3", "fyp")

        fyp_articles = cache.list_by_feed("fyp")
        assert len(fyp_articles) == 2

    def test_list_empty_feed(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        assert cache.list_by_feed("fyp") == []


class TestDedupMigration:
    """Test schema migration."""

    def test_migration_creates_tables(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        # Check seen_articles table exists
        cursor = cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_articles'"
        )
        assert cursor.fetchone() is not None

    def test_migration_creates_schema_version_table(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cursor = cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        assert cursor.fetchone() is not None

    def test_migration_creates_indexes(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cursor = cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_seen_articles_first_seen" in indexes
        assert "idx_seen_articles_source" in indexes
        assert "idx_seen_articles_status" in indexes

    def test_migration_is_idempotent(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        # Run migration again — should not error
        cache._run_migrations()
        cursor = cache.conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1

    def test_schema_version_recorded(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cursor = cache.conn.execute(
            "SELECT version FROM schema_version"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1

    def test_article_has_first_seen_timestamp(self):
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert(
            article_id="ts_test",
            url="url",
            title="title",
            source="source",
            source_feed="fyp",
        )
        cursor = cache.conn.execute(
            "SELECT first_seen_at FROM seen_articles WHERE id = ?",
            ("ts_test",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is not None
