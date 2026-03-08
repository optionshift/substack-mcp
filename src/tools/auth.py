import httpx

from src.substack_client import create_client

_cached_user_id: str | None = None

AUTH_ENDPOINT = "/api/v1/user/profile/self"


def get_client():
    return create_client()


def get_cached_user_id() -> str | None:
    return _cached_user_id


def _clear_cache():
    global _cached_user_id
    _cached_user_id = None


async def auth_check() -> dict:
    global _cached_user_id

    client = get_client()
    if client is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    try:
        response = await client.get(AUTH_ENDPOINT)
    except httpx.ConnectError:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": "Failed to connect to Substack API",
            "retry_after": None,
        }
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

    data = response.json()
    user_id = str(data.get("id", ""))
    _cached_user_id = user_id

    return {
        "valid": True,
        "user_id": user_id,
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "expires_warning": False,
    }
