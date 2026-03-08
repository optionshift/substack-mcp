from src.substack_client import create_client

ACTIVITY_ENDPOINT = "/api/v1/activity-feed-web"
VALID_FILTERS = ("all", "replies-and-mentions", "restacks")


def get_client():
    return create_client()


def _build_user_lookup(users: list) -> dict:
    return {u["id"]: u for u in users}


def _build_post_lookup(posts: list) -> dict:
    return {p["id"]: p for p in posts}


def _build_comment_lookup(comments: list) -> dict:
    return {c["id"]: c for c in comments}


def _build_pub_lookup(pubs: list) -> dict:
    return {p["id"]: p for p in pubs}


def _enrich_activity(item: dict, users: dict, posts: dict, comments: dict, pubs: dict) -> dict:
    senders = []
    for sender_id in item.get("recent_sender_ids", []):
        user = users.get(sender_id)
        if user:
            senders.append({
                "id": user["id"],
                "name": user.get("name", ""),
                "handle": user.get("handle", ""),
                "photo_url": user.get("photo_url", ""),
                "is_following": user.get("is_following", False),
                "can_dm": user.get("can_dm", False),
            })

    target_post = None
    if item.get("target_post_id"):
        post = posts.get(item["target_post_id"])
        if post:
            target_post = {
                "id": post["id"],
                "title": post.get("title", ""),
                "url": post.get("canonical_url", ""),
            }

    target_comment = None
    if item.get("target_comment_id"):
        comment = comments.get(item["target_comment_id"])
        if comment:
            target_comment = {
                "id": comment["id"],
                "body": comment.get("body", ""),
            }

    reply_comment = None
    if item.get("comment_id"):
        comment = comments.get(item["comment_id"])
        if comment:
            reply_comment = {
                "id": comment["id"],
                "body": comment.get("body", ""),
            }

    publication = None
    if item.get("publication_id"):
        pub = pubs.get(item["publication_id"])
        if pub:
            publication = {
                "id": pub["id"],
                "name": pub.get("name", ""),
                "subdomain": pub.get("subdomain", ""),
            }

    return {
        "type": item.get("type", ""),
        "sender_count": item.get("sender_count", 0),
        "senders": senders,
        "target_post": target_post,
        "target_comment": target_comment,
        "reply_comment": reply_comment,
        "publication": publication,
        "is_new": item.get("isNew", False),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


async def get_activity_feed(
    filter: str = "all",
    limit: int = 20,
) -> dict:
    if filter not in VALID_FILTERS:
        return {
            "error": True,
            "code": "VALIDATION",
            "message": f"filter must be one of: {', '.join(VALID_FILTERS)}",
            "retry_after": None,
        }

    client = get_client()
    if client is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    try:
        response = await client.get(
            ACTIVITY_ENDPOINT,
            params={"filter": filter},
        )
    except Exception as e:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": str(e),
            "retry_after": None,
        }

    if response.status_code == 401:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie expired. Rotate via browser DevTools.",
            "retry_after": None,
        }

    if response.status_code != 200:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": f"Unexpected status {response.status_code}",
            "retry_after": None,
        }

    data = response.json()

    users = _build_user_lookup(data.get("users", []))
    posts = _build_post_lookup(data.get("posts", []))
    comments = _build_comment_lookup(data.get("comments", []))
    pubs = _build_pub_lookup(data.get("pubs", []))

    activities = []
    for item in data.get("activityItems", []):
        if len(activities) >= limit:
            break
        activities.append(_enrich_activity(item, users, posts, comments, pubs))

    return {
        "activities": activities,
        "filter": data.get("filter", filter),
        "has_more": data.get("more", False),
    }
