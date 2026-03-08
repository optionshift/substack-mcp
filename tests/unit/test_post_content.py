import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_POST_RESPONSE = {
    "id": 3001,
    "title": "Deep Dive into AI",
    "slug": "deep-dive-ai",
    "post_date": "2026-03-06T10:00:00Z",
    "publishedBylines": [{"name": "Deep Author"}],
    "publication": {"name": "AI Weekly", "subdomain": "aiweekly"},
    "canonical_url": "https://aiweekly.substack.com/p/deep-dive-ai",
    "body_html": "<h1>Deep Dive</h1><p>This is a deep dive into AI agents and their impact.</p>",
}

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "tags": ["AI-agents"],
    "relevance": 9,
    "key_quote": "A quote.",
    "angle": "An angle",
}


class TestPostContentByURL:
    """Test returns full article by URL."""

    @pytest.mark.asyncio
    async def test_returns_article_by_url(self):
        from src.tools.post_content import get_post_content
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_POST_RESPONSE,
            request=httpx.Request("GET", "https://aiweekly.substack.com/api/v1/posts/deep-dive-ai"),
        )

        with patch("src.tools.post_content.get_cache", return_value=cache), \
             patch("src.tools.post_content.fetch_post", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.post_content.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):

            result = await get_post_content(url="https://aiweekly.substack.com/p/deep-dive-ai")

        assert result["title"] == "Deep Dive into AI"
        assert result["id"] == "substack_post_3001"

    @pytest.mark.asyncio
    async def test_url_parsing_extracts_subdomain_and_slug(self):
        from src.tools.post_content import parse_substack_url

        subdomain, slug = parse_substack_url("https://aiweekly.substack.com/p/deep-dive-ai")
        assert subdomain == "aiweekly"
        assert slug == "deep-dive-ai"

    @pytest.mark.asyncio
    async def test_url_parsing_custom_domain(self):
        from src.tools.post_content import parse_substack_url

        # Custom domains won't have .substack.com
        subdomain, slug = parse_substack_url("https://example.com/p/my-article")
        assert subdomain == "example.com"
        assert slug == "my-article"


class TestPostContentHTML:
    """Test HTML converts to markdown."""

    @pytest.mark.asyncio
    async def test_html_converts_to_markdown(self):
        from src.tools.post_content import get_post_content
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_POST_RESPONSE,
            request=httpx.Request("GET", "https://aiweekly.substack.com/api/v1/posts/deep-dive-ai"),
        )

        with patch("src.tools.post_content.get_cache", return_value=cache), \
             patch("src.tools.post_content.fetch_post", new_callable=AsyncMock, return_value=mock_response):

            result = await get_post_content(url="https://aiweekly.substack.com/p/deep-dive-ai", summarize=False)

        assert "raw_content" in result
        # Should be markdown, not HTML
        assert "<p>" not in result["raw_content"]


class TestPostContentDedup:
    """Test dedup exception: does NOT skip, but DOES insert."""

    @pytest.mark.asyncio
    async def test_inserts_into_cache(self):
        from src.tools.post_content import get_post_content
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_POST_RESPONSE,
            request=httpx.Request("GET", "https://aiweekly.substack.com/api/v1/posts/deep-dive-ai"),
        )

        with patch("src.tools.post_content.get_cache", return_value=cache), \
             patch("src.tools.post_content.fetch_post", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.post_content.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):

            await get_post_content(url="https://aiweekly.substack.com/p/deep-dive-ai")

        assert cache.exists("substack_post_3001")

    @pytest.mark.asyncio
    async def test_does_not_skip_existing(self):
        from src.tools.post_content import get_post_content
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        # Pre-insert as seen
        cache.insert("substack_post_3001", "url", "title", "source", "fyp")

        mock_response = httpx.Response(
            200,
            json=MOCK_POST_RESPONSE,
            request=httpx.Request("GET", "https://aiweekly.substack.com/api/v1/posts/deep-dive-ai"),
        )

        with patch("src.tools.post_content.get_cache", return_value=cache), \
             patch("src.tools.post_content.fetch_post", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.post_content.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):

            result = await get_post_content(url="https://aiweekly.substack.com/p/deep-dive-ai")

        # Should still return the article even though it's already seen
        assert result["title"] == "Deep Dive into AI"
        assert result["is_new"] is False


class TestPostContentSummarize:
    """Test summarization with truncation."""

    @pytest.mark.asyncio
    async def test_summarize_true_returns_summary(self):
        from src.tools.post_content import get_post_content
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_POST_RESPONSE,
            request=httpx.Request("GET", "https://aiweekly.substack.com/api/v1/posts/deep-dive-ai"),
        )

        with patch("src.tools.post_content.get_cache", return_value=cache), \
             patch("src.tools.post_content.fetch_post", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.post_content.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):

            result = await get_post_content(url="https://aiweekly.substack.com/p/deep-dive-ai", summarize=True)

        assert "summary" in result


class TestPostContentErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_missing_post_returns_not_found(self):
        from src.tools.post_content import get_post_content

        mock_response = httpx.Response(
            404,
            json={"error": "not found"},
            request=httpx.Request("GET", "https://aiweekly.substack.com/api/v1/posts/nonexistent"),
        )

        with patch("src.tools.post_content.fetch_post", new_callable=AsyncMock, return_value=mock_response):
            result = await get_post_content(url="https://aiweekly.substack.com/p/nonexistent")

        assert result["error"] is True
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_no_url_returns_error(self):
        from src.tools.post_content import get_post_content

        result = await get_post_content()

        assert result["error"] is True
