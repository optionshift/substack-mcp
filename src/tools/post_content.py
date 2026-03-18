from urllib.parse import urlparse

import httpx
import markdownify

from src.dedup import DedupCache
from src.summarizer import summarize as run_summarize

CONTENT_HINT = "Use ss_get_post_content with this URL to read the full article"

_cache_instance: DedupCache | None = None


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


def parse_substack_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if hostname.endswith(".substack.com"):
        subdomain = hostname.replace(".substack.com", "")
    else:
        subdomain = hostname

    path_parts = [p for p in parsed.path.split("/") if p]
    slug = path_parts[-1] if path_parts else ""

    return subdomain, slug


async def fetch_post(url: str) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True) as http:
        response = await http.get(url)
        await response.aread()
        return response


async def get_post_content(
    url: str | None = None,
    summarize: bool = False,
) -> dict:
    if not url:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": "url is required.",
            "retry_after": None,
        }

    subdomain, slug = parse_substack_url(url)
    if "." not in subdomain:
        api_url = f"https://{subdomain}.substack.com/api/v1/posts/{slug}"
    else:
        api_url = f"https://{subdomain}/api/v1/posts/{slug}"

    try:
        response = await fetch_post(api_url)
    except Exception as e:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": str(e),
            "retry_after": None,
        }

    if response.status_code == 404:
        return {
            "error": True,
            "code": "NOT_FOUND",
            "message": "Post not found.",
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
    cache = get_cache()

    bylines = data.get("publishedBylines", [])
    author = bylines[0].get("name", "") if bylines else ""
    pub = data.get("publication", {})
    body_html = data.get("body_html", "")
    markdown = markdownify.markdownify(body_html) if body_html else ""

    article_id = f"substack_post_{data.get('id', '')}"

    # Dedup exception: does NOT skip, but DOES insert
    is_new = cache.insert(
        article_id=article_id,
        url=data.get("canonical_url", url or ""),
        title=data.get("title", ""),
        source=pub.get("name", ""),
        source_feed="post_content",
    )

    article = {
        "id": article_id,
        "title": data.get("title", ""),
        "author": author,
        "publication": pub.get("name", ""),
        "url": data.get("canonical_url", url or ""),
        "published_at": data.get("post_date", ""),
        "platform": "substack",
        "is_new": is_new,
        "source_feed": "post_content",
    }

    # Always include full content
    article["content"] = markdown

    if summarize:
        summary_result = await run_summarize(markdown)
        if "raw_content" not in summary_result:
            article.update(summary_result)

    return article
