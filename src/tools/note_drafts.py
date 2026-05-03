from src.substack_client import create_client
from src.voice_check import check as voice_check


def get_client():
    return create_client()


def _to_prosemirror(text: str) -> dict:
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1", "title": None},
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def _post_draft(text: str, trigger_at: str | None, force: bool) -> dict:
    if not text or not text.strip():
        return {
            "error": True, "code": "VALIDATION",
            "message": "text required", "retry_after": None,
        }

    if not force:
        violations = voice_check(text)
        if violations:
            return {
                "error": True, "code": "VOICE_VIOLATION",
                "violations": [v.to_dict() for v in violations],
                "message": "Voice check failed. Use force=True to bypass.",
                "retry_after": None,
            }

    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }

    body: dict = {
        "bodyJson": _to_prosemirror(text),
        "replyMinimumRole": "everyone",
    }
    if trigger_at:
        body["trigger_at"] = trigger_at

    try:
        resp = await client.post("/api/v1/comment/draft", json=body)
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

    data = resp.json()
    return {
        "success": True,
        "id": data.get("id"),
        "trigger_at": data.get("trigger_at"),
        "raw": data,
    }


async def create_note_draft(text: str, force: bool = False) -> dict:
    return await _post_draft(text=text, trigger_at=None, force=force)


async def schedule_note(text: str, trigger_at_iso: str, force: bool = False) -> dict:
    return await _post_draft(text=text, trigger_at=trigger_at_iso, force=force)


async def list_note_drafts(limit: int = 20) -> dict:
    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        resp = await client.get("/api/v1/feed/drafts", params={"limit": limit})
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

    return resp.json()


async def cancel_scheduled_note(comment_id: str) -> dict:
    try:
        comment_int = int(comment_id)
    except (ValueError, TypeError):
        return {
            "error": True, "code": "VALIDATION",
            "message": "comment_id must be numeric", "retry_after": None,
        }

    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        resp = await client.delete(f"/api/v1/comment/{comment_int}")
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

    return {"success": True, "comment_id": comment_id, "action": "deleted"}
