import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://substack.com/api/v1/feed/44606/follow"),
    )


class TestFollow:
    @pytest.mark.asyncio
    async def test_follow_success(self):
        from src.tools.follow import follow_user

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await follow_user(user_id="44606")

        assert result["success"] is True
        mock_client.post.assert_called_once_with(
            "/api/v1/feed/44606/follow", json={"surface": "profile"}
        )

    @pytest.mark.asyncio
    async def test_follow_invalid_id(self):
        from src.tools.follow import follow_user
        result = await follow_user(user_id="not-numeric")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_follow_missing_cookie(self):
        from src.tools.follow import follow_user

        with patch("src.tools.follow.get_client", return_value=None):
            result = await follow_user(user_id="44606")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_follow_401(self):
        from src.tools.follow import follow_user

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await follow_user(user_id="44606")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestUnfollow:
    @pytest.mark.asyncio
    async def test_unfollow_success(self):
        from src.tools.follow import unfollow_user

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(method="DELETE")
            mock_gc.return_value = mock_client

            result = await unfollow_user(user_id="44606")

        assert result["success"] is True
        mock_client.delete.assert_called_once_with(
            "/api/v1/feed/44606/follow", json={"surface": "profile"}
        )

    @pytest.mark.asyncio
    async def test_unfollow_invalid_id(self):
        from src.tools.follow import unfollow_user
        result = await unfollow_user(user_id="not-numeric")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_unfollow_401(self):
        from src.tools.follow import unfollow_user

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(status=401, method="DELETE")
            mock_gc.return_value = mock_client

            result = await unfollow_user(user_id="44606")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestListFollowing:
    @pytest.mark.asyncio
    async def test_list(self):
        from src.tools.follow import list_following

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(data=[1, 2, 3], method="GET")
            mock_gc.return_value = mock_client

            result = await list_following()

        assert result == {"user_ids": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_list_missing_cookie(self):
        from src.tools.follow import list_following

        with patch("src.tools.follow.get_client", return_value=None):
            result = await list_following()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
