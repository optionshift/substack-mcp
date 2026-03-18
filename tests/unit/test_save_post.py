import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request("POST", "https://substack.com/api/v1/posts/saved"),
    )


def _make_delete_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request("DELETE", "https://substack.com/api/v1/posts/saved"),
    )


class TestSavePost:
    """Tests for ss_save_post tool."""

    @pytest.mark.asyncio
    async def test_save_success(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await save_post(post_id="191270969")

        assert result["success"] is True
        assert result["post_id"] == "191270969"
        assert result["action"] == "saved"

    @pytest.mark.asyncio
    async def test_save_calls_correct_endpoint(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            await save_post(post_id="191270969")

        mock_client.post.assert_called_once_with(
            "/api/v1/posts/saved",
            json={"post_id": 191270969},
        )

    @pytest.mark.asyncio
    async def test_save_missing_cookie(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client", return_value=None):
            result = await save_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_save_401(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await save_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_save_server_error(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=500)
            mock_gc.return_value = mock_client

            result = await save_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_save_network_error(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_gc.return_value = mock_client

            result = await save_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_save_invalid_post_id(self):
        from src.tools.save_post import save_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_gc.return_value = AsyncMock()
            result = await save_post(post_id="not-a-number")

        assert result["error"] is True
        assert result["code"] == "VALIDATION"


class TestUnsavePost:
    """Tests for ss_unsave_post tool."""

    @pytest.mark.asyncio
    async def test_unsave_success(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_delete_response()
            mock_gc.return_value = mock_client

            result = await unsave_post(post_id="191270969")

        assert result["success"] is True
        assert result["post_id"] == "191270969"
        assert result["action"] == "unsaved"

    @pytest.mark.asyncio
    async def test_unsave_calls_correct_endpoint(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_delete_response()
            mock_gc.return_value = mock_client

            await unsave_post(post_id="191270969")

        mock_client.delete.assert_called_once_with(
            "/api/v1/posts/saved",
            json={"post_id": 191270969},
        )

    @pytest.mark.asyncio
    async def test_unsave_missing_cookie(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client", return_value=None):
            result = await unsave_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_unsave_401(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_delete_response(status=401)
            mock_gc.return_value = mock_client

            result = await unsave_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_unsave_server_error(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_delete_response(status=500)
            mock_gc.return_value = mock_client

            result = await unsave_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_unsave_network_error(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.side_effect = Exception("Timeout")
            mock_gc.return_value = mock_client

            result = await unsave_post(post_id="123")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_unsave_invalid_post_id(self):
        from src.tools.save_post import unsave_post

        with patch("src.tools.save_post.get_client") as mock_gc:
            mock_gc.return_value = AsyncMock()
            result = await unsave_post(post_id="abc")

        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_save_empty_string_post_id(self):
        from src.tools.save_post import save_post

        result = await save_post(post_id="")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_unsave_empty_string_post_id(self):
        from src.tools.save_post import unsave_post

        result = await unsave_post(post_id="")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
