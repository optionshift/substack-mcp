import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_FYP_RESPONSE = {
    "posts": [
        {
            "id": 1001,
            "title": "AI Agents Are the Future",
            "slug": "ai-agents-future",
            "post_date": "2026-03-06T10:00:00Z",
            "publishedBylines": [{"name": "Test Author"}],
            "publication": {"name": "Tech Blog", "subdomain": "techblog"},
            "canonical_url": "https://techblog.substack.com/p/ai-agents-future",
            "body_html": "<p>Article content here</p>",
        },
        {
            "id": 1002,
            "title": "Creator Economy 2026",
            "slug": "creator-economy-2026",
            "post_date": "2026-03-05T08:00:00Z",
            "publishedBylines": [{"name": "Another Author"}],
            "publication": {"name": "Creator Weekly", "subdomain": "creatorweekly"},
            "canonical_url": "https://creatorweekly.substack.com/p/creator-economy-2026",
            "body_html": "<p>More content</p>",
        },
    ],
}

MOCK_FYP_PAGE2 = {
    "posts": [
        {
            "id": 1003,
            "title": "Page 2 Article",
            "slug": "page-2-article",
            "post_date": "2026-03-04T06:00:00Z",
            "publishedBylines": [{"name": "Page2 Author"}],
            "publication": {"name": "Page2 Pub", "subdomain": "page2pub"},
            "canonical_url": "https://page2pub.substack.com/p/page-2-article",
            "body_html": "<p>Page 2 content</p>",
        },
    ],
}

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "tags": ["AI-agents"],
    "relevance": 8,
    "key_quote": "A quote.",
    "angle": "An angle",
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
             patch("src.tools.fyp_feed.get_cache", return_value=cache), \
             patch("src.tools.fyp_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
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
             patch("src.tools.fyp_feed.get_cache", return_value=cache), \
             patch("src.tools.fyp_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
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
        cache.insert("substack_post_1001", "url", "title", "source", "fyp")

        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache), \
             patch("src.tools.fyp_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
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
             patch("src.tools.fyp_feed.get_cache", return_value=cache), \
             patch("src.tools.fyp_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            await get_fyp_feed()

        assert cache.exists("substack_post_1001")
        assert cache.exists("substack_post_1002")


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
             patch("src.tools.fyp_feed.get_cache", return_value=cache), \
             patch("src.tools.fyp_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            # Only articles after March 6 — should filter out the March 5 article
            result = await get_fyp_feed(since="2026-03-06T00:00:00Z")

        assert len(result) == 1
        assert result[0]["title"] == "AI Agents Are the Future"


class TestFYPFeedSummarize:
    """Test summarize param controls output."""

    @pytest.mark.asyncio
    async def test_summarize_true_returns_summary_fields(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_FYP_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed"),
        )

        with patch("src.tools.fyp_feed.get_client") as mock_get_client, \
             patch("src.tools.fyp_feed.get_cache", return_value=cache), \
             patch("src.tools.fyp_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_fyp_feed(summarize=True)

        article = result[0]
        assert "summary" in article
        assert "tags" in article
        assert "relevance" in article
        assert "key_quote" in article
        assert "angle" in article

    @pytest.mark.asyncio
    async def test_summarize_false_returns_raw_content(self):
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

            result = await get_fyp_feed(summarize=False)

        article = result[0]
        assert "raw_content" in article
        assert "summary" not in article


class TestFYPFeedEmpty:
    """Test empty feed returns empty array."""

    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty_list(self):
        from src.tools.fyp_feed import get_fyp_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json={"posts": []},
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
