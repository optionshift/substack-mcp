import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.tools.auth import auth_check
from src.tools.fyp_feed import get_fyp_feed
from src.tools.subscriptions import get_subscriptions

mcp = FastMCP("ss-navigator")


@mcp.tool()
async def ss_auth_check() -> dict:
    """Validate Substack session cookie and return user profile."""
    return await auth_check()


@mcp.tool()
async def ss_get_fyp_feed(limit: int = 20, since: str | None = None, summarize: bool = True) -> list | dict:
    """Get personalized For You feed with dedup and optional summarization."""
    return await get_fyp_feed(limit=limit, since=since, summarize=summarize)


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
    return mcp.streamable_http_app()


if __name__ == "__main__":
    mcp.run(transport=get_transport())
