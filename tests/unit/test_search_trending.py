import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_TRENDING_RESPONSE = {
    "items": [
        {
            "entity_key": "p-191041024",
            "type": "post",
            "post": {
                "id": 191041024,
                "title": "AI Agents Are Changing Everything",
                "slug": "ai-agents-changing-everything",
                "post_date": "2026-03-15T18:36:30.000Z",
                "canonical_url": "https://aiweekly.substack.com/p/ai-agents-changing-everything",
                "body_html": "<p>Trending content</p>",
            },
            "publication": {
                "name": "AI Weekly",
                "subdomain": "aiweekly",
            },
            "context": {
                "type": "post",
                "timestamp": "2026-03-15T18:36:30.000Z",
                "users": [
                    {"id": 100000, "name": "AI Weekly Author", "handle": "aiweekly"}
                ],
                "searchTrackingParameters": {
                    "query": "AI agents",
                    "search_source": "knn-post-search",
                    "search_score": 0.85,
                    "recency_score": 0.92,
                    "semantic_score": 0.75,
                    "pos_engagement_score": 0.60,
                    "ranker_score": 0.88,
                },
            },
        },
        {
            "entity_key": "p-190500000",
            "type": "post",
            "post": {
                "id": 190500000,
                "title": "Building AI-First Products",
                "slug": "building-ai-first-products",
                "post_date": "2026-03-14T12:00:00.000Z",
                "canonical_url": "https://techblog.substack.com/p/building-ai-first-products",
                "body_html": "<p>More trending content</p>",
            },
            "publication": {
                "name": "Tech Blog",
                "subdomain": "techblog",
            },
            "context": {
                "type": "post",
                "timestamp": "2026-03-14T12:00:00.000Z",
                "users": [
                    {"id": 200000, "name": "Tech Author", "handle": "techauthor"}
                ],
                "searchTrackingParameters": {
                    "query": "AI agents",
                    "search_source": "knn-post-search",
                    "search_score": 0.72,
                    "recency_score": 0.80,
                    "semantic_score": 0.65,
                    "pos_engagement_score": 0.45,
                    "ranker_score": 0.70,
                },
            },
        },
    ],
}

MOCK_EMPTY_RESPONSE = {"items": []}


class TestSearchTrendingBasic:
    """Test basic trending search functionality."""

    @pytest.mark.asyncio
    async def test_returns_trending_articles(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_TRENDING_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="AI agents")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["title"] == "AI Agents Are Changing Everything"

    @pytest.mark.asyncio
    async def test_article_has_required_fields(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_TRENDING_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="AI agents")

        article = result[0]
        assert "id" in article
        assert "title" in article
        assert "author" in article
        assert "publication" in article
        assert "url" in article
        assert "published_at" in article
        assert "search_score" in article
        assert "recency_score" in article
        assert "hint" in article
        assert "is_new" in article
        assert article["platform"] == "substack"
        assert article["source_feed"] == "trending"

    @pytest.mark.asyncio
    async def test_scores_extracted_correctly(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_TRENDING_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="AI agents")

        assert result[0]["search_score"] == 0.85
        assert result[0]["recency_score"] == 0.92

    @pytest.mark.asyncio
    async def test_hint_field_present(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_TRENDING_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="AI agents")

        for article in result:
            assert "ss_get_post_content" in article["hint"]

    @pytest.mark.asyncio
    async def test_limit_caps_results(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_TRENDING_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="AI agents", limit=1)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_dedup_inserts_but_does_not_skip(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert("substack_post_191041024", "url", "title", "source", "fyp")

        mock_response = httpx.Response(
            200,
            json=MOCK_TRENDING_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="AI agents")

        assert len(result) == 2
        assert result[0]["is_new"] is False
        assert result[1]["is_new"] is True


class TestSearchTrendingErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_no_cookie_returns_error(self):
        from src.tools.search_trending import search_trending

        with patch("src.tools.search_trending.get_client", return_value=None):
            result = await search_trending(query="test")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_401_returns_auth_expired(self):
        from src.tools.search_trending import search_trending

        mock_response = httpx.Response(
            401, json={},
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="test")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.search_trending import search_trending

        mock_response = httpx.Response(
            500, json={},
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="test")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.search_trending import search_trending

        with patch("src.tools.search_trending.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection failed")
            mock_gc.return_value = mock_client

            result = await search_trending(query="test")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self):
        from src.tools.search_trending import search_trending
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/recent/search"),
        )

        with patch("src.tools.search_trending.get_client") as mock_gc, \
             patch("src.tools.search_trending.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_trending(query="nonexistent")

        assert result == []
