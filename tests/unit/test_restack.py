import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://substack.com/api/v1/restack/feed"),
    )


class TestRestack:
    @pytest.mark.asyncio
    async def test_restack_post_success(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(target_id="191270969", kind="post")

        assert result["success"] is True
        mock_client.post.assert_called_once()
        call = mock_client.post.call_args
        assert call.args[0] == "/api/v1/restack/feed"
        assert call.kwargs["json"]["postId"] == 191270969
        assert call.kwargs["json"]["commentId"] is None

    @pytest.mark.asyncio
    async def test_restack_note_success(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(target_id="252827081", kind="note")

        body = mock_client.post.call_args.kwargs["json"]
        assert body["commentId"] == 252827081
        assert body["postId"] is None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_restack_invalid_kind(self):
        from src.tools.restack import restack_content

        result = await restack_content(target_id="123", kind="bogus")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_restack_with_quote_voice_blocks(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            result = await restack_content(
                target_id="123", kind="post",
                quote_text="we leverage this revolutionary tool",
            )
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_restack_with_quote_force_bypasses(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            # First call: comment/feed (the quote note); second: restack/feed
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(
                target_id="123", kind="post",
                quote_text="we leverage this", force=True,
            )
        assert result["success"] is True
        # Two POSTs: comment/feed for quote, restack/feed for restack
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_restack_with_clean_quote(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(
                target_id="191270969", kind="post",
                quote_text="this changed how i think about distribution",
            )

        assert result["success"] is True
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_unrestack_post(self):
        from src.tools.restack import unrestack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(method="DELETE")
            mock_gc.return_value = mock_client

            result = await unrestack_content(target_id="191270969", kind="post")

        assert result["success"] is True
        mock_client.delete.assert_called_once()
        body = mock_client.delete.call_args.kwargs["json"]
        assert body["postId"] == 191270969

    @pytest.mark.asyncio
    async def test_restack_401(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await restack_content(target_id="123", kind="post")
        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
