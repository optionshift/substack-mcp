from src.substack_client import create_client


def get_client():
    return create_client()


async def mark_seen(id: str, type: str = "post") -> dict:
    if type not in ("post", "note"):
        return {
            "error": True,
            "code": "VALIDATION",
            "message": "type must be 'post' or 'note'",
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

    prefix = "p" if type == "post" else "c"
    endpoint = f"/api/v1/reader/feed/{prefix}-{id}/seen"

    try:
        response = await client.post(endpoint)
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

    return {
        "success": True,
        "id": id,
        "type": type,
    }
