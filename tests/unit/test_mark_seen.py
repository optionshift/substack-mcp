import pytest
from unittest.mock import patch, AsyncMock
import httpx


class TestMarkSeenPost:
    """Test marking posts as seen."""

    @pytest.mark.asyncio
    async def test_post_mark_seen_succeeds(self):
        from src.tools.mark_seen import mark_seen

        mock_response = httpx.Response(
            200, json={},
            request=httpx.Request("POST", "https://substack.com/api/v1/reader/feed/p-12345/seen"),
        )

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await mark_seen(id="12345", type="post")

        assert result["success"] is True
        assert result["id"] == "12345"
        assert result["type"] == "post"

    @pytest.mark.asyncio
    async def test_post_calls_correct_endpoint(self):
        from src.tools.mark_seen import mark_seen

        mock_response = httpx.Response(
            200, json={},
            request=httpx.Request("POST", "https://substack.com/api/v1/reader/feed/p-12345/seen"),
        )

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_gc.return_value = mock_client

            await mark_seen(id="12345", type="post")

        call_args = mock_client.post.call_args[0][0]
        assert call_args == "/api/v1/reader/feed/p-12345/seen"


class TestMarkSeenNote:
    """Test marking notes as seen."""

    @pytest.mark.asyncio
    async def test_note_mark_seen_succeeds(self):
        from src.tools.mark_seen import mark_seen

        mock_response = httpx.Response(
            200, json={},
            request=httpx.Request("POST", "https://substack.com/api/v1/reader/feed/c-99999/seen"),
        )

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await mark_seen(id="99999", type="note")

        assert result["success"] is True
        assert result["type"] == "note"

    @pytest.mark.asyncio
    async def test_note_calls_correct_endpoint(self):
        from src.tools.mark_seen import mark_seen

        mock_response = httpx.Response(
            200, json={},
            request=httpx.Request("POST", "https://substack.com/api/v1/reader/feed/c-99999/seen"),
        )

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_gc.return_value = mock_client

            await mark_seen(id="99999", type="note")

        call_args = mock_client.post.call_args[0][0]
        assert call_args == "/api/v1/reader/feed/c-99999/seen"


class TestMarkSeenErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_invalid_type_returns_error(self):
        from src.tools.mark_seen import mark_seen

        result = await mark_seen(id="12345", type="invalid")

        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_no_cookie_returns_error(self):
        from src.tools.mark_seen import mark_seen

        with patch("src.tools.mark_seen.get_client", return_value=None):
            result = await mark_seen(id="12345", type="post")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_401_returns_auth_expired(self):
        from src.tools.mark_seen import mark_seen

        mock_response = httpx.Response(
            401, json={},
            request=httpx.Request("POST", "https://substack.com/api/v1/reader/feed/p-12345/seen"),
        )

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await mark_seen(id="12345", type="post")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.mark_seen import mark_seen

        mock_response = httpx.Response(
            500, json={},
            request=httpx.Request("POST", "https://substack.com/api/v1/reader/feed/p-12345/seen"),
        )

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_gc.return_value = mock_client

            result = await mark_seen(id="12345", type="post")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.mark_seen import mark_seen

        with patch("src.tools.mark_seen.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection failed")
            mock_gc.return_value = mock_client

            result = await mark_seen(id="12345", type="post")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"
