import base64
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {"url": "https://substackcdn.com/abc.jpg"},
        request=httpx.Request("POST", "https://substack.com/api/v1/image"),
    )


class TestUploadImage:
    @pytest.mark.asyncio
    async def test_upload_with_base64(self):
        from src.tools.upload_image import upload_image

        b64 = base64.b64encode(b"fake image bytes").decode()
        data_uri = f"data:image/jpeg;base64,{b64}"

        with patch("src.tools.upload_image.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await upload_image(image_data=data_uri)

        assert result["success"] is True
        assert result["url"] == "https://substackcdn.com/abc.jpg"

    @pytest.mark.asyncio
    async def test_upload_invalid_format(self):
        from src.tools.upload_image import upload_image

        result = await upload_image(image_data="not-a-data-uri")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
