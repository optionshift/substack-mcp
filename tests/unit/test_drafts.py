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


class TestCreateDraft:
    @pytest.mark.asyncio
    async def test_create_voice_blocks(self):
        from src.tools.drafts import create_draft

        result = await create_draft(title="ok", body_markdown="we leverage synergy")
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"

    @pytest.mark.asyncio
    async def test_create_force_bypasses(self):
        from src.tools.drafts import create_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(
                    data={"id": 99}, method="POST"
                )
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await create_draft(
                    title="t", body_markdown="we leverage", force=True,
                )
        assert result["success"] is True
        assert result["id"] == 99

    @pytest.mark.asyncio
    async def test_create_clean_text_succeeds(self):
        from src.tools.drafts import create_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(
                    data={"id": 7}, method="POST"
                )
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await create_draft(
                    title="hello world",
                    body_markdown="first paragraph.\n\nsecond paragraph.",
                    subtitle="a clean subtitle",
                )

        assert result["success"] is True
        assert result["id"] == 7

    @pytest.mark.asyncio
    async def test_create_voice_checks_subtitle(self):
        from src.tools.drafts import create_draft

        result = await create_draft(
            title="ok",
            body_markdown="clean body",
            subtitle="we leverage synergy",
        )
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"


class TestUpdateDraft:
    @pytest.mark.asyncio
    async def test_update_title_only(self):
        from src.tools.drafts import update_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(method="PUT")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await update_draft(draft_id="42", fields={"title": "new"})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_body_voice_blocks(self):
        from src.tools.drafts import update_draft

        result = await update_draft(
            draft_id="42",
            fields={"body_markdown": "we leverage synergy"},
        )
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"

    @pytest.mark.asyncio
    async def test_update_unsupported_field(self):
        from src.tools.drafts import update_draft

        result = await update_draft(
            draft_id="42",
            fields={"some_random_field": "x"},
        )
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_update_body_force_bypasses(self):
        from src.tools.drafts import update_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(method="PUT")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await update_draft(
                    draft_id="42",
                    fields={"body_markdown": "we leverage"},
                    force=True,
                )
        assert result["success"] is True
        assert result["draft_id"] == "42"


class TestPublishDraft:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        from src.tools.drafts import publish_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(data={"id": 42}, method="POST")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await publish_draft(draft_id="42")
        assert result["success"] is True
        assert result["draft_id"] == "42"

    @pytest.mark.asyncio
    async def test_publish_no_publication(self):
        from src.tools.drafts import publish_draft

        with patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value=None)):
            result = await publish_draft(draft_id="42")
        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"


class TestSchedulePost:
    @pytest.mark.asyncio
    async def test_schedule_success(self):
        from src.tools.drafts import schedule_post

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(method="POST")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await schedule_post(draft_id="42", post_date_iso="2026-06-01T15:00:00Z")
        assert result["success"] is True
        assert result["scheduled_for"] == "2026-06-01T15:00:00Z"

    @pytest.mark.asyncio
    async def test_unschedule(self):
        from src.tools.drafts import unschedule_post

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get_cookies.return_value = {"substack.sid": "abc"}
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.request.return_value = _make_response(method="POST")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await unschedule_post(draft_id="42")
        assert result["success"] is True
        assert result["action"] == "unscheduled"


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
