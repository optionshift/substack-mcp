import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request("POST", "https://substack.com/api/v1/post/123/reaction"),
    )


class TestReact:
    @pytest.mark.asyncio
    async def test_react_post_default_heart(self):
        from src.tools.react import react

        with patch("src.tools.react.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await react(target_id="123", kind="post")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["reaction"] == "❤"
        assert mock_client.post.call_args.args[0] == "/api/v1/post/123/reaction"

    @pytest.mark.asyncio
    async def test_react_note_thumbs_up(self):
        from src.tools.react import react

        with patch("src.tools.react.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await react(target_id="999", kind="note", emoji="👍")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["reaction"] == "👍"
        assert mock_client.post.call_args.args[0] == "/api/v1/comment/999/reaction"

    @pytest.mark.asyncio
    async def test_react_invalid_kind(self):
        from src.tools.react import react

        result = await react(target_id="1", kind="bogus")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_like_alias_still_works(self):
        from src.tools.like import like_content

        with patch("src.tools.react.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await like_content(id="123", type="post")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["reaction"] == "❤"
