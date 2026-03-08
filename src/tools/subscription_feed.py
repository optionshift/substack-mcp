import asyncio
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
import markdownify

from src.dedup import DedupCache
from src.substack_client import create_client
from src.summarizer import summarize as run_summarize
from src.tools.subscriptions import get_subscriptions

SUB_ENDPOINT = "/api/v1/reader/feed"
RAW_CONTENT_CHARS = 2000

_cache_instance: DedupCache | None = None


def get_client():
    return create_client()


def get_cache() -> DedupCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DedupCache()
    return _cache_instance


async def get_subscriptions_list() -> list:
    result = await get_subscriptions()
    if isinstance(result, dict) and result.get("error"):
        return []
    return result


async def fetch_rss(url: str) -> httpx.Response:
    async with httpx.AsyncClient() as http:
        response = await http.get(url)
        await response.aread()
        return response


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


def _parse_rss_item(item: ET.Element, pub_name: str) -> dict:
    title = item.findtext("title", "")
    link = item.findtext("link", "")
    guid = item.findtext("guid", link)
    pub_date = item.findtext("pubDate", "")
    description = item.findtext("description", "")
    markdown = markdownify.markdownify(description) if description else ""

    published_at = ""
    if pub_date:
        try:
            dt = parsedate_to_datetime(pub_date)
            published_at = dt.isoformat()
        except Exception:
            pass

    # Generate a stable ID from the URL for cross-source dedup
    url_hash = hashlib.md5(link.encode()).hexdigest()[:12]

    return {
        "post_id": f"rss_{url_hash}",
        "title": title,
        "author": "",
        "publication": pub_name,
        "url": link,
        "published_at": published_at,
        "markdown": markdown,
    }


async def _fetch_via_rss(
    limit: int,
    since_dt: datetime | None,
    summarize: bool,
    cache: DedupCache,
) -> list:
    subs = await get_subscriptions_list()
    articles = []

    for sub in subs:
        if len(articles) >= limit:
            break

        rss_url = sub.get("rss_url", "")
        if not rss_url:
            continue

        try:
            response = await fetch_rss(rss_url)
            await asyncio.sleep(1)  # Rate limit RSS requests
            if response.status_code != 200:
                continue
        except Exception:
            continue

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            continue

        channel = root.find("channel")
        if channel is None:
            continue

        for item in channel.findall("item"):
            if len(articles) >= limit:
                break

            parsed = _parse_rss_item(item, sub.get("name", ""))
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
                source_feed="subscription",
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
                "source_feed": "subscription",
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


async def get_subscription_feed(
    limit: int = 30,
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

    cache = get_cache()

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    try:
        response = await client.get(
            SUB_ENDPOINT, params={"tab": "subscribed", "type": "secondary"}
        )
    except Exception:
        return await _fetch_via_rss(limit, since_dt, summarize, cache)

    if response.status_code != 200:
        return await _fetch_via_rss(limit, since_dt, summarize, cache)

    data = response.json()
    items = data.get("items", [])
    articles = []

    for item in items:
        if len(articles) >= limit:
            break

        # Subscription feed mixes posts and notes — only process posts
        post = item.get("post")
        if post is None:
            continue

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
            source_feed="subscription",
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
            "source_feed": "subscription",
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
