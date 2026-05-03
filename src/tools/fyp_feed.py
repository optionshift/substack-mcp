from datetime import datetime, timezone

import httpx
import markdownify

from src.dedup import DedupCache
from src.substack_client import create_client

FYP_ENDPOINT = "/api/v1/reader/feed"
CONTENT_HINT = "Use ss_get_post_content with this URL to read the full article"

_cache_instance: DedupCache | None = None


def get_client():
    return create_client()


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


def _parse_article(post: dict) -> dict:
    bylines = post.get("publishedBylines", [])
    author = bylines[0].get("name", "") if bylines else ""
    pub = post.get("publication", {})
    body_html = post.get("body_html", "")
    markdown = markdownify.markdownify(body_html) if body_html else ""

    return {
        "post_id": post.get("id"),
        "title": post.get("title", ""),
        "author": author,
        "publication": pub.get("name", ""),
        "url": post.get("canonical_url", ""),
        "published_at": post.get("post_date", ""),
        "markdown": markdown,
    }


async def get_fyp_feed(
    limit: int = 20,
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
            FYP_ENDPOINT, params={"tab": "for-you", "type": "base"}
        )
    except httpx.ConnectError:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": "Failed to connect to Substack API",
            "retry_after": None,
        }
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
    articles = []

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    for item in items:
        if len(articles) >= limit:
            break

        # FYP mixes posts and notes — only process posts
        post = item.get("post")
        if post is None:
            continue

        parsed = _parse_article(post)
        article_id = f"substack_post_{parsed['post_id']}"

        # Since filter
        if since_dt and parsed["published_at"]:
            try:
                post_dt = datetime.fromisoformat(
                    parsed["published_at"].replace("Z", "+00:00")
                )
                if post_dt < since_dt:
                    continue
            except ValueError:
                pass

        # Dedup: insert returns False if already exists
        is_new = await cache.insert(
            article_id=article_id,
            url=parsed["url"],
            title=parsed["title"],
            source=parsed["publication"],
            source_feed="fyp",
        )
        if not is_new:
            continue

        article = {
            "id": article_id,
            "title": parsed["title"],
            "author": parsed["author"],
            "publication": parsed["publication"],
            "url": parsed["url"],
            "published_at": parsed["published_at"],
            "platform": "substack",
            "is_new": True,
            "source_feed": "fyp",
            "hint": CONTENT_HINT,
        }

        article["content"] = parsed["markdown"]

        articles.append(article)

    return articles
