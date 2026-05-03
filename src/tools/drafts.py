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
