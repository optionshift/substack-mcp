import httpx

from src.substack_client import create_client
from src.tools.auth import get_my_publication_subdomain
from src.voice_check import check as voice_check


def get_client():
    return create_client()


async def _http_request(method: str, url: str, **kwargs):
    """Issue an authenticated request to a publication subdomain URL.
    Returns (response, error_dict). On any error, response is None and error_dict is set.
    """
    client = get_client()
    if client is None:
        return None, {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
            resp = await http.request(method, url, **kwargs)
            await resp.aread()
        return resp, None
    except Exception as e:
        return None, {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}


def _check_status(resp) -> dict | None:
    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}
    return None


async def _resolve_pub() -> tuple[str | None, dict | None]:
    sub = await get_my_publication_subdomain()
    if sub is None:
        return None, {"error": True, "code": "AUTH_EXPIRED",
                      "message": "Could not resolve your publication subdomain. Check ss_auth_check.",
                      "retry_after": None}
    return sub, None


async def list_drafts(limit: int = 20, offset: int = 0) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts"
    resp, err = await _http_request("GET", url, params={"limit": limit, "offset": offset})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return resp.json()


async def get_draft(draft_id: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}"
    resp, err = await _http_request("GET", url)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return resp.json()


async def delete_draft(draft_id: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}"
    resp, err = await _http_request("DELETE", url)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "action": "deleted"}


def _md_to_prosemirror(md: str) -> dict:
    """Minimal markdown-to-ProseMirror converter. For now, paragraph-only."""
    paragraphs = [p.strip() for p in (md or "").split("\n\n") if p.strip()]
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1"},
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]}
            for p in paragraphs
        ],
    }


async def create_draft(
    title: str,
    body_markdown: str,
    subtitle: str | None = None,
    force: bool = False,
) -> dict:
    if not force:
        violations = (
            voice_check(body_markdown)
            + voice_check(title)
            + (voice_check(subtitle) if subtitle else [])
        )
        if violations:
            return {"error": True, "code": "VOICE_VIOLATION",
                    "violations": [v.to_dict() for v in violations],
                    "message": "Voice check failed. Use force=True to bypass.",
                    "retry_after": None}

    sub, err = await _resolve_pub()
    if err:
        return err

    body = {
        "draft_title": title,
        "draft_body": _md_to_prosemirror(body_markdown),
    }
    if subtitle:
        body["draft_subtitle"] = subtitle

    url = f"https://{sub}.substack.com/api/v1/drafts"
    resp, err = await _http_request("POST", url, json=body)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    data = resp.json()
    return {"success": True, "id": data.get("id"), "raw": data}


ALLOWED_UPDATE_FIELDS = {
    "title", "subtitle", "slug", "search_engine_title", "search_engine_description",
    "draft_section_id", "body_markdown",
}


async def update_draft(draft_id: str, fields: dict, force: bool = False) -> dict:
    bad = set(fields.keys()) - ALLOWED_UPDATE_FIELDS
    if bad:
        return {"error": True, "code": "VALIDATION",
                "message": f"unsupported fields: {sorted(bad)}",
                "retry_after": None}

    if not force:
        text_to_check = " ".join(
            [str(v) for k, v in fields.items() if isinstance(v, str)]
        )
        if text_to_check.strip():
            violations = voice_check(text_to_check)
            if violations:
                return {"error": True, "code": "VOICE_VIOLATION",
                        "violations": [v.to_dict() for v in violations],
                        "message": "Voice check failed. Use force=True to bypass.",
                        "retry_after": None}

    sub, err = await _resolve_pub()
    if err:
        return err

    body: dict = {}
    for k, v in fields.items():
        if k == "body_markdown":
            body["draft_body"] = _md_to_prosemirror(v)
        elif k == "title":
            body["draft_title"] = v
        elif k == "subtitle":
            body["draft_subtitle"] = v
        else:
            body[k] = v

    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}"
    resp, err = await _http_request("PUT", url, json=body)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "raw": resp.json()}


async def publish_draft(
    draft_id: str,
    send: bool = True,
    share_automatically: bool = False,
) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}/publish"
    resp, err = await _http_request(
        "POST", url, json={"send": send, "share_automatically": share_automatically}
    )
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "raw": resp.json()}


async def schedule_post(draft_id: str, post_date_iso: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}/schedule"
    resp, err = await _http_request("POST", url, json={"post_date": post_date_iso})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "scheduled_for": post_date_iso}


async def unschedule_post(draft_id: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}/schedule"
    resp, err = await _http_request("POST", url, json={"post_date": None})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "action": "unscheduled"}
