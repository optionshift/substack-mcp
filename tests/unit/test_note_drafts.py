import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {"id": 1},
        request=httpx.Request(method, "https://substack.com/api/v1/comment/draft"),
    )


class TestCreateNoteDraft:
    @pytest.mark.asyncio
    async def test_create_unscheduled(self):
        from src.tools.note_drafts import create_note_draft

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 252827081, "trigger_at": None})
            mock_gc.return_value = mock_client

            result = await create_note_draft(text="some clean note text")

        assert result["success"] is True
        assert result["id"] == 252827081
        body = mock_client.post.call_args.kwargs["json"]
        assert "trigger_at" not in body or body["trigger_at"] is None
        assert body["bodyJson"]["content"][0]["content"][0]["text"] == "some clean note text"

    @pytest.mark.asyncio
    async def test_create_voice_blocks(self):
        from src.tools.note_drafts import create_note_draft

        result = await create_note_draft(text="we leverage synergy")
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"

    @pytest.mark.asyncio
    async def test_create_force_bypasses_voice(self):
        from src.tools.note_drafts import create_note_draft

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 9, "trigger_at": None})
            mock_gc.return_value = mock_client

            result = await create_note_draft(text="we leverage synergy", force=True)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_validation_empty(self):
        from src.tools.note_drafts import create_note_draft

        result = await create_note_draft(text="   ")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_create_missing_cookie(self):
        from src.tools.note_drafts import create_note_draft

        with patch("src.tools.note_drafts.get_client", return_value=None):
            result = await create_note_draft(text="clean note text")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_create_401(self):
        from src.tools.note_drafts import create_note_draft

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await create_note_draft(text="clean note text")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestScheduleNote:
    @pytest.mark.asyncio
    async def test_schedule_success(self):
        from src.tools.note_drafts import schedule_note

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 252827081, "trigger_at": "2026-06-01T00:00:00.000Z"})
            mock_gc.return_value = mock_client

            result = await schedule_note(text="hi", trigger_at_iso="2026-06-01T00:00:00.000Z")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["trigger_at"] == "2026-06-01T00:00:00.000Z"

    @pytest.mark.asyncio
    async def test_schedule_voice_blocks(self):
        from src.tools.note_drafts import schedule_note

        result = await schedule_note(text="we leverage synergy", trigger_at_iso="2026-06-01T00:00:00.000Z")
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"


class TestListNoteDrafts:
    @pytest.mark.asyncio
    async def test_list(self):
        from src.tools.note_drafts import list_note_drafts

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(
                data={"drafts": [
                    {"id": 1, "trigger_at": None},
                    {"id": 2, "trigger_at": "2026-06-01T00:00:00.000Z"},
                ], "hasMore": False, "nextCursor": None},
                method="GET",
            )
            mock_gc.return_value = mock_client

            result = await list_note_drafts()

        assert len(result["drafts"]) == 2
        mock_client.get.assert_called_once_with("/api/v1/feed/drafts", params={"limit": 20})

    @pytest.mark.asyncio
    async def test_list_missing_cookie(self):
        from src.tools.note_drafts import list_note_drafts

        with patch("src.tools.note_drafts.get_client", return_value=None):
            result = await list_note_drafts()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestCancelScheduledNote:
    @pytest.mark.asyncio
    async def test_cancel(self):
        from src.tools.note_drafts import cancel_scheduled_note

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(method="DELETE")
            mock_gc.return_value = mock_client

            result = await cancel_scheduled_note(comment_id="252827081")

        assert result["success"] is True
        mock_client.delete.assert_called_once_with("/api/v1/comment/252827081")

    @pytest.mark.asyncio
    async def test_cancel_invalid_id(self):
        from src.tools.note_drafts import cancel_scheduled_note

        result = await cancel_scheduled_note(comment_id="not-numeric")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_cancel_401(self):
        from src.tools.note_drafts import cancel_scheduled_note

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(status=401, method="DELETE")
            mock_gc.return_value = mock_client

            result = await cancel_scheduled_note(comment_id="252827081")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
