from src.substack_client import create_client


def get_client():
    return create_client()


async def upload_image(image_data: str) -> dict:
    """Upload an image. image_data must be a data URI like 'data:image/jpeg;base64,...'."""
    if not image_data.startswith("data:image/"):
        return {"error": True, "code": "VALIDATION",
                "message": "image_data must be a data URI like 'data:image/jpeg;base64,...'",
                "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    try:
        resp = await client.post("/api/v1/image", json={"image": image_data})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    data = resp.json()
    return {"success": True, "url": data.get("url"), "raw": data}
