import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_FYP_RESPONSE = {
    "items": [
        {
            "entity_key": "p-1001",
            "type": "post",
            "post": {
                "id": 1001,
                "title": "AI Agents Are the Future",
                "slug": "ai-agents-future",
                "post_date": "2026-03-06T10:00:00Z",
                "publishedBylines": [{"name": "Test Author"}],
                "publication": {"name": "Tech Blog", "subdomain": "techblog"},
                "canonical_url": "https://techblog.substack.com/p/ai-agents-future",
                "body_html": "<p>Article content here</p>",
            },
            "comment": None,
            "context": {"type": "post", "typeBucket": "posts"},
        },
        {
            "entity_key": "p-1002",
            "type": "post",
            "post": {
                "id": 1002,
                "title": "Creator Economy 2026",
                "slug": "creator-economy-2026",
                "post_date": "2026-03-05T08:00:00Z",
                "publishedBylines": [{"name": "Another Author"}],
                "publication": {"name": "Creator Weekly", "subdomain": "creatorweekly"},
                "canonical_url": "https://creatorweekly.substack.com/p/creator-economy-2026",
                "body_html": "<p>More content</p>",
            },
            "comment": None,
            "context": {"type": "post", "typeBucket": "posts"},
        },
        {
            "entity_key": "c-9999",
            "type": "comment",
            "post": None,
            "comment": {"id": 9999, "body": "A note in the feed"},
            "context": {"type": "note", "typeBucket": "notes"},
        },
    ],
}

MOCK_FYP_PAGE2 = {
    "items": [
        {
            "entity_key": "p-1003",
            "type": "post",
            "post": {
                "id": 1003,
                "title": "Page 2 Article",
                "slug": "page-2-article",
                "post_date": "2026-03-04T06:00:00Z",
                "publishedBylines": [{"name": "Page2 Author"}],
                "publication": {"name": "Page2 Pub", "subdomain": "page2pub"},
                "canonical_url": "https://page2pub.substack.com/p/page-2-article",
                "body_html": "<p>Page 2 content</p>",
            },
            "comment": None,
            "context": {"type": "post", "typeBucket": "posts"},
        },
    ],
}

class TestFYPFeedBasic:
    """Test FYP feed returns articles with dedup applied."""

    @pytest.mark.asyncio
    async def test_returns_articles(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_article_has_required_fields(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        article = result[0]
        assert "id" in article
        assert "title" in article
        assert "author" in article
        assert "publication" in article
        assert "url" in article
        assert "published_at" in article
        assert "platform" in article
        assert "is_new" in article
        assert "source_feed" in article
        assert article["source_feed"] == "fyp"
        assert article["platform"] == "substack"


class TestFYPFeedDedup:
    """Test dedup behavior — skips seen, inserts new."""

    @pytest.mark.asyncio
    async def test_skips_seen_articles(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        # Pre-insert first article as seen
        await cache.insert("substack_post_1001", "url", "title", "source", "fyp")

        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        assert len(result) == 1
        assert result[0]["id"] == "substack_post_1002"

    @pytest.mark.asyncio
    async def test_inserts_new_articles_into_cache(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            await get_fyp_feed()

        assert await cache.exists("substack_post_1001")
        assert await cache.exists("substack_post_1002")


class TestFYPFeedSinceFilter:
    """Test since param filters by date."""

    @pytest.mark.asyncio
    async def test_since_filters_old_articles(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            # Only articles after March 6 — should filter out the March 5 article
            result = await get_fyp_feed(since="2026-03-06T00:00:00Z")

        assert len(result) == 1
        assert result[0]["title"] == "AI Agents Are the Future"


class TestFYPFeedContent:
    """Test articles always include full content."""

    @pytest.mark.asyncio
    async def test_returns_full_content(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        article = result[0]
        assert "content" in article
        assert "summary" not in article


class TestFYPFeedHintAndContent:
    """Test hint field and full content (no truncation)."""

    @pytest.mark.asyncio
    async def test_hint_field_present(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        for article in result:
            assert "hint" in article
            assert "ss_get_post_content" in article["hint"]

    @pytest.mark.asyncio
    async def test_content_not_truncated(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        long_html = "<p>" + "x" * 5000 + "</p>"
        long_response = {
            "items": [{
                "entity_key": "p-9001",
                "type": "post",
                "post": {
                    "id": 9001,
                    "title": "Long Article",
                    "slug": "long-article",
                    "post_date": "2026-03-06T10:00:00Z",
                    "publishedBylines": [{"name": "Author"}],
                    "publication": {"name": "Pub", "subdomain": "pub"},
                    "canonical_url": "https://pub.substack.com/p/long-article",
                    "body_html": long_html,
                },
                "comment": None,
                "context": {"type": "post"},
            }],
        }

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=long_response,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        assert len(result[0]["content"]) > 2000


class TestFYPFeedEmpty:
    """Test empty feed returns empty array."""

    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty_list(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json={"items": []},
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        assert result == []


class TestFYPFeedAuth:
    """Test auth error handling."""

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.fyp_feed import get_fyp_feed

        with patch("src.tools.fyp_feed.get_client", return_value=None):
            result = await get_fyp_feed()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_401_returns_auth_expired(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
