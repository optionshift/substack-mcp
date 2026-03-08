import os

import httpx

BASE_URL = "https://substack.com"


class SubstackClient:
    def __init__(self, session_cookie: str | None = None):
        if session_cookie is None:
            raise ValueError("session_cookie is required")
        self.session_cookie = session_cookie

    def get_cookies(self) -> dict[str, str]:
        return {
            "substack.sid": self.session_cookie,
            "connect.sid": self.session_cookie,
        }

    async def get(self, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=BASE_URL,
            cookies=self.get_cookies(),
        ) as http:
            return await http.get(path, **kwargs)


def create_client() -> SubstackClient | None:
    cookie = os.environ.get("SUBSTACK_SESSION_COOKIE")
    if not cookie:
        return None
    return SubstackClient(session_cookie=cookie)
