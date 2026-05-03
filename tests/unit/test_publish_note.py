import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {"id": 12345, "body": "hi"},
        request=httpx.Request("POST", "https://substack.com/api/v1/comment/feed"),
    )


class TestPublishNote:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await publish_note(text="two years ago i wouldn't know an API from a CLI")

        assert result["success"] is True
        assert result["id"] == 12345

    @pytest.mark.asyncio
    async def test_publish_calls_correct_endpoint(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            await publish_note(text="hello")

        mock_client.post.assert_called_once()
        call = mock_client.post.call_args
        assert call.args[0] == "/api/v1/comment/feed"
        body = call.kwargs["json"]
        assert body["bodyJson"]["type"] == "doc"
        assert body["bodyJson"]["content"][0]["content"][0]["text"] == "hello"
        assert body["replyMinimumRole"] == "everyone"

    @pytest.mark.asyncio
    async def test_publish_voice_violation_blocks(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            result = await publish_note(text="we leverage synergy — it's revolutionary")

        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
        assert "violations" in result
        # Endpoint NOT called
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_force_bypasses_voice(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await publish_note(text="we leverage synergy", force=True)

        assert result["success"] is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_missing_cookie(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client", return_value=None):
            result = await publish_note(text="clean text")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_publish_401(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await publish_note(text="clean text")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
