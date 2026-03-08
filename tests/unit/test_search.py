import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_SEARCH_RESPONSE = [
    {
        "name": "AI Weekly",
        "subdomain": "aiweekly",
        "custom_domain": None,
        "author_name": "AI Author",
        "description": "Weekly AI news",
        "active_subscribers": 5000,
    },
    {
        "name": "Creator Economy Daily",
        "subdomain": "creatordaily",
        "custom_domain": "creatordaily.com",
        "author_name": "Creator Author",
        "description": "Daily creator tips",
        "active_subscribers": 12000,
    },
]


class TestSearchPublications:
    """Test returns publications matching query."""

    @pytest.mark.asyncio
    async def test_returns_publications(self):
        from src.tools.search import search_publications

        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/publication/search"),
        )

        with patch("src.tools.search.fetch_search", new_callable=AsyncMock, return_value=mock_response):
            result = await search_publications(query="AI")

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_publication_has_correct_schema(self):
        from src.tools.search import search_publications

        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/publication/search"),
        )

        with patch("src.tools.search.fetch_search", new_callable=AsyncMock, return_value=mock_response):
            result = await search_publications(query="AI")

        pub = result[0]
        assert "name" in pub
        assert "url" in pub
        assert "author" in pub
        assert "description" in pub
        assert "subscriber_count" in pub

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        from src.tools.search import search_publications

        mock_response = httpx.Response(
            200,
            json=MOCK_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/publication/search"),
        )

        with patch("src.tools.search.fetch_search", new_callable=AsyncMock, return_value=mock_response):
            result = await search_publications(query="AI", limit=1)

        assert len(result) == 1


class TestSearchEmpty:
    """Test handles empty results."""

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from src.tools.search import search_publications

        mock_response = httpx.Response(
            200,
            json=[],
            request=httpx.Request("GET", "https://substack.com/api/v1/publication/search"),
        )

        with patch("src.tools.search.fetch_search", new_callable=AsyncMock, return_value=mock_response):
            result = await search_publications(query="nonexistent")

        assert result == []


class TestSearchSpecialChars:
    """Test handles special characters in query."""

    @pytest.mark.asyncio
    async def test_special_characters(self):
        from src.tools.search import search_publications

        mock_response = httpx.Response(
            200,
            json=[],
            request=httpx.Request("GET", "https://substack.com/api/v1/publication/search"),
        )

        with patch("src.tools.search.fetch_search", new_callable=AsyncMock, return_value=mock_response):
            # Should not raise
            result = await search_publications(query="AI & ML <script>")

        assert isinstance(result, list)


class TestSearchErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_network_error(self):
        from src.tools.search import search_publications

        with patch("src.tools.search.fetch_search", new_callable=AsyncMock, side_effect=Exception("Connection error")):
            result = await search_publications(query="AI")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"
