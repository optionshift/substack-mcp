import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_LIKES_RESPONSE = {
    "posts": [
        {
            "id": 4001,
            "title": "Liked Article",
            "slug": "liked-article",
            "post_date": "2026-03-06T10:00:00Z",
            "publishedBylines": [{"name": "Liked Author"}],
            "publication": {"name": "Liked Pub", "subdomain": "likedpub"},
            "canonical_url": "https://likedpub.substack.com/p/liked-article",
            "body_html": "<p>Liked content</p>",
        },
    ],
}

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "tags": ["creator-economy"],
    "relevance": 9,
    "key_quote": "A quote.",
    "angle": "An angle",
}


class TestLikesFeed:
    """Test returns liked articles."""

    @pytest.mark.asyncio
    async def test_returns_liked_articles(self):
        from src.tools.likes import get_likes
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_LIKES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.likes.get_client") as mock_gc, \
             patch("src.tools.likes.get_cache", return_value=cache), \
             patch("src.tools.likes.get_cached_user_id", return_value="12345"), \
             patch("src.tools.likes.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_likes()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["source_feed"] == "likes"

    @pytest.mark.asyncio
    async def test_uses_cached_user_id(self):
        from src.tools.likes import get_likes
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_LIKES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.likes.get_client") as mock_gc, \
             patch("src.tools.likes.get_cache", return_value=cache), \
             patch("src.tools.likes.get_cached_user_id", return_value="12345"), \
             patch("src.tools.likes.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await get_likes()

        # Verify the endpoint was called with user_id
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "12345" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_user_id_returns_error(self):
        from src.tools.likes import get_likes

        with patch("src.tools.likes.get_client") as mock_gc, \
             patch("src.tools.likes.get_cached_user_id", return_value=None):
            mock_gc.return_value = AsyncMock()

            result = await get_likes()

        assert result["error"] is True

    @pytest.mark.asyncio
    async def test_dedup_applied(self):
        from src.tools.likes import get_likes
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert("substack_post_4001", "url", "title", "source", "likes")

        mock_response = httpx.Response(
            200,
            json=MOCK_LIKES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.likes.get_client") as mock_gc, \
             patch("src.tools.likes.get_cache", return_value=cache), \
             patch("src.tools.likes.get_cached_user_id", return_value="12345"):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_likes()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_since_filters(self):
        from src.tools.likes import get_likes
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_LIKES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.likes.get_client") as mock_gc, \
             patch("src.tools.likes.get_cache", return_value=cache), \
             patch("src.tools.likes.get_cached_user_id", return_value="12345"), \
             patch("src.tools.likes.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_likes(since="2026-03-07T00:00:00Z")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.likes import get_likes

        with patch("src.tools.likes.get_client", return_value=None):
            result = await get_likes()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
