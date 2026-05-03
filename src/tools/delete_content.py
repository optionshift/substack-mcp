import httpx

from src.substack_client import create_client
from src.tools.comment_on_post import resolve_publication_subdomain


def get_client():
    return create_client()


async def delete_content(target_id: str, kind: str, post_id: str | None = None) -> dict:
    if kind not in ("note", "post_comment"):
        return {"error": True, "code": "VALIDATION",
                "message": "kind must be 'note' or 'post_comment'", "retry_after": None}
    try:
        target_int = int(target_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "target_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    if kind == "note":
        try:
            resp = await client.delete(f"/api/v1/comment/{target_int}")
        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    else:
        if post_id is None:
            return {"error": True, "code": "VALIDATION",
                    "message": "post_id required when kind='post_comment'", "retry_after": None}
        try:
            post_id_int = int(post_id)
        except (ValueError, TypeError):
            return {"error": True, "code": "VALIDATION",
                    "message": "post_id must be numeric", "retry_after": None}

        subdomain = await resolve_publication_subdomain(post_id_int)
        if subdomain is None:
            return {"error": True, "code": "VALIDATION",
                    "message": f"could not resolve publication for post {post_id}",
                    "retry_after": None}
        url = f"https://{subdomain}.substack.com/api/v1/comment/{target_int}"
        try:
            async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
                resp = await http.delete(url)
                await resp.aread()
        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "action": "deleted"}
