from datetime import datetime

import httpx
import markdownify

from src.dedup import DedupCache
from src.substack_client import create_client
from src.summarizer import summarize as run_summarize
from src.tools.auth import get_cached_user_id

RAW_CONTENT_CHARS = 2000

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


async def get_likes(
    limit: int = 20,
    since: str | None = None,
    summarize: bool = True,
) -> list | dict:
    client = get_client()
    if client is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    user_id = get_cached_user_id()
    if not user_id:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "User ID not cached. Call ss_auth_check first.",
            "retry_after": None,
        }

    cache = get_cache()
    endpoint = f"/api/v1/reader/feed/profile/{user_id}"

    try:
        response = await client.get(endpoint, params={"types[]": "like"})
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
    posts = data.get("posts", [])
    articles = []

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    for post in posts:
        if len(articles) >= limit:
            break

        parsed = _parse_article(post)
        article_id = f"substack_post_{parsed['post_id']}"

        if since_dt and parsed["published_at"]:
            try:
                post_dt = datetime.fromisoformat(
                    parsed["published_at"].replace("Z", "+00:00")
                )
                if post_dt < since_dt:
                    continue
            except ValueError:
                pass

        is_new = cache.insert(
            article_id=article_id,
            url=parsed["url"],
            title=parsed["title"],
            source=parsed["publication"],
            source_feed="likes",
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
            "source_feed": "likes",
        }

        if summarize:
            summary_result = await run_summarize(parsed["markdown"])
            if "raw_content" in summary_result:
                article["raw_content"] = summary_result["raw_content"]
            else:
                article.update(summary_result)
        else:
            article["raw_content"] = parsed["markdown"][:RAW_CONTENT_CHARS]

        articles.append(article)

    return articles
