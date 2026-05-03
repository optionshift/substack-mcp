import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request("DELETE", "https://substack.com/api/v1/comment/123"),
    )


class TestDeleteContent:
    @pytest.mark.asyncio
    async def test_delete_note_uses_substack_root(self):
        from src.tools.delete_content import delete_content

        with patch("src.tools.delete_content.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await delete_content(target_id="252827081", kind="note")

        assert result["success"] is True
        # delete called against substack.com root via SubstackClient.delete (which uses base_url)
        mock_client.delete.assert_called_once_with("/api/v1/comment/252827081")

    @pytest.mark.asyncio
    async def test_delete_post_comment_uses_publication(self):
        from src.tools.delete_content import delete_content

        with patch("src.tools.delete_content.get_client") as mock_gc, \
             patch("src.tools.delete_content.resolve_publication_subdomain", new=AsyncMock(return_value=("lenny", None))):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "x"}
            mock_gc.return_value = mock_client

            with patch("src.tools.delete_content.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_resp = _make_response()
                mock_http.delete.return_value = mock_resp
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await delete_content(target_id="50", kind="post_comment", post_id="123")

        assert result["success"] is True
        called_url = mock_http.delete.call_args.args[0]
        assert "lenny.substack.com" in called_url
        assert "/comment/50" in called_url

    @pytest.mark.asyncio
    async def test_delete_post_comment_requires_post_id(self):
        from src.tools.delete_content import delete_content

        with patch("src.tools.delete_content.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client
            result = await delete_content(target_id="50", kind="post_comment")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_delete_invalid_kind(self):
        from src.tools.delete_content import delete_content

        result = await delete_content(target_id="50", kind="bogus")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
