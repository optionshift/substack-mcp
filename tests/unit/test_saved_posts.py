import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_SAVED_RESPONSE = {
    "posts": [
        {
            "id": 162633402,
            "publication_id": 2125183,
            "title": "89 Best Startup Essays by Top VCs and Founders",
            "slug": "best-startup-essays-vc-founders",
            "post_date": "2025-05-01T18:22:26.577Z",
            "audience": "only_paid",
            "type": "newsletter",
            "body_html": "<p>Great startup wisdom</p>",
            "publishedBylines": [{"name": "VC Corner Author"}],
            "canonical_url": "https://thevccorner.substack.com/p/best-startup-essays-vc-founders",
        },
        {
            "id": 191270969,
            "publication_id": 494303,
            "title": "How to Build a Content Engine",
            "slug": "how-to-build-content-engine",
            "post_date": "2026-03-17T20:07:15.213Z",
            "audience": "everyone",
            "type": "newsletter",
            "body_html": "<p>Content engine tips</p>",
            "publishedBylines": [{"name": "Content Author"}],
            "canonical_url": "https://contentpub.substack.com/p/how-to-build-content-engine",
        },
    ],
    "publications": [
        {
            "id": 2125183,
            "name": "The VC Corner",
            "subdomain": "thevccorner",
            "custom_domain": "www.thevccorner.com",
        },
        {
            "id": 494303,
            "name": "Content Lab",
            "subdomain": "contentpub",
            "custom_domain": None,
        },
    ],
    "savedPosts": [
        {"user_id": 383926424, "post_id": 191270969, "created_at": "2026-03-18T00:56:39.149Z"},
        {"user_id": 383926424, "post_id": 162633402, "created_at": "2026-03-17T00:19:52.420Z"},
    ],
    "inboxItems": [
        {
            "user_id": 383926424,
            "content_key": "post:191270969",
            "publication_id": 494303,
            "read_progress": 0.098,
            "max_read_progress": 0.989,
        },
        {
            "user_id": 383926424,
            "content_key": "post:162633402",
            "publication_id": 2125183,
            "read_progress": 0.0,
            "max_read_progress": 0.0,
        },
    ],
    "postViews": [],
    "postReactions": [],
    "more": True,
}

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "tags": ["startup"],
    "relevance": 9,
    "key_quote": "A quote.",
    "angle": "An angle",
}


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data or MOCK_SAVED_RESPONSE,
        request=httpx.Request("GET", "https://substack.com/api/v1/reader/posts"),
    )


