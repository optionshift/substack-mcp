import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_RESTACKS_RESPONSE = {
    "items": [
        {
            "entity_key": "p-5001",
            "type": "post",
            "post": {
                "id": 5001,
                "title": "Restacked Article",
                "slug": "restacked-article",
                "post_date": "2026-03-06T10:00:00Z",
                "publishedBylines": [{"name": "Restack Author"}],
                "publication": {"name": "Restack Pub", "subdomain": "restackpub"},
                "canonical_url": "https://restackpub.substack.com/p/restacked-article",
                "body_html": "<p>Restacked content</p>",
            },
            "comment": None,
            "context": {"type": "restack"},
        },
    ],
}

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "tags": ["creator-economy"],
    "relevance": 10,
    "key_quote": "A quote.",
    "angle": "An angle",
}


class TestRestacksFeed:
    """Test returns restacked articles."""

    @pytest.mark.asyncio
    async def test_returns_restacked_articles(self):
        from src.tools.restacks import get_restacks
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_RESTACKS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.restacks.get_client") as mock_gc, \
             patch("src.tools.restacks.get_cache", return_value=cache), \
             patch("src.tools.restacks.get_cached_user_id", return_value="12345"), \
             patch("src.tools.restacks.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_restacks()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["source_feed"] == "restacks"

    @pytest.mark.asyncio
    async def test_uses_cached_user_id(self):
        from src.tools.restacks import get_restacks
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_RESTACKS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.restacks.get_client") as mock_gc, \
             patch("src.tools.restacks.get_cache", return_value=cache), \
             patch("src.tools.restacks.get_cached_user_id", return_value="12345"), \
             patch("src.tools.restacks.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            await get_restacks()

        call_args = mock_client.get.call_args
        assert "12345" in call_args[0][0]
        assert "restack" in call_args[1].get("params", {}).get("types[]", "")

    @pytest.mark.asyncio
    async def test_no_user_id_returns_error(self):
        from src.tools.restacks import get_restacks

        with patch("src.tools.restacks.get_client") as mock_gc, \
             patch("src.tools.restacks.get_cached_user_id", return_value=None):
            mock_gc.return_value = AsyncMock()

            result = await get_restacks()

        assert result["error"] is True

    @pytest.mark.asyncio
    async def test_dedup_applied(self):
        from src.tools.restacks import get_restacks
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert("substack_post_5001", "url", "title", "source", "restacks")

        mock_response = httpx.Response(
            200,
            json=MOCK_RESTACKS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/reader/feed/profile/12345"),
        )

        with patch("src.tools.restacks.get_client") as mock_gc, \
             patch("src.tools.restacks.get_cache", return_value=cache), \
             patch("src.tools.restacks.get_cached_user_id", return_value="12345"):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_restacks()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.restacks import get_restacks

        with patch("src.tools.restacks.get_client", return_value=None):
            result = await get_restacks()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
