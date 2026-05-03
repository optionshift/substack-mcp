from datetime import datetime

import markdownify

from src.dedup import DedupCache
from src.substack_client import create_client

CONTENT_HINT = "Use ss_get_post_content with this URL to read the full article"
VALID_INBOX_TYPES = {"saved", "seen", "paid"}

_cache_instance: DedupCache | None = None


def get_client():
    return create_client()


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


async def get_saved_posts(
    inbox_type: str = "saved",
    limit: int = 20,
    since: str | None = None,
) -> list | dict:
    if inbox_type not in VALID_INBOX_TYPES:
        return {
            "error": True,
            "code": "VALIDATION",
            "message": f"inbox_type must be one of: {', '.join(sorted(VALID_INBOX_TYPES))}",
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

    endpoint = "/api/v1/reader/posts"
    params = {"inboxType": inbox_type, "limit": limit}

    try:
        response = await client.get(endpoint, params=params)
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

    cache = get_cache()
    data = response.json()
    posts = data.get("posts", [])
    publications = data.get("publications", [])
    saved_posts = data.get("savedPosts", [])
    inbox_items = data.get("inboxItems", [])

    # Build lookup maps for server-side joins
    pub_map = {pub["id"]: pub for pub in publications}
    saved_map = {sp["post_id"]: sp for sp in saved_posts}
    inbox_map = {}
    for item in inbox_items:
        content_key = item.get("content_key", "")
        if content_key.startswith("post:"):
            try:
                post_id = int(content_key.split(":")[1])
                inbox_map[post_id] = item
            except (ValueError, IndexError):
                pass

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    articles = []
    for post in posts:
        if len(articles) >= limit:
            break

        post_id = post.get("id")
        saved_meta = saved_map.get(post_id, {})
        saved_at = saved_meta.get("created_at", "")
        inbox_meta = inbox_map.get(post_id, {})

        # Filter by since (use saved_at for saved, post_date for seen/paid)
        filter_timestamp = saved_at if inbox_type == "saved" and saved_at else post.get("post_date", "")
        if since_dt and filter_timestamp:
            try:
                item_dt = datetime.fromisoformat(filter_timestamp.replace("Z", "+00:00"))
                if item_dt < since_dt:
                    continue
            except ValueError:
                pass

        pub = pub_map.get(post.get("publication_id"), {})
        bylines = post.get("publishedBylines", [])
        author = bylines[0].get("name", "") if bylines else ""
        body_html = post.get("body_html", "")
        markdown = markdownify.markdownify(body_html) if body_html else ""

        article_id = f"substack_post_{post_id}"
        url = post.get("canonical_url", "")

        # Dedup: insert but don't skip (saved posts always returned)
        is_new = cache.insert(
            article_id=article_id,
            url=url,
            title=post.get("title", ""),
            source=pub.get("name", ""),
            source_feed=inbox_type,
        )

        article = {
            "id": article_id,
            "title": post.get("title", ""),
            "author": author,
            "publication": pub.get("name", ""),
            "url": url,
            "published_at": post.get("post_date", ""),
            "saved_at": saved_at,
            "read_progress": inbox_meta.get("read_progress", 0.0),
            "platform": "substack",
            "is_new": is_new,
            "source_feed": inbox_type,
        }

        if url:
            article["hint"] = CONTENT_HINT

        article["content"] = markdown

        articles.append(article)

    return articles
