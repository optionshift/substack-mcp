import httpx

SEARCH_ENDPOINT = "https://substack.com/api/v1/publication/search"


async def fetch_search(query: str) -> httpx.Response:
    async with httpx.AsyncClient() as http:
        response = await http.get(SEARCH_ENDPOINT, params={"query": query})
        await response.aread()
        return response


async def search_publications(
    query: str,
    limit: int = 10,
) -> list | dict:
    try:
        response = await fetch_search(query)
    except Exception as e:
        return {
            "error": True,
            "code": "UNKNOWN",
            "message": str(e),
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
    results = []

    for pub in data:
        if len(results) >= limit:
            break

        subdomain = pub.get("subdomain", "")
        custom_domain = pub.get("custom_domain")
        base_url = f"https://{custom_domain}" if custom_domain else f"https://{subdomain}.substack.com"

        results.append({
            "name": pub.get("name", ""),
            "url": base_url,
            "author": pub.get("author_name", ""),
            "description": pub.get("description", ""),
            "subscriber_count": pub.get("active_subscribers", 0),
        })

    return results
