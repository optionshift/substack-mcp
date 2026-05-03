import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="GET", url="https://x.substack.com/api/v1/drafts"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, url),
    )


class TestListDrafts:
    @pytest.mark.asyncio
    async def test_list_success(self):
        from src.tools.drafts import list_drafts

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(
                    data={"drafts": [{"id": 1, "title": "T1"}], "hasMore": False}
                )
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await list_drafts(limit=20)

        assert result["drafts"][0]["title"] == "T1"

    @pytest.mark.asyncio
    async def test_list_no_publication(self):
        from src.tools.drafts import list_drafts

        with patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value=None)):
            result = await list_drafts(limit=20)

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_list_no_client(self):
        from src.tools.drafts import list_drafts

        with patch("src.tools.drafts.get_client", return_value=None), \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            result = await list_drafts(limit=20)

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_list_401(self):
        from src.tools.drafts import list_drafts

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(status=401)
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await list_drafts()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestGetDraft:
    @pytest.mark.asyncio
    async def test_get_success(self):
        from src.tools.drafts import get_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(data={"id": 42, "title": "T"})
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await get_draft(draft_id="42")

        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_get_non_200(self):
        from src.tools.drafts import get_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(status=404)
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await get_draft(draft_id="42")

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"


class TestDeleteDraft:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        from src.tools.drafts import delete_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(method="DELETE")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await delete_draft(draft_id="42")

        assert result["success"] is True
        assert result["draft_id"] == "42"
        assert result["action"] == "deleted"
