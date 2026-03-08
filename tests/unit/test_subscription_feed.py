import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_SUB_RESPONSE = {
    "items": [
        {
            "entity_key": "p-2001",
            "type": "post",
            "post": {
                "id": 2001,
                "title": "Subscription Article 1",
                "slug": "sub-article-1",
                "post_date": "2026-03-06T10:00:00Z",
                "publishedBylines": [{"name": "Sub Author"}],
                "publication": {"name": "Sub Pub", "subdomain": "subpub"},
                "canonical_url": "https://subpub.substack.com/p/sub-article-1",
                "body_html": "<p>Subscription content</p>",
            },
            "comment": None,
            "context": {"type": "post", "typeBucket": "posts"},
        },
        {
            "entity_key": "p-2002",
            "type": "post",
            "post": {
                "id": 2002,
                "title": "Subscription Article 2",
                "slug": "sub-article-2",
                "post_date": "2026-03-05T08:00:00Z",
                "publishedBylines": [{"name": "Sub Author 2"}],
                "publication": {"name": "Sub Pub 2", "subdomain": "subpub2"},
                "canonical_url": "https://subpub2.substack.com/p/sub-article-2",
                "body_html": "<p>More subscription content</p>",
            },
            "comment": None,
            "context": {"type": "post", "typeBucket": "posts"},
        },
    ],
}

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "tags": ["creator-economy"],
    "relevance": 7,
    "key_quote": "A quote.",
    "angle": "An angle",
}

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Pub</title>
    <item>
      <title>RSS Article</title>
      <link>https://testpub.substack.com/p/rss-article</link>
      <guid>https://testpub.substack.com/p/rss-article</guid>
      <pubDate>Thu, 06 Mar 2026 10:00:00 GMT</pubDate>
      <description><![CDATA[<p>RSS content here</p>]]></description>
    </item>
  </channel>
</rss>"""

MOCK_SUBSCRIPTIONS = [
    {"name": "Test Pub", "subdomain": "testpub", "rss_url": "https://testpub.substack.com/feed"},
    {"name": "Test Pub 2", "subdomain": "testpub2", "rss_url": "https://testpub2.substack.com/feed"},
]


class TestSubscriptionFeedPrimary:
    """Test primary API returns articles."""

    @pytest.mark.asyncio
    async def test_returns_articles(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SUB_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache), \
             patch("src.tools.subscription_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_article_has_source_feed_subscription(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SUB_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache), \
             patch("src.tools.subscription_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed()

        assert result[0]["source_feed"] == "subscription"


class TestSubscriptionFeedRSSFallback:
    """Test primary API failure triggers RSS fallback."""

    @pytest.mark.asyncio
    async def test_api_failure_triggers_rss_fallback(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        # Primary API returns 500
        mock_api_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )
        # RSS returns valid XML
        mock_rss_response = httpx.Response(
            200,
            text=MOCK_RSS_XML,
            request=httpx.Request("GET", "https://testpub.substack.com/feed"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache), \
             patch("src.tools.subscription_feed.get_subscriptions_list", new_callable=AsyncMock, return_value=MOCK_SUBSCRIPTIONS), \
             patch("src.tools.subscription_feed.fetch_rss", new_callable=AsyncMock, return_value=mock_rss_response), \
             patch("src.tools.subscription_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_api_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed()

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_rss_articles_have_dedup(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_api_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )
        mock_rss_response = httpx.Response(
            200,
            text=MOCK_RSS_XML,
            request=httpx.Request("GET", "https://testpub.substack.com/feed"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache), \
             patch("src.tools.subscription_feed.get_subscriptions_list", new_callable=AsyncMock, return_value=MOCK_SUBSCRIPTIONS), \
             patch("src.tools.subscription_feed.fetch_rss", new_callable=AsyncMock, return_value=mock_rss_response), \
             patch("src.tools.subscription_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_api_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed()

        # All articles should be in cache now
        for article in result:
            assert cache.exists(article["id"])


class TestSubscriptionFeedSinceFilter:
    """Test since param filters."""

    @pytest.mark.asyncio
    async def test_since_filters_old_articles(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SUB_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache), \
             patch("src.tools.subscription_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed(since="2026-03-06T00:00:00Z")

        assert len(result) == 1


class TestSubscriptionFeedSummarize:
    """Test summarization applied."""

    @pytest.mark.asyncio
    async def test_summarize_true_returns_summary(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SUB_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache), \
             patch("src.tools.subscription_feed.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed(summarize=True)

        assert "summary" in result[0]


class TestSubscriptionFeedEmpty:
    """Test empty feed handled."""

    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty(self):
        from src.tools.subscription_feed import get_subscription_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json={"items": []},
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed?filter=subscription"),
        )

        with patch("src.tools.subscription_feed.get_client") as mock_gc, \
             patch("src.tools.subscription_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_subscription_feed()

        assert result == []


class TestSubscriptionFeedAuth:
    """Test auth error handling."""

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.subscription_feed import get_subscription_feed

        with patch("src.tools.subscription_feed.get_client", return_value=None):
            result = await get_subscription_feed()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
