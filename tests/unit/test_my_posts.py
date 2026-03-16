import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_MY_POSTS_RESPONSE = [
    {
        "id": 7001,
        "title": "My First Article",
        "slug": "my-first-article",
        "post_date": "2026-03-10T10:00:00.000Z",
        "canonical_url": "https://joinveri.substack.com/p/my-first-article",
        "subtitle": "A subtitle here",
        "wordcount": 1500,
        "audience": "everyone",
        "type": "newsletter",
    },
    {
        "id": 7002,
        "title": "My Second Article",
        "slug": "my-second-article",
        "post_date": "2026-03-08T08:00:00.000Z",
        "canonical_url": "https://joinveri.substack.com/p/my-second-article",
        "subtitle": "",
        "wordcount": 2200,
        "audience": "only_paid",
        "type": "newsletter",
    },
]

SUBDOMAIN_PATCH = patch("src.tools.my_posts.PUBLICATION_SUBDOMAIN", "joinveri")


class TestMyPostsBasic:
    """Test basic my posts functionality."""

    @pytest.mark.asyncio
    async def test_returns_published_posts(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            200,
            json=MOCK_MY_POSTS_RESPONSE,
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            result = await get_my_posts()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["title"] == "My First Article"

    @pytest.mark.asyncio
    async def test_article_has_required_fields(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            200,
            json=MOCK_MY_POSTS_RESPONSE,
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            result = await get_my_posts()

        article = result[0]
        assert "id" in article
        assert "title" in article
        assert "slug" in article
        assert "url" in article
        assert "published_at" in article
        assert article["platform"] == "substack"
        assert article["source_feed"] == "my_posts"

    @pytest.mark.asyncio
    async def test_limit_caps_results(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            200,
            json=MOCK_MY_POSTS_RESPONSE,
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            result = await get_my_posts(limit=1)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_passes_params_to_fetch(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            200,
            json=[],
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response) as mock_fetch, \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            await get_my_posts(limit=5, offset=10, order_direction="asc")

        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args
        assert call_kwargs[1]["params"]["limit"] == 5
        assert call_kwargs[1]["params"]["offset"] == 10
        assert call_kwargs[1]["params"]["order_direction"] == "asc"


class TestMyPostsErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_no_subdomain_returns_error(self):
        from src.tools.my_posts import get_my_posts

        with patch("src.tools.my_posts.PUBLICATION_SUBDOMAIN", None):
            result = await get_my_posts()

        assert result["error"] is True
        assert result["code"] == "CONFIG_ERROR"

    @pytest.mark.asyncio
    async def test_no_cookie_returns_error(self):
        from src.tools.my_posts import get_my_posts

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.get_cookie", return_value=None):
            result = await get_my_posts()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_401_returns_auth_expired(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            401, json={},
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            result = await get_my_posts()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            500, json={},
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            result = await get_my_posts()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self):
        from src.tools.my_posts import get_my_posts

        mock_response = httpx.Response(
            200, json=[],
            request=httpx.Request("GET", "https://joinveri.substack.com/api/v1/post_management/published"),
        )

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.fetch_my_posts", new_callable=AsyncMock, return_value=mock_response), \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):

            result = await get_my_posts()

        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_order_direction_returns_error(self):
        from src.tools.my_posts import get_my_posts

        with SUBDOMAIN_PATCH, \
             patch("src.tools.my_posts.get_cookie", return_value="test_cookie"):
            result = await get_my_posts(order_direction="invalid")

        assert result["error"] is True
        assert result["code"] == "INVALID_PARAM"
