import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.tools.auth import auth_check
from src.tools.activity_feed import get_activity_feed
from src.tools.like import like_content
from src.tools.fyp_feed import get_fyp_feed
from src.tools.navigator import get_navigator
from src.tools.likes import get_likes
from src.tools.notes_feed import get_notes_feed
from src.tools.post_content import get_post_content
from src.tools.restacks import get_restacks
from src.tools.search import search_publications
from src.tools.subscription_feed import get_subscription_feed
from src.tools.subscriptions import get_subscriptions


FLY_HOST = os.environ.get("FLY_APP_NAME", "ss-nav-3950b79a5cc7") + ".fly.dev"


def _create_mcp():
    """Create FastMCP instance, conditionally enabling OAuth if OAUTH_PASSWORD is set."""
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            FLY_HOST,
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ],
    )

    oauth_password = os.environ.get("OAUTH_PASSWORD")
    if oauth_password:
        from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
        from src.oauth.db import OAuthDB
        from src.oauth.provider import SubstackOAuthProvider

        provider = SubstackOAuthProvider(
            db=OAuthDB(),
            password=oauth_password,
            issuer_url=f"https://{FLY_HOST}",
        )
        server = FastMCP(
            "ss-navigator",
            auth_server_provider=provider,
            auth=AuthSettings(
                issuer_url=f"https://{FLY_HOST}",
                resource_server_url=f"https://{FLY_HOST}",
                client_registration_options=ClientRegistrationOptions(enabled=True),
                revocation_options=RevocationOptions(enabled=True),
            ),
            transport_security=transport_security,
        )
        return server, provider

    return FastMCP("ss-navigator", transport_security=transport_security), None


mcp, _oauth_provider = _create_mcp()


# -- OAuth login route (only registered if OAuth is enabled) --

if _oauth_provider:
    from src.oauth.pages import login_page

    @mcp.custom_route("/login", methods=["GET", "POST"])
    async def login_endpoint(request: Request) -> HTMLResponse | RedirectResponse:
        if request.method == "GET":
            request_id = request.query_params.get("request_id", "")
            return HTMLResponse(login_page(
                client_name="MCP Client",
                request_id=request_id,
            ))

        form = await request.form()
        request_id = str(form.get("request_id", ""))
        password = str(form.get("password", ""))

        if not _oauth_provider.verify_password(password):
            return HTMLResponse(login_page(
                client_name="MCP Client",
                request_id=request_id,
                error="Invalid password. Please try again.",
            ))

        redirect_url = _oauth_provider.create_auth_code_from_pending(request_id)
        if redirect_url is None:
            return HTMLResponse(login_page(
                client_name="MCP Client",
                request_id=request_id,
                error="Authorization request expired. Please try again.",
            ))

        return RedirectResponse(url=redirect_url, status_code=302)


# -- Tools --


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


@mcp.tool()
async def ss_get_activity_feed(filter: str = "all", limit: int = 20) -> dict:
    """See who liked, restacked, or replied to your posts/notes. Filters: all, replies-and-mentions, restacks."""
    return await get_activity_feed(filter=filter, limit=limit)


@mcp.tool()
async def ss_like(id: str, type: str) -> dict:
    """Like/heart an article or note. type: 'post' or 'note'."""
    return await like_content(id=id, type=type)


# -- Health & transport --


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
