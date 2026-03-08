import httpx

from src.substack_client import create_client

SUBSCRIPTIONS_ENDPOINT = "/api/v1/subscriptions"


def get_client():
    return create_client()


async def get_subscriptions() -> list | dict:
    client = get_client()
    if client is None:
        return {
            "error": True,
            "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    try:
        response = await client.get(SUBSCRIPTIONS_ENDPOINT)
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
    result = []
    for item in data:
        pub = item.get("publication", {})
        subdomain = pub.get("subdomain", "")
        result.append({
            "name": pub.get("name", ""),
            "subdomain": subdomain,
            "url": f"https://{subdomain}.substack.com",
            "rss_url": f"https://{subdomain}.substack.com/feed",
            "author": pub.get("author_name", ""),
            "description": pub.get("description", ""),
        })
    return result
