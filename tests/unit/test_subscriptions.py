import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_SUBSCRIPTIONS_RESPONSE = {
    "subscriptions": [
        {
            "id": 1001,
            "user_id": 383926424,
            "publication_id": 100,
            "membership_state": "free_signup",
        },
        {
            "id": 1002,
            "user_id": 383926424,
            "publication_id": 200,
            "membership_state": "free_signup",
        },
    ],
    "publications": [
        {
            "id": 100,
            "name": "Test Publication",
            "subdomain": "testpub",
            "custom_domain": None,
            "author_name": "Author One",
            "description": "A test publication",
        },
        {
            "id": 200,
            "name": "Another Blog",
            "subdomain": "anotherblog",
            "custom_domain": "blog.example.com",
            "author_name": "Author Two",
            "description": "Another blog",
        },
    ],
}


class TestGetSubscriptions:
    """Test ss_get_subscriptions tool."""

    @pytest.mark.asyncio
    async def test_returns_valid_subscription_list(self):
        from src.tools.subscriptions import get_subscriptions

        mock_response = httpx.Response(
            200,
            json=MOCK_SUBSCRIPTIONS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/subscriptions"),
        )

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_subscription_has_required_fields(self):
        from src.tools.subscriptions import get_subscriptions

        mock_response = httpx.Response(
            200,
            json=MOCK_SUBSCRIPTIONS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/subscriptions"),
        )

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        sub = result[0]
        assert "name" in sub
        assert "subdomain" in sub
        assert "url" in sub
        assert "rss_url" in sub
        assert "author" in sub
        assert "description" in sub

    @pytest.mark.asyncio
    async def test_subscription_url_format(self):
        from src.tools.subscriptions import get_subscriptions

        mock_response = httpx.Response(
            200,
            json=MOCK_SUBSCRIPTIONS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/subscriptions"),
        )

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        assert result[0]["url"] == "https://testpub.substack.com"
        assert result[0]["rss_url"] == "https://testpub.substack.com/feed"

    @pytest.mark.asyncio
    async def test_handles_empty_list(self):
        from src.tools.subscriptions import get_subscriptions

        mock_response = httpx.Response(
            200,
            json={"subscriptions": [], "publications": []},
            request=httpx.Request("GET", "https://substack.com/api/v1/subscriptions"),
        )

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        assert result == []

    @pytest.mark.asyncio
    async def test_auth_failure_returns_error(self):
        from src.tools.subscriptions import get_subscriptions

        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://substack.com/api/v1/subscriptions"),
        )

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_error(self):
        from src.tools.subscriptions import get_subscriptions

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_get_client.return_value = None

            result = await get_subscriptions()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.subscriptions import get_subscriptions

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_custom_domain_url_uses_custom_domain(self):
        from src.tools.subscriptions import get_subscriptions

        mock_response = httpx.Response(
            200,
            json=MOCK_SUBSCRIPTIONS_RESPONSE,
            request=httpx.Request("GET", "https://substack.com/api/v1/subscriptions"),
        )

        with patch("src.tools.subscriptions.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await get_subscriptions()

        assert result[1]["url"] == "https://blog.example.com"
        # RSS always uses subdomain (RSS is auth-free, works on substack.com domain)
        assert result[1]["rss_url"] == "https://anotherblog.substack.com/feed"


class TestRateLimiting:
    """Test rate limiting in SubstackClient."""

    @pytest.mark.asyncio
    async def test_rate_limiting_enforces_delay(self):
        import time
        from src.substack_client import SubstackClient

        client = SubstackClient(session_cookie="test")
        client._last_request_time = time.monotonic()

        with patch("src.substack_client.httpx.AsyncClient") as mock_class:
            mock_http = AsyncMock()
            mock_response = httpx.Response(
                200,
                json={},
                request=httpx.Request("GET", "https://substack.com/test"),
            )
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_class.return_value = mock_http

            with patch("src.substack_client.asyncio.sleep") as mock_sleep:
                await client.get("/test")
                mock_sleep.assert_called_once()
