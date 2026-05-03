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


def _validate_kind(kind: str) -> dict | None:
    if kind not in ("post", "note"):
        return {
            "error": True, "code": "VALIDATION",
            "message": "kind must be 'post' or 'note'",
            "retry_after": None,
        }
    return None


def _validate_id(target_id: str) -> tuple[int | None, dict | None]:
    try:
        return int(target_id), None
    except (ValueError, TypeError):
        return None, {
            "error": True, "code": "VALIDATION",
            "message": "target_id must be a numeric string",
            "retry_after": None,
        }


def _restack_body(target_id_int: int, kind: str) -> dict:
    return {
        "postId": target_id_int if kind == "post" else None,
        "commentId": target_id_int if kind == "note" else None,
        "tabId": "for-you",
        "surface": "feed",
    }


async def restack_content(
    target_id: str,
    kind: str,
    quote_text: str | None = None,
    force: bool = False,
) -> dict:
    err = _validate_kind(kind)
    if err:
        return err
    target_int, err = _validate_id(target_id)
    if err:
        return err

    if quote_text:
        violations = voice_check(quote_text)
        if violations and not force:
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
            "message": "Session cookie not configured.",
            "retry_after": None,
        }

    # If quote_text, post the quote-note first
    if quote_text:
        try:
            quote_body = {
                "bodyJson": _to_prosemirror(quote_text),
                "replyMinimumRole": "everyone",
            }
            quote_resp = await client.post("/api/v1/comment/feed", json=quote_body)
            if quote_resp.status_code == 401:
                return {
                    "error": True, "code": "AUTH_EXPIRED",
                    "message": "Session cookie expired.", "retry_after": None,
                }
            if quote_resp.status_code != 200:
                return {
                    "error": True, "code": "UNKNOWN",
                    "message": f"Quote note POST failed: {quote_resp.status_code}",
                    "retry_after": None,
                }
        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    try:
        response = await client.post("/api/v1/restack/feed", json=_restack_body(target_int, kind))
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if response.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if response.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {response.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "quoted": bool(quote_text)}


async def unrestack_content(target_id: str, kind: str) -> dict:
    err = _validate_kind(kind)
    if err:
        return err
    target_int, err = _validate_id(target_id)
    if err:
        return err

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    try:
        response = await client.delete("/api/v1/restack/feed", json=_restack_body(target_int, kind))
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if response.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if response.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {response.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "action": "unrestacked"}
