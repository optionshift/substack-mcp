import pytest
from unittest.mock import patch, AsyncMock
import httpx


MOCK_ACTIVITY_RESPONSE = {
    "activityItems": [
        {
            "id": "note_like:214184522",
            "user_id": 383926424,
            "item_key": "note_like:214184522",
            "type": "note_like",
            "created_at": "2026-02-27T17:35:03.565Z",
            "updated_at": "2026-03-08T21:48:39.019Z",
            "sender_count": 2,
            "recent_sender_ids": [134689899, 255841],
            "publication_id": None,
            "target_post_id": None,
            "target_comment_id": 214184522,
            "comment_id": None,
            "isNew": True,
            "rank": 1773007547123,
        },
        {
            "id": "post_like:190215624",
            "user_id": 383926424,
            "item_key": "post_like:190215624",
            "type": "post_like",
            "created_at": "2026-03-06T10:00:00Z",
            "updated_at": "2026-03-08T12:00:00Z",
            "sender_count": 1,
            "recent_sender_ids": [59518773],
            "publication_id": 12345,
            "target_post_id": 190215624,
            "target_comment_id": None,
            "comment_id": None,
            "isNew": False,
            "rank": 1773007500000,
        },
        {
            "id": "restack:190215624",
            "user_id": 383926424,
            "item_key": "restack:190215624",
            "type": "restack",
            "created_at": "2026-03-05T08:00:00Z",
            "updated_at": "2026-03-07T15:00:00Z",
            "sender_count": 1,
            "recent_sender_ids": [134689899],
            "publication_id": 12345,
            "target_post_id": 190215624,
            "target_comment_id": None,
            "comment_id": None,
            "isNew": True,
            "rank": 1773007400000,
        },
    ],
    "users": [
        {
            "id": 134689899,
            "name": "Alice Builder",
            "handle": "alicebuilder",
            "photo_url": "https://example.com/alice.jpg",
            "bio": "Building things",
            "is_following": False,
            "can_dm": True,
        },
        {
            "id": 255841,
            "name": "Aryn Foland",
            "handle": "arynfoland",
            "photo_url": "https://example.com/aryn.jpg",
            "bio": None,
            "is_following": True,
            "can_dm": True,
        },
        {
            "id": 59518773,
            "name": "Bob Writer",
            "handle": "bobwriter",
            "photo_url": "https://example.com/bob.jpg",
            "bio": "Writing stuff",
            "is_following": False,
            "can_dm": False,
        },
    ],
    "posts": [
        {
            "id": 190215624,
            "title": "My Great Article",
            "slug": "my-great-article",
            "canonical_url": "https://miles.substack.com/p/my-great-article",
            "post_date": "2026-03-01T10:00:00Z",
        },
    ],
    "comments": [
        {
            "id": 214184522,
            "body": "This is my note content here",
            "date": "2026-02-27T17:00:00Z",
            "name": "Miles Lozano",
        },
    ],
    "pubs": [
        {
            "id": 12345,
            "name": "Miles's Newsletter",
            "subdomain": "miles",
        },
    ],
    "more": True,
    "filter": "all",
}

MOCK_RESTACKS_RESPONSE = {
    "activityItems": [
        {
            "id": "restack:190215624",
            "user_id": 383926424,
            "item_key": "restack:190215624",
            "type": "restack",
            "created_at": "2026-03-05T08:00:00Z",
            "updated_at": "2026-03-07T15:00:00Z",
            "sender_count": 1,
            "recent_sender_ids": [134689899],
            "publication_id": 12345,
            "target_post_id": 190215624,
            "target_comment_id": None,
            "comment_id": None,
            "isNew": True,
            "rank": 1773007400000,
        },
    ],
    "users": [
        {
            "id": 134689899,
            "name": "Alice Builder",
            "handle": "alicebuilder",
            "photo_url": "https://example.com/alice.jpg",
            "bio": "Building things",
            "is_following": False,
            "can_dm": True,
        },
    ],
    "posts": [
        {
            "id": 190215624,
            "title": "My Great Article",
            "slug": "my-great-article",
            "canonical_url": "https://miles.substack.com/p/my-great-article",
            "post_date": "2026-03-01T10:00:00Z",
        },
    ],
    "comments": [],
    "pubs": [
        {
            "id": 12345,
            "name": "Miles's Newsletter",
            "subdomain": "miles",
        },
    ],
    "more": False,
    "filter": "restacks",
}

MOCK_REPLIES_RESPONSE = {
    "activityItems": [
        {
            "id": "note_reply:224950341",
            "user_id": 383926424,
            "item_key": "note_reply:224950341",
            "type": "note_reply",
            "created_at": "2026-03-08T10:00:00Z",
            "updated_at": "2026-03-08T10:00:00Z",
            "sender_count": 1,
            "recent_sender_ids": [255841],
            "publication_id": None,
            "target_post_id": None,
            "target_comment_id": 214184522,
            "comment_id": 224950341,
            "isNew": True,
            "rank": 1773007600000,
        },
    ],
    "users": [
        {
            "id": 255841,
            "name": "Aryn Foland",
            "handle": "arynfoland",
            "photo_url": "https://example.com/aryn.jpg",
            "bio": None,
            "is_following": True,
            "can_dm": True,
        },
    ],
    "posts": [],
    "comments": [
        {
            "id": 214184522,
            "body": "Original note",
            "date": "2026-02-27T17:00:00Z",
            "name": "Miles Lozano",
        },
        {
            "id": 224950341,
            "body": "Great note, Miles!",
            "date": "2026-03-08T10:00:00Z",
            "name": "Aryn Foland",
        },
    ],
    "pubs": [],
    "more": False,
    "filter": "replies-and-mentions",
}


