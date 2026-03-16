import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_SEARCH_RESPONSE = {
    "results": [
        {
            "id": 189918781,
            "publication_id": 3054100,
            "title": "Creator Economy Trends 2026",
            "type": "newsletter",
            "slug": "creator-economy-trends-2026",
            "post_date": "2026-03-06T05:08:36.227Z",
            "subtitle": "Data-led intelligence report",
            "truncated_body_text": "The full report is now available in both print and digital formats.",
            "wordcount": 1219,
            "reactions": {"❤": 3},
            "restacks": 2,
            "comment_count": 0,
            "canonical_url": "https://creatoreconomyiiq.substack.com/p/creator-economy-trends-2026",
            "publishedBylines": [
                {"id": 269247615, "name": "Creator Economy IQ", "handle": "creatorecoiq"}
            ],
            "section_id": 151857,
            "section_name": "Music Business IQ",
            "cover_image": "https://substackcdn.com/image/fetch/example.jpg",
        },
        {
            "id": 190123456,
            "publication_id": 4000000,
            "title": "AI and the Creator Economy",
            "type": "newsletter",
            "slug": "ai-creator-economy",
            "post_date": "2026-03-05T12:00:00.000Z",
            "subtitle": "How AI changes content creation",
            "truncated_body_text": "AI is transforming how creators work.",
            "wordcount": 2500,
            "reactions": {"❤": 15},
            "restacks": 8,
            "comment_count": 3,
            "canonical_url": "https://aiweekly.substack.com/p/ai-creator-economy",
            "publishedBylines": [
                {"id": 100000, "name": "AI Weekly", "handle": "aiweekly"}
            ],
        },
    ],
}

MOCK_EMPTY_RESPONSE = {"results": []}


class TestSearchPostsBasic:
    """Test basic article search functionality."""

    @pytest.mark.asyncio
    async def test_returns_articles_matching_query(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="creator economy")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["title"] == "Creator Economy Trends 2026"

    @pytest.mark.asyncio
    async def test_article_has_required_fields(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="creator economy")

        article = result[0]
        assert "id" in article
        assert "title" in article
        assert "author" in article
        assert "url" in article
        assert "published_at" in article
        assert "preview" in article
        assert "wordcount" in article
        assert "reactions" in article
        assert "restacks" in article
        assert "comment_count" in article
        assert "hint" in article
        assert "is_new" in article
        assert "platform" in article
        assert article["platform"] == "substack"
        assert article["source_feed"] == "search"

    @pytest.mark.asyncio
    async def test_hint_field_present(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="creator economy")

        for article in result:
            assert "ss_get_post_content" in article["hint"]

    @pytest.mark.asyncio
    async def test_dedup_inserts_but_does_not_skip(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        # Pre-insert first article
        cache.insert("substack_post_189918781", "url", "title", "source", "fyp")

        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="creator economy")

        # Should still return both articles (no skip), but first one is_new=False
        assert len(result) == 2
        assert result[0]["is_new"] is False
        assert result[1]["is_new"] is True


class TestSearchPostsFilters:
    """Test search filter parameters."""

    @pytest.mark.asyncio
    async def test_filter_all_sets_include_platform_true(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await search_posts(query="test", filter="all")

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs["params"]
        assert params["includePlatformResults"] == "true"
        assert params["filter"] == "all"

    @pytest.mark.asyncio
    async def test_filter_subscribed_sets_include_platform_false(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await search_posts(query="test", filter="subscribed")

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs["params"]
        assert params["includePlatformResults"] == "false"
        assert params["filter"] == "subscribed"

    @pytest.mark.asyncio
    async def test_date_range_passed_to_api(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await search_posts(query="test", date_range="week")

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs["params"]
        assert params["dateRange"] == "week"

    @pytest.mark.asyncio
    async def test_no_date_range_omits_param(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await search_posts(query="test", date_range=None)

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs["params"]
        assert "dateRange" not in params

    @pytest.mark.asyncio
    async def test_invalid_filter_returns_error(self):
        from src.tools.search_posts import search_posts

        with patch("src.tools.search_posts.get_client") as mock_gc:
            mock_gc.return_value = AsyncMock()
            result = await search_posts(query="test", filter="invalid")

        assert result["error"] is True
        assert result["code"] == "INVALID_PARAM"

    @pytest.mark.asyncio
    async def test_invalid_date_range_returns_error(self):
        from src.tools.search_posts import search_posts

        with patch("src.tools.search_posts.get_client") as mock_gc:
            mock_gc.return_value = AsyncMock()
            result = await search_posts(query="test", date_range="year")

        assert result["error"] is True
        assert result["code"] == "INVALID_PARAM"


class TestSearchPostsPagination:
    """Test pagination support."""

    @pytest.mark.asyncio
    async def test_page_param_passed_to_api(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await search_posts(query="test", page=2)

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs["params"]
        assert params["page"] == 2

    @pytest.mark.asyncio
    async def test_limit_caps_results(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="test", limit=1)

        assert len(result) == 1


class TestSearchPostsErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_no_cookie_returns_error(self):
        from src.tools.search_posts import search_posts

        with patch("src.tools.search_posts.get_client", return_value=None):
            result = await search_posts(query="test")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_401_returns_auth_expired(self):
        from src.tools.search_posts import search_posts

        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="test")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.search_posts import search_posts

        mock_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="test")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.search_posts import search_posts

        with patch("src.tools.search_posts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection failed")
            mock_gc.return_value = mock_client

            result = await search_posts(query="test")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self):
        from src.tools.search_posts import search_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_EMPTY_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/post/search"),
        )

        with patch("src.tools.search_posts.get_client") as mock_gc, \
             patch("src.tools.search_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await search_posts(query="nonexistent")

        assert result == []
