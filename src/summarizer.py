import json
import os

from google import genai

MAX_INPUT_CHARS = 15000
FALLBACK_CHARS = 2000
MODEL = "gemini-2.0-flash-lite"

FIXED_TAGS = {
    "creator-economy", "AI-agents", "monetization", "platform-strategy",
    "content-strategy", "fundraising", "product", "engineering", "culture", "other",
}

PROMPT_TEMPLATE = """Summarize this article for a content strategist. Return valid JSON only, no markdown fences.

Schema:
{{"summary": "2-3 sentence key argument", "tags": ["from fixed list"], "relevance": 1-10, "key_quote": "one notable sentence", "angle": "content hook for LinkedIn/Notes"}}

Fixed tag vocabulary (pick 1-3): creator-economy, AI-agents, monetization, platform-strategy, content-strategy, fundraising, product, engineering, culture, other

Article:
{content}"""


def get_genai_client():
    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


async def summarize(content: str | None) -> dict:
    if not content:
        return {"raw_content": ""}

    client = get_genai_client()
    if client is None:
        return {"raw_content": content[:FALLBACK_CHARS]}

    truncated = content[:MAX_INPUT_CHARS]
    prompt = PROMPT_TEMPLATE.format(content=truncated)

    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        result = json.loads(response.text)
    except Exception:
        return {"raw_content": content[:FALLBACK_CHARS]}

    # Validate and sanitize
    result["tags"] = [t for t in result.get("tags", []) if t in FIXED_TAGS]

    relevance = result.get("relevance", 5)
    if not isinstance(relevance, int):
        relevance = 5
    result["relevance"] = max(1, min(10, relevance))

    for field in ("summary", "key_quote", "angle"):
        if field not in result or not isinstance(result[field], str):
            result[field] = ""

    return result
