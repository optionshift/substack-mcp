import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.tools.auth import auth_check
from src.tools.fyp_feed import get_fyp_feed
from src.tools.navigator import get_navigator
from src.tools.likes import get_likes
from src.tools.notes_feed import get_notes_feed
from src.tools.post_content import get_post_content
from src.tools.restacks import get_restacks
from src.tools.search import search_publications
from src.tools.subscription_feed import get_subscription_feed
from src.tools.subscriptions import get_subscriptions


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Simple bearer token auth matching the memory-mcp pattern.
    Accepts: Authorization: Bearer <key> header OR ?key=<key> query param.
    Skips /health endpoint.
    """

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        header_token = (request.headers.get("authorization") or "").replace("Bearer ", "")
        query_token = request.query_params.get("key", "")

        if header_token != self.api_key and query_token != self.api_key:
            return JSONResponse(
                {"error": "Unauthorized — invalid or missing API key"},
                status_code=401,
            )

        return await call_next(request)


def create_bearer_verifier():
    """Returns api_key string if MCP_API_KEY is set, None otherwise."""
    return os.environ.get("MCP_API_KEY")


mcp = FastMCP(
    "ss-navigator",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "substack-mcp.fly.dev",
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ],
    ),
)


@mcp.tool()
async def ss_navigator() -> dict:
    """START here. Discover tools, workflows, and Substack API domain knowledge."""
    return get_navigator()


@mcp.tool()
async def ss_auth_check() -> dict:
    """Validate Substack session cookie and return user profile."""
    return await auth_check()


@mcp.tool()
async def ss_get_fyp_feed(limit: int = 20, since: str | None = None, summarize: bool = True) -> list | dict:
    """Get personalized For You feed with dedup and optional summarization."""
    return await get_fyp_feed(limit=limit, since=since, summarize=summarize)


@mcp.tool()
async def ss_get_likes(limit: int = 20, since: str | None = None, summarize: bool = True) -> list | dict:
    """Get user's liked/hearted posts (high signal)."""
    return await get_likes(limit=limit, since=since, summarize=summarize)


@mcp.tool()
async def ss_get_restacks(limit: int = 20, since: str | None = None, summarize: bool = True) -> list | dict:
    """Get user's restacked/shared posts (highest signal)."""
    return await get_restacks(limit=limit, since=since, summarize=summarize)


@mcp.tool()
async def ss_get_notes_feed(limit: int = 30, since: str | None = None) -> list | dict:
    """Get short-form Notes feed with high-signal flagging."""
    return await get_notes_feed(limit=limit, since=since)


@mcp.tool()
async def ss_get_post_content(url: str | None = None, summarize: bool = True) -> dict:
    """Get full article content by URL with optional summarization."""
    return await get_post_content(url=url, summarize=summarize)


@mcp.tool()
async def ss_get_subscription_feed(limit: int = 30, since: str | None = None, summarize: bool = True) -> list | dict:
    """Get subscription feed with dedup, summarization, and RSS fallback."""
    return await get_subscription_feed(limit=limit, since=since, summarize=summarize)


@mcp.tool()
async def ss_search_publications(query: str, limit: int = 10) -> list | dict:
    """Search for Substack publications by keyword (no auth required)."""
    return await search_publications(query=query, limit=limit)


@mcp.tool()
async def ss_get_subscriptions() -> list | dict:
    """List all followed Substack publications."""
    return await get_subscriptions()


def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Request) -> JSONResponse:
    return JSONResponse(health_check())


def get_transport() -> str:
    if os.environ.get("MCP_ENV") == "production":
        return "streamable-http"
    return "stdio"


def create_starlette_app():
    app = mcp.streamable_http_app()
    api_key = create_bearer_verifier()
    if api_key:
        app.add_middleware(BearerAuthMiddleware, api_key=api_key)
    return app


if __name__ == "__main__":
    mcp.run(transport=get_transport())
