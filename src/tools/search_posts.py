from src.dedup import DedupCache
from src.substack_client import create_client

SEARCH_ENDPOINT = "/api/v1/post/search"
CONTENT_HINT = "Use ss_get_post_content with this URL to read the full article"
VALID_FILTERS = {"all", "subscribed"}
VALID_DATE_RANGES = {"day", "week", "month"}


_cache_instance: DedupCache | None = None


def get_client():
    return create_client()


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


async def search_posts(
    query: str,
    page: int = 0,
    filter: str = "all",
    date_range: str | None = None,
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

    if filter not in VALID_FILTERS:
        return {
            "error": True,
            "code": "INVALID_PARAM",
            "message": f"filter must be one of: {sorted(VALID_FILTERS)}",
            "retry_after": None,
        }

    if date_range is not None and date_range not in VALID_DATE_RANGES:
        return {
            "error": True,
            "code": "INVALID_PARAM",
            "message": f"date_range must be one of: {sorted(VALID_DATE_RANGES)}",
            "retry_after": None,
        }

    params = {
        "query": query,
        "page": page,
        "includePlatformResults": "true" if filter == "all" else "false",
        "filter": filter,
    }

    if date_range is not None:
        params["dateRange"] = date_range

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
    results = data.get("results", [])
    articles = []
    cache = get_cache()

    for result in results:
        if len(articles) >= limit:
            break

        bylines = result.get("publishedBylines", [])
        author = bylines[0].get("name", "") if bylines else ""

        article_id = f"substack_post_{result.get('id', '')}"

        # Dedup: insert but do NOT skip (same as post_content — search should always return)
        is_new = await cache.insert(
            article_id=article_id,
            url=result.get("canonical_url", ""),
            title=result.get("title", ""),
            source="",
            source_feed="search",
        )

        article = {
            "id": article_id,
            "title": result.get("title", ""),
            "subtitle": result.get("subtitle", ""),
            "author": author,
            "url": result.get("canonical_url", ""),
            "published_at": result.get("post_date", ""),
            "preview": result.get("truncated_body_text", ""),
            "wordcount": result.get("wordcount", 0),
            "reactions": result.get("reactions", {}),
            "restacks": result.get("restacks", 0),
            "comment_count": result.get("comment_count", 0),
            "cover_image": result.get("cover_image", ""),
            "platform": "substack",
            "is_new": is_new,
            "source_feed": "search",
            "hint": CONTENT_HINT,
        }

        articles.append(article)

    return articles
