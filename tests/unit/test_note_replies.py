import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {"commentBranches": []},
        request=httpx.Request("GET", "https://substack.com/api/v1/reader/comment/123/replies"),
    )


class TestGetNoteReplies:
    @pytest.mark.asyncio
    async def test_get_replies_success(self):
        from src.tools.note_replies import get_note_replies

        with patch("src.tools.note_replies.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(
                data={"commentBranches": [{"id": 1, "descendantComments": []}]}
            )
            mock_gc.return_value = mock_client

            result = await get_note_replies(note_id="252827081")

        assert "commentBranches" in result
        mock_client.get.assert_called_once_with(
            "/api/v1/reader/comment/252827081/replies",
            params={},
        )

    @pytest.mark.asyncio
    async def test_get_replies_with_cursor(self):
        from src.tools.note_replies import get_note_replies

        with patch("src.tools.note_replies.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            await get_note_replies(note_id="252827081", cursor="abc123")

        assert mock_client.get.call_args.kwargs["params"] == {"cursor": "abc123"}

    @pytest.mark.asyncio
    async def test_get_replies_invalid_id(self):
        from src.tools.note_replies import get_note_replies

        result = await get_note_replies(note_id="not-numeric")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
