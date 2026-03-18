from src.substack_client import create_client


def get_client():
    return create_client()


async def save_post(post_id: str) -> dict:
    try:
        post_id_int = int(post_id)
    except (ValueError, TypeError):
        return {
            "error": True,
            "code": "VALIDATION",
            "message": "post_id must be a numeric string",
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

    try:
        response = await client.post("/api/v1/posts/saved", json={"post_id": post_id_int})
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
        "post_id": post_id,
        "action": "saved",
    }


async def unsave_post(post_id: str) -> dict:
    try:
        post_id_int = int(post_id)
    except (ValueError, TypeError):
        return {
            "error": True,
            "code": "VALIDATION",
            "message": "post_id must be a numeric string",
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

    try:
        response = await client.delete("/api/v1/posts/saved", json={"post_id": post_id_int})
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
        "post_id": post_id,
        "action": "unsaved",
    }
