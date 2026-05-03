from datetime import datetime

import httpx

from src.dedup import DedupCache
from src.substack_client import create_client

NOTES_ENDPOINT = "/api/v1/reader/feed"
HIGH_SIGNAL_LIKES = 10
HIGH_SIGNAL_RESTACKS = 3

_cache_instance: DedupCache | None = None


def get_client():
    return create_client()


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


async def get_notes_feed(
    limit: int = 30,
    since: str | None = None,
) -> list | dict:
    client = get_client()
    if client is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    cache = get_cache()

    try:
        response = await client.get(
            NOTES_ENDPOINT, params={"tab": "for-you", "type": "base"}
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
    items = data.get("items", [])
    notes = []

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    for item in items:
        if len(notes) >= limit:
            break

        # Only process notes (comments), skip posts
        comment = item.get("comment")
        if comment is None:
            continue

        note_id = str(comment.get("id", ""))
        article_id = f"substack_note_{note_id}"
        timestamp = comment.get("date", "")

        if since_dt and timestamp:
            try:
                note_dt = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
                if note_dt < since_dt:
                    continue
            except ValueError:
                pass

        is_new = await cache.insert(
            article_id=article_id,
            url="",
            title=comment.get("body", "")[:100],
            source="notes",
            source_feed="notes",
        )
        if not is_new:
            continue

        author = comment.get("name", "")
        likes = comment.get("reaction_count", 0)
        restacks = comment.get("restacks", 0)
        comments = comment.get("children_count", 0)

        high_signal = likes > HIGH_SIGNAL_LIKES or restacks > HIGH_SIGNAL_RESTACKS

        notes.append({
            "id": article_id,
            "author": author,
            "content": comment.get("body", ""),
            "timestamp": timestamp,
            "likes": likes,
            "restacks": restacks,
            "comments": comments,
            "url": "",
            "high_signal": high_signal,
        })

    return notes
