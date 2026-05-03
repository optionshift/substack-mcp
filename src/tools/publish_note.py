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


async def publish_note(text: str, attachments: list[str] | None = None, force: bool = False) -> dict:
    if not text or not text.strip():
        return {
            "error": True, "code": "VALIDATION",
            "message": "text is required", "retry_after": None,
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
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    body = {
        "bodyJson": _to_prosemirror(text),
        "replyMinimumRole": "everyone",
    }
    if attachments:
        body["attachmentIds"] = attachments

    try:
        response = await client.post("/api/v1/comment/feed", json=body)
    except Exception as e:
        return {
            "error": True, "code": "UNKNOWN",
            "message": str(e), "retry_after": None,
        }

    if response.status_code == 401:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie expired. Rotate via browser DevTools.",
            "retry_after": None,
        }

    if response.status_code != 200:
        return {
            "error": True, "code": "UNKNOWN",
            "message": f"Unexpected status {response.status_code}",
            "retry_after": None,
        }

    data = response.json()
    return {
        "success": True,
        "id": data.get("id"),
        "body": data.get("body"),
    }
