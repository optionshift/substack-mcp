import httpx

from src.substack_client import create_client
from src.voice_check import check as voice_check


def get_client():
    return create_client()


async def resolve_publication_subdomain(post_id_int: int) -> str | None:
    """Look up a post's publication subdomain via /api/v1/posts/by-id/{id}.
    Returns the subdomain (e.g., 'lenny') or None on failure."""
    client = get_client()
    if client is None:
        return None
    try:
        resp = await client.get(f"/api/v1/posts/by-id/{post_id_int}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("publication", {}).get("subdomain")
    except Exception:
        return None


async def comment_on_post(
    post_id: str,
    text: str,
    parent_id: str | None = None,
    force: bool = False,
) -> dict:
    if not text or not text.strip():
        return {"error": True, "code": "VALIDATION",
                "message": "text required", "retry_after": None}

    if not force:
        violations = voice_check(text)
        if violations:
            return {
                "error": True, "code": "VOICE_VIOLATION",
                "violations": [v.to_dict() for v in violations],
                "message": "Voice check failed. Use force=True to bypass.",
                "retry_after": None,
            }

    try:
        post_id_int = int(post_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "post_id must be numeric", "retry_after": None}

    parent_int = None
    if parent_id is not None:
        try:
            parent_int = int(parent_id)
        except (ValueError, TypeError):
            return {"error": True, "code": "VALIDATION",
                    "message": "parent_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    subdomain = await resolve_publication_subdomain(post_id_int)
    if subdomain is None:
        return {"error": True, "code": "VALIDATION",
                "message": f"could not resolve publication for post {post_id}",
                "retry_after": None}

    body = {"body": text}
    if parent_int is not None:
        body["parent_id"] = parent_int

    url = f"https://{subdomain}.substack.com/api/v1/post/{post_id_int}/comment"
    try:
        async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
            resp = await http.post(url, json=body)
            await resp.aread()
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    data = resp.json()
    return {"success": True, "id": data.get("id"), "body": data.get("body")}


async def get_post_comments(post_id: str, sort: str = "best_first") -> dict:
    try:
        post_id_int = int(post_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "post_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    subdomain = await resolve_publication_subdomain(post_id_int)
    if subdomain is None:
        return {"error": True, "code": "VALIDATION",
                "message": f"could not resolve publication for post {post_id}",
                "retry_after": None}

    url = f"https://{subdomain}.substack.com/api/v1/post/{post_id_int}/comments"
    params = {"all_comments": "true", "sort": sort}
    try:
        async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
            resp = await http.get(url, params=params)
            await resp.aread()
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return resp.json()
