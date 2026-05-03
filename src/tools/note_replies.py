from src.substack_client import create_client


def get_client():
    return create_client()


async def get_note_replies(note_id: str, cursor: str | None = None) -> dict:
    try:
        note_int = int(note_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "note_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    params = {}
    if cursor:
        params["cursor"] = cursor

    try:
        resp = await client.get(f"/api/v1/reader/comment/{note_int}/replies", params=params)
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return resp.json()
