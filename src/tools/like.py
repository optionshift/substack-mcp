from src.tools.react import get_client, react


async def like_content(id: str, type: str) -> dict:
    """Backward-compat alias for ss_react with emoji=❤.

    Returns the old response shape {success, id, type} (or error dict).
    """
    result = await react(target_id=id, kind=type, emoji="❤")
    if result.get("error"):
        return result
    return {"success": True, "id": id, "type": type}
