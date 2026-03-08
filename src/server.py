import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("ss-navigator")


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
