from src.substack_client import create_client


def get_client():
    return create_client()


async def react(target_id: str, kind: str, emoji: str = "❤") -> dict:
    if kind not in ("post", "note"):
        return {"error": True, "code": "VALIDATION",
                "message": "kind must be 'post' or 'note'", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    if kind == "post":
        endpoint = f"/api/v1/post/{target_id}/reaction"
        body = {"reaction": emoji, "surface": "reader", "tabId": "for-you"}
    else:
        endpoint = f"/api/v1/comment/{target_id}/reaction"
        body = {"publication_id": None, "reaction": emoji, "tabId": "for-you"}

    try:
        resp = await client.post(endpoint, json=body)
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "emoji": emoji}
