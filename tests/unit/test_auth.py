import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


MOCK_USER_PROFILE = {
    "id": 12345,
    "name": "Test User",
    "email": "test@example.com",
    "photo_url": "https://example.com/photo.jpg",
}


class TestSubstackClient:
    """Test base Substack API client."""

    def test_client_requires_cookie(self):
        from src.substack_client import SubstackClient
        with pytest.raises(ValueError):
            SubstackClient(session_cookie=None)

    def test_client_sets_session_cookie(self):
        from src.substack_client import SubstackClient
        client = SubstackClient(session_cookie="test_cookie_value")
        cookies = client.get_cookies()
        assert "substack.sid" in cookies
        assert cookies["substack.sid"] == "test_cookie_value"
        assert "connect.sid" not in cookies

    def test_client_stores_cookie(self):
        from src.substack_client import SubstackClient
        client = SubstackClient(session_cookie="abc123")
        assert client.session_cookie == "abc123"


class TestAuthCheck:
    """Test ss_auth_check tool."""

    @pytest.mark.asyncio
    async def test_valid_cookie_returns_profile(self):
        from src.tools.auth import auth_check

        mock_response = httpx.Response(
            200,
            json=MOCK_USER_PROFILE,
            request=httpx.Request("GET", "https://substack.com/api/v1/user/profile/self"),
        )

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await auth_check()

        assert result["valid"] is True
        assert result["user_id"] == "12345"
        assert result["name"] == "Test User"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_expired_cookie_returns_auth_expired(self):
        from src.tools.auth import auth_check

        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://substack.com/api/v1/user/profile/self"),
        )

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await auth_check()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_auth_expired(self):
        from src.tools.auth import auth_check

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_get_client.return_value = None

            result = await auth_check()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
        assert "missing" in result["message"].lower() or "not configured" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.auth import auth_check

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_get_client.return_value = mock_client

            result = await auth_check()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_user_id_cached_after_success(self):
        from src.tools.auth import auth_check, get_cached_user_id, _clear_cache

        _clear_cache()

        mock_response = httpx.Response(
            200,
            json=MOCK_USER_PROFILE,
            request=httpx.Request("GET", "https://substack.com/api/v1/user/profile/self"),
        )

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            await auth_check()

        assert get_cached_user_id() == "12345"

    @pytest.mark.asyncio
    async def test_error_response_has_standard_shape(self):
        from src.tools.auth import auth_check

        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://substack.com/api/v1/user/profile/self"),
        )

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await auth_check()

        assert "error" in result
        assert "code" in result
        assert "message" in result
        assert "retry_after" in result

    @pytest.mark.asyncio
    async def test_success_response_has_required_fields(self):
        from src.tools.auth import auth_check

        mock_response = httpx.Response(
            200,
            json=MOCK_USER_PROFILE,
            request=httpx.Request("GET", "https://substack.com/api/v1/user/profile/self"),
        )

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await auth_check()

        assert "valid" in result
        assert "user_id" in result
        assert "name" in result
        assert "email" in result
        assert "expires_warning" in result

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.auth import auth_check

        mock_response = httpx.Response(
            500,
            json={"error": "internal server error"},
            request=httpx.Request("GET", "https://substack.com/api/v1/user/profile/self"),
        )

        with patch("src.tools.auth.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await auth_check()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"
        assert "500" in result["message"]


class TestCreateClient:
    """Test create_client env var wiring."""

    def test_create_client_with_env_var(self):
        from src.substack_client import create_client
        with patch.dict("os.environ", {"SUBSTACK_SESSION_COOKIE": "test_value"}):
            client = create_client()
        assert client is not None
        assert client.session_cookie == "test_value"

    def test_create_client_without_env_var(self):
        from src.substack_client import create_client
        import os
        env = os.environ.copy()
        env.pop("SUBSTACK_SESSION_COOKIE", None)
        with patch.dict("os.environ", env, clear=True):
            client = create_client()
        assert client is None