def _make_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json_data,
        request=httpx.Request("GET", "https://substack.com/api/v1/activity-feed-web"),
    )


class TestActivityFeedAll:
    """Test activity feed with filter=all."""

    @pytest.mark.asyncio
    async def test_returns_all_activities(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all")

        assert "activities" in result
        assert len(result["activities"]) == 3
        assert result["filter"] == "all"
        assert result["has_more"] is True

    @pytest.mark.asyncio
    async def test_enriches_senders_from_users(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all")

        note_like = result["activities"][0]
        assert note_like["type"] == "note_like"
        assert len(note_like["senders"]) == 2
        assert note_like["senders"][0]["name"] == "Alice Builder"
        assert note_like["senders"][0]["handle"] == "alicebuilder"
        assert note_like["senders"][1]["name"] == "Aryn Foland"

    @pytest.mark.asyncio
    async def test_enriches_target_post(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all")

        post_like = result["activities"][1]
        assert post_like["type"] == "post_like"
        assert post_like["target_post"] is not None
        assert post_like["target_post"]["title"] == "My Great Article"
        assert post_like["target_post"]["url"] == "https://miles.substack.com/p/my-great-article"

    @pytest.mark.asyncio
    async def test_enriches_target_comment(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all")

        note_like = result["activities"][0]
        assert note_like["target_comment"] is not None
        assert note_like["target_comment"]["body"] == "This is my note content here"

    @pytest.mark.asyncio
    async def test_enriches_publication(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all")

        post_like = result["activities"][1]
        assert post_like["publication"] is not None
        assert post_like["publication"]["name"] == "Miles's Newsletter"

    @pytest.mark.asyncio
    async def test_limit_caps_results(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all", limit=2)

        assert len(result["activities"]) == 2


class TestActivityFeedFilters:
    """Test specific filter values."""

    @pytest.mark.asyncio
    async def test_restacks_filter(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_RESTACKS_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="restacks")

        assert result["filter"] == "restacks"
        assert len(result["activities"]) == 1
        assert result["activities"][0]["type"] == "restack"
        assert result["has_more"] is False

        mock_client.get.assert_called_once_with(
            "/api/v1/activity-feed-web",
            params={"filter": "restacks"},
        )

    @pytest.mark.asyncio
    async def test_replies_and_mentions_filter(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_REPLIES_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="replies-and-mentions")

        assert result["filter"] == "replies-and-mentions"
        assert len(result["activities"]) == 1
        assert result["activities"][0]["type"] == "note_reply"
        # Reply should have the reply comment enriched
        assert result["activities"][0]["reply_comment"] is not None
        assert result["activities"][0]["reply_comment"]["body"] == "Great note, Miles!"

    @pytest.mark.asyncio
    async def test_invalid_filter_returns_error(self):
        from src.tools.activity_feed import get_activity_feed

        result = await get_activity_feed(filter="invalid")

        assert result["error"] is True
        assert result["code"] == "VALIDATION"
        assert "filter" in result["message"]


class TestActivityFeedErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_no_cookie_returns_error(self):
        from src.tools.activity_feed import get_activity_feed

        with patch("src.tools.activity_feed.get_client", return_value=None):
            result = await get_activity_feed()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_auth_expired_returns_error(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(401, {})

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed()

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_server_error_returns_unknown(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(500, {})

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_network_error_returns_unknown(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed()

        assert result["error"] is True
        assert result["code"] == "UNKNOWN"
        assert "Connection refused" in result["message"]


class TestActivityFeedEndpoint:
    """Test correct API endpoint usage."""

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            await get_activity_feed(filter="all")

        mock_client.get.assert_called_once_with(
            "/api/v1/activity-feed-web",
            params={"filter": "all"},
        )

    @pytest.mark.asyncio
    async def test_default_filter_is_all(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            await get_activity_feed()

        mock_client.get.assert_called_once_with(
            "/api/v1/activity-feed-web",
            params={"filter": "all"},
        )


class TestActivityFeedIsNewFlag:
    """Test isNew flag passthrough."""

    @pytest.mark.asyncio
    async def test_is_new_flag_passed_through(self):
        from src.tools.activity_feed import get_activity_feed

        mock_client = AsyncMock()
        mock_client.get.return_value = _make_response(200, MOCK_ACTIVITY_RESPONSE)

        with patch("src.tools.activity_feed.get_client", return_value=mock_client):
            result = await get_activity_feed(filter="all")

        assert result["activities"][0]["is_new"] is True
        assert result["activities"][1]["is_new"] is False
