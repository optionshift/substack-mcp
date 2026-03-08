import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_NOTES_RESPONSE = {
    "items": [
        {
            "entity_key": "c-6001",
            "type": "comment",
            "post": None,
            "comment": {
                "id": 6001,
                "name": "Note Author",
                "handle": "noteauthor",
                "body": "This is a short note about AI agents",
                "date": "2026-03-06T10:00:00Z",
                "reaction_count": 15,
                "restacks": 5,
                "children_count": 3,
            },
            "context": {"type": "note", "typeBucket": "notes"},
        },
        {
            "entity_key": "c-6002",
            "type": "comment",
            "post": None,
            "comment": {
                "id": 6002,
                "name": "Note Author 2",
                "handle": "noteauthor2",
                "body": "A low engagement note",
                "date": "2026-03-05T08:00:00Z",
                "reaction_count": 2,
                "restacks": 0,
                "children_count": 1,
            },
            "context": {"type": "note", "typeBucket": "notes"},
        },
        {
            "entity_key": "p-9999",
            "type": "post",
            "post": {
                "id": 9999,
                "title": "A post mixed in the feed",
                "post_date": "2026-03-06T09:00:00Z",
            },
            "comment": None,
            "context": {"type": "post", "typeBucket": "posts"},
        },
    ],
}


class TestNotesFeedBasic:
    """Test returns notes with correct schema."""

    @pytest.mark.asyncio
    async def test_returns_notes(self):
        from src.tools.notes_feed import get_notes_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_NOTES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/notes"),
        )

        with patch("src.tools.notes_feed.get_client") as mock_gc, \
             patch("src.tools.notes_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_notes_feed()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_note_has_correct_schema(self):
        from src.tools.notes_feed import get_notes_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_NOTES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/notes"),
        )

        with patch("src.tools.notes_feed.get_client") as mock_gc, \
             patch("src.tools.notes_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_notes_feed()

        note = result[0]
        assert "id" in note
        assert "author" in note
        assert "content" in note
        assert "timestamp" in note
        assert "likes" in note
        assert "restacks" in note
        assert "comments" in note
        assert "url" in note
        assert "high_signal" in note
        # Should NOT have article-specific fields
        assert "summary" not in note
        assert "tags" not in note
        assert "publication" not in note


class TestNotesFeedHighSignal:
    """Test high-signal flagging."""

    @pytest.mark.asyncio
    async def test_high_likes_flagged(self):
        from src.tools.notes_feed import get_notes_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_NOTES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/notes"),
        )

        with patch("src.tools.notes_feed.get_client") as mock_gc, \
             patch("src.tools.notes_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_notes_feed()

        # First note: 15 likes > 10, 5 restacks > 3 → high_signal
        assert result[0]["high_signal"] is True
        # Second note: 2 likes, 0 restacks → not high_signal
        assert result[1]["high_signal"] is False


class TestNotesFeedDedup:
    """Test dedup applied by note ID."""

    @pytest.mark.asyncio
    async def test_dedup_skips_seen_notes(self):
        from src.tools.notes_feed import get_notes_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        cache.insert("substack_note_6001", "url", "title", "source", "notes")

        mock_response = httpx.Response(
            200,
            json=MOCK_NOTES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/notes"),
        )

        with patch("src.tools.notes_feed.get_client") as mock_gc, \
             patch("src.tools.notes_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_notes_feed()

        assert len(result) == 1
        assert result[0]["id"] == "substack_note_6002"


class TestNotesFeedSinceFilter:
    """Test since param filters."""

    @pytest.mark.asyncio
    async def test_since_filters_old_notes(self):
        from src.tools.notes_feed import get_notes_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json=MOCK_NOTES_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/notes"),
        )

        with patch("src.tools.notes_feed.get_client") as mock_gc, \
             patch("src.tools.notes_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_notes_feed(since="2026-03-06T00:00:00Z")

        assert len(result) == 1


class TestNotesFeedEmpty:
    """Test empty feed handled."""

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        from src.tools.notes_feed import get_notes_feed
        from src.dedup import DedupCache

        cache = DedupCache(":memory:")
        mock_response = httpx.Response(
            200,
            json={"items": []},
            request=httpx.Request("GET", "https://substack.com/api/v1/notes"),
        )

        with patch("src.tools.notes_feed.get_client") as mock_gc, \
             patch("src.tools.notes_feed.get_cache", return_value=cache):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await get_notes_feed()

        assert result == []


class TestNotesFeedAuth:
    """Test auth error handling."""

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.notes_feed import get_notes_feed

        with patch("src.tools.notes_feed.get_client", return_value=None):
            result = await get_notes_feed()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
