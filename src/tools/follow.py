from src.substack_client import create_client


def get_client():
    return create_client()


async def follow_user(user_id: str) -> dict:
    try:
        user_int = int(user_id)
    except (ValueError, TypeError):
        return {
            "error": True, "code": "VALIDATION",
            "message": "user_id must be numeric", "retry_after": None,
        }

    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        resp = await client.post(f"/api/v1/feed/{user_int}/follow", json={"surface": "profile"})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    if resp.status_code == 401:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie expired.", "retry_after": None,
        }
    if resp.status_code != 200:
        return {
            "error": True, "code": "UNKNOWN",
            "message": f"Unexpected status {resp.status_code}", "retry_after": None,
        }
    return {"success": True, "user_id": user_id, "action": "followed"}


async def unfollow_user(user_id: str) -> dict:
    try:
        user_int = int(user_id)
    except (ValueError, TypeError):
        return {
            "error": True, "code": "VALIDATION",
            "message": "user_id must be numeric", "retry_after": None,
        }

    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        resp = await client.delete(f"/api/v1/feed/{user_int}/follow", json={"surface": "profile"})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    if resp.status_code == 401:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie expired.", "retry_after": None,
        }
    if resp.status_code != 200:
        return {
            "error": True, "code": "UNKNOWN",
            "message": f"Unexpected status {resp.status_code}", "retry_after": None,
        }
    return {"success": True, "user_id": user_id, "action": "unfollowed"}


async def list_following() -> dict:
    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        resp = await client.get("/api/v1/feed/following")
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    if resp.status_code == 401:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie expired.", "retry_after": None,
        }
    if resp.status_code != 200:
        return {
            "error": True, "code": "UNKNOWN",
            "message": f"Unexpected status {resp.status_code}", "retry_after": None,
        }
    return {"user_ids": resp.json()}
