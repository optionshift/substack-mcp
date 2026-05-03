from src.dedup import DedupCache
from src.substack_client import create_client

SEARCH_ENDPOINT = "/api/v1/recent/search"
CONTENT_HINT = "Use ss_get_post_content with this URL to read the full article"

_cache_instance: DedupCache | None = None


def get_client():
    return create_client()


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


async def search_trending(
    query: str,
    limit: int = 20,
) -> list | dict:
    client = get_client()
    if client is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    params = {
        "query": query,
        "fromSuggestedSearch": "false",
    }

    try:
        response = await client.get(SEARCH_ENDPOINT, params=params)
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
    cache = get_cache()

    for item in items:
        if len(articles) >= limit:
            break

        post = item.get("post")
        if post is None:
            continue

        publication = item.get("publication", {})
        context = item.get("context", {})
        users = context.get("users", [])
        tracking = context.get("searchTrackingParameters", {})

        author = users[0].get("name", "") if users else ""
        article_id = f"substack_post_{post.get('id', '')}"

        # Dedup: insert but do NOT skip — search should always return all results
        is_new = await cache.insert(
            article_id=article_id,
            url=post.get("canonical_url", ""),
            title=post.get("title", ""),
            source=publication.get("name", ""),
            source_feed="trending",
        )

        article = {
            "id": article_id,
            "title": post.get("title", ""),
            "author": author,
            "publication": publication.get("name", ""),
            "url": post.get("canonical_url", ""),
            "published_at": post.get("post_date", ""),
            "search_score": tracking.get("search_score", 0),
            "recency_score": tracking.get("recency_score", 0),
            "platform": "substack",
            "is_new": is_new,
            "source_feed": "trending",
            "hint": CONTENT_HINT,
        }

        articles.append(article)

    return articles
