import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://example.substack.com/api/v1/post/123/comment"),
    )


class TestCommentOnPost:
    @pytest.mark.asyncio
    async def test_comment_success(self):
        from src.tools.comment_on_post import comment_on_post

        with patch("src.tools.comment_on_post.get_client") as mock_gc, \
             patch("src.tools.comment_on_post.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "x"}
            mock_gc.return_value = mock_client

            with patch("src.tools.comment_on_post.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.post.return_value = _make_response(data={"id": 99, "body": "great post"})
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await comment_on_post(post_id="191270969", text="great post")

        assert result["success"] is True
        assert result["id"] == 99
        # Endpoint must include the resolved subdomain
        called_url = mock_http.post.call_args.args[0]
        assert "lenny.substack.com" in called_url

    @pytest.mark.asyncio
    async def test_comment_voice_blocks(self):
        from src.tools.comment_on_post import comment_on_post

        with patch("src.tools.comment_on_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            result = await comment_on_post(post_id="123", text="we leverage synergy")

        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_comment_with_parent_id(self):
        from src.tools.comment_on_post import comment_on_post

        with patch("src.tools.comment_on_post.get_client") as mock_gc, \
             patch("src.tools.comment_on_post.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "x"}
            mock_gc.return_value = mock_client

            with patch("src.tools.comment_on_post.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.post.return_value = _make_response(data={"id": 100})
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                await comment_on_post(post_id="123", text="thanks for clarifying", parent_id="55")

        body = mock_http.post.call_args.kwargs["json"]
        assert body["parent_id"] == 55

    @pytest.mark.asyncio
    async def test_get_post_comments(self):
        from src.tools.comment_on_post import get_post_comments

        with patch("src.tools.comment_on_post.get_client") as mock_gc, \
             patch("src.tools.comment_on_post.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "x"}
            mock_gc.return_value = mock_client

            with patch("src.tools.comment_on_post.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = _make_response(
                    data={"comments": [{"id": 1, "body": "x"}]},
                    method="GET",
                )
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await get_post_comments(post_id="123")

        assert "comments" in result
        assert len(result["comments"]) == 1
