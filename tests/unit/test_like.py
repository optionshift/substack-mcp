import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import httpx


def make_response(status_code: int, json_data: dict = None):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    return response


class TestLikePost:
    """Test liking an article (POST /api/v1/post/{id}/reaction)."""

    @pytest.mark.asyncio
    async def test_like_post_success(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=make_response(200, {}))

        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="190215624", type="post")

        assert result["success"] is True
        assert result["id"] == "190215624"
        assert result["type"] == "post"
        mock_client.post.assert_called_once_with(
            "/api/v1/post/190215624/reaction",
            json={"reaction": "❤", "surface": "reader", "tabId": "for-you"},
        )

    @pytest.mark.asyncio
    async def test_like_post_auth_expired(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=make_response(401))

        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="190215624", type="post")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_like_post_server_error(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=make_response(500))

        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="190215624", type="post")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"
        assert "500" in result["message"]


class TestLikeNote:
    """Test liking a note (POST /api/v1/comment/{id}/reaction)."""

    @pytest.mark.asyncio
    async def test_like_note_success(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=make_response(200, {}))

        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="224486083", type="note")

        assert result["success"] is True
        assert result["id"] == "224486083"
        assert result["type"] == "note"
        mock_client.post.assert_called_once_with(
            "/api/v1/comment/224486083/reaction",
            json={"publication_id": None, "reaction": "❤", "tabId": "for-you"},
        )

    @pytest.mark.asyncio
    async def test_like_note_auth_expired(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=make_response(401))

        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="224486083", type="note")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestLikeEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_no_cookie_configured(self):
        from src.tools.like import like_content

        with patch("src.tools.like.get_client", return_value=None):
            result = await like_content(id="123", type="post")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
        assert "cookie" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_invalid_type(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="123", type="invalid")

        assert result["error"] is True
        assert result["code"] == "VALIDATION"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_network_error(self):
        from src.tools.like import like_content

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("src.tools.react.get_client", return_value=mock_client):
            result = await like_content(id="123", type="post")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"
        assert "Connection refused" in result["message"]
