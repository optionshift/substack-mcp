import os

import httpx

PUBLICATION_SUBDOMAIN = os.environ.get("SUBSTACK_PUBLICATION_SUBDOMAIN")
VALID_ORDER_DIRECTIONS = {"asc", "desc"}


def get_cookie() -> str | None:
    return os.environ.get("SUBSTACK_SESSION_COOKIE")


async def fetch_my_posts(cookie: str, **kwargs) -> httpx.Response:
    base_url = f"https://{PUBLICATION_SUBDOMAIN}.substack.com"
    async with httpx.AsyncClient(
        base_url=base_url,
        cookies={"substack.sid": cookie},
        follow_redirects=True,
    ) as http:
        response = await http.get("/api/v1/post_management/published", **kwargs)
        await response.aread()
        return response


async def get_my_posts(
    limit: int = 10,
    offset: int = 0,
    order_direction: str = "desc",
) -> list | dict:
    if PUBLICATION_SUBDOMAIN is None:
        return {
            "error": True,
            "code": "CONFIG_ERROR",
            "message": "SUBSTACK_PUBLICATION_SUBDOMAIN env var not set.",
            "retry_after": None,
        }

    cookie = get_cookie()
    if cookie is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    if order_direction not in VALID_ORDER_DIRECTIONS:
        return {
            "error": True,
            "code": "INVALID_PARAM",
            "message": f"order_direction must be one of: {sorted(VALID_ORDER_DIRECTIONS)}",
            "retry_after": None,
        }

    params = {
        "offset": offset,
        "limit": limit,
        "order_by": "post_date",
        "order_direction": order_direction,
    }

    try:
        response = await fetch_my_posts(cookie, params=params)
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
    if not isinstance(data, list):
        data = data.get("posts", data.get("results", []))

    posts = []
    for post in data:
        if len(posts) >= limit:
            break

        posts.append({
            "id": f"substack_post_{post.get('id', '')}",
            "title": post.get("title", ""),
            "slug": post.get("slug", ""),
            "url": post.get("canonical_url", ""),
            "published_at": post.get("post_date", ""),
            "subtitle": post.get("subtitle", ""),
            "wordcount": post.get("wordcount", 0),
            "audience": post.get("audience", ""),
            "platform": "substack",
            "source_feed": "my_posts",
        })

    return posts