class TestGetSavedPosts:
    """Tests for ss_get_saved_posts tool."""

    @pytest.mark.asyncio
    async def test_returns_saved_articles(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["source_feed"] == "saved"

    @pytest.mark.asyncio
    async def test_joins_publication_data(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        # First post (id=162633402) should have publication "The VC Corner"
        vc_article = [a for a in result if "VC" in a["title"]][0]
        assert vc_article["publication"] == "The VC Corner"

    @pytest.mark.asyncio
    async def test_includes_saved_at_timestamp(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        for article in result:
            assert "saved_at" in article

    @pytest.mark.asyncio
    async def test_includes_read_progress(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        content_article = [a for a in result if "Content" in a["title"]][0]
        assert content_article["read_progress"] == 0.098

    @pytest.mark.asyncio
    async def test_default_inbox_type_is_saved(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            await get_saved_posts()

        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs.kwargs["params"]
        assert params["inboxType"] == "saved"

    @pytest.mark.asyncio
    async def test_inbox_type_seen(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            await get_saved_posts(inbox_type="seen")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs.kwargs["params"]
        assert params["inboxType"] == "seen"

    @pytest.mark.asyncio
    async def test_inbox_type_paid(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            await get_saved_posts(inbox_type="paid")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs.kwargs["params"]
        assert params["inboxType"] == "paid"

    @pytest.mark.asyncio
    async def test_invalid_inbox_type_returns_error(self):
        from src.tools.saved_posts import get_saved_posts

        with patch("src.tools.saved_posts.get_client") as mock_gc:
            mock_gc.return_value = AsyncMock()
            result = await get_saved_posts(inbox_type="invalid")

        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_dedup_inserts_but_does_not_skip(self):
        """Saved posts should always be returned even if seen before (like search_posts)."""
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert("substack_post_162633402", "url", "title", "source", "saved")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert len(result) == 2
        vc_article = [a for a in result if "VC" in a["title"]][0]
        assert vc_article["is_new"] is False

    @pytest.mark.asyncio
    async def test_since_filters_by_saved_at(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts(since="2026-03-18T00:00:00Z")

        # Only the post saved at 2026-03-18 should pass
        assert len(result) == 1
        assert result[0]["title"] == "How to Build a Content Engine"

    @pytest.mark.asyncio
    async def test_limit_caps_results(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts(limit=1)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_hint_field_present(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        for article in result:
            assert "hint" in article
            assert "ss_get_post_content" in article["hint"]

    @pytest.mark.asyncio
    async def test_summarize_false_returns_content(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts(summarize=False)

        assert len(result) == 2
        for article in result:
            assert "content" in article

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.saved_posts import get_saved_posts

        with patch("src.tools.saved_posts.get_client", return_value=None):
            result = await get_saved_posts()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_401_returns_auth_error(self):
        from src.tools.saved_posts import get_saved_posts

        with patch("src.tools.saved_posts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(status=401, data={})
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.saved_posts import get_saved_posts

        with patch("src.tools.saved_posts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(status=500, data={})
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.saved_posts import get_saved_posts

        with patch("src.tools.saved_posts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_returns_list_type(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_hint_absent_when_no_url(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        data = {
            "posts": [{
                "id": 77777,
                "publication_id": 0,
                "title": "No URL Post",
                "slug": "no-url",
                "post_date": "2026-03-01T00:00:00Z",
                "audience": "everyone",
                "type": "newsletter",
                "body_html": "<p>Content</p>",
                "publishedBylines": [],
                "canonical_url": "",
            }],
            "publications": [],
            "savedPosts": [{"user_id": 383926424, "post_id": 77777, "created_at": "2026-03-01T00:00:00Z"}],
            "inboxItems": [],
            "postViews": [],
            "postReactions": [],
            "more": False,
        }

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(data=data)
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert len(result) == 1
        assert "hint" not in result[0]

    @pytest.mark.asyncio
    async def test_empty_saved_returns_empty_list(self):
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        empty_response = {
            "posts": [],
            "publications": [],
            "savedPosts": [],
            "inboxItems": [],
            "postViews": [],
            "postReactions": [],
            "more": False,
        }

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(data=empty_response)
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert result == []

    @pytest.mark.asyncio
    async def test_missing_publication_graceful(self):
        """Posts with no matching publication should still return."""
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        data = {
            "posts": [{
                "id": 99999,
                "publication_id": 0,
                "title": "Orphan Post",
                "slug": "orphan-post",
                "post_date": "2026-03-01T00:00:00Z",
                "audience": "everyone",
                "type": "newsletter",
                "body_html": "<p>No pub</p>",
                "publishedBylines": [],
                "canonical_url": "https://orphan.substack.com/p/orphan-post",
            }],
            "publications": [],
            "savedPosts": [{"user_id": 383926424, "post_id": 99999, "created_at": "2026-03-01T00:00:00Z"}],
            "inboxItems": [],
            "postViews": [],
            "postReactions": [],
            "more": False,
        }

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(data=data)
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert len(result) == 1
        assert result[0]["publication"] == ""

    @pytest.mark.asyncio
    async def test_summarize_fallback_returns_raw_content(self):
        """When summarizer fails, raw_content is returned instead of summary fields."""
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        fallback_result = {"raw_content": "Summarization failed, here is the raw text..."}

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=fallback_result):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert len(result) == 2
        for article in result:
            assert "raw_content" in article
            assert "summary" not in article

    @pytest.mark.asyncio
    async def test_malformed_content_key_handled(self):
        """Malformed content_key in inboxItems should not crash."""
        from src.tools.saved_posts import get_saved_posts
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        data = {
            "posts": [{
                "id": 11111,
                "publication_id": 0,
                "title": "Test Post",
                "slug": "test",
                "post_date": "2026-03-01T00:00:00Z",
                "audience": "everyone",
                "type": "newsletter",
                "body_html": "<p>Test</p>",
                "publishedBylines": [],
                "canonical_url": "https://test.substack.com/p/test",
            }],
            "publications": [],
            "savedPosts": [{"user_id": 383926424, "post_id": 11111, "created_at": "2026-03-01T00:00:00Z"}],
            "inboxItems": [
                {"content_key": "post:", "read_progress": 0.5},
                {"content_key": "post:abc", "read_progress": 0.3},
            ],
            "postViews": [],
            "postReactions": [],
            "more": False,
        }

        with patch("src.tools.saved_posts.get_client") as mock_gc, \
             patch("src.tools.saved_posts.get_cache", return_value=cache), \
             patch("src.tools.saved_posts.run_summarize", new_callable=AsyncMock, return_value=MOCK_SUMMARY):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(data=data)
            mock_gc.return_value = mock_client

            result = await get_saved_posts()

        assert len(result) == 1
        assert result[0]["read_progress"] == 0.0
