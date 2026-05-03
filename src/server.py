import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.tools.auth import auth_check
from src.tools.activity_feed import get_activity_feed
from src.tools.comment_on_post import comment_on_post, get_post_comments
from src.tools.delete_content import delete_content
from src.tools.like import like_content
from src.tools.fyp_feed import get_fyp_feed
from src.tools.navigator import get_navigator
from src.tools.likes import get_likes
from src.tools.note_replies import get_note_replies
from src.tools.notes_feed import get_notes_feed
from src.tools.post_content import get_post_content
from src.tools.restacks import get_restacks
from src.tools.mark_seen import mark_seen
from src.tools.my_posts import get_my_posts
from src.tools.search import search_publications
from src.tools.search_posts import search_posts
from src.tools.search_trending import search_trending
from src.tools.subscription_feed import get_subscription_feed
from src.tools.publish_note import publish_note
from src.tools.react import react
from src.tools.restack import restack_content, unrestack_content
from src.tools.save_post import save_post, unsave_post
from src.tools.saved_posts import get_saved_posts
from src.tools.subscriptions import get_subscriptions
from src.tools.upload_image import upload_image


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
async def ss_get_fyp_feed(limit: int = 20, since: str | None = None) -> list | dict:
    """Get personalized For You feed with dedup."""
    return await get_fyp_feed(limit=limit, since=since)


@mcp.tool()
async def ss_get_likes(limit: int = 20, since: str | None = None) -> list | dict:
    """Get user's liked/hearted posts (high signal)."""
    return await get_likes(limit=limit, since=since)


@mcp.tool()
async def ss_get_restacks(limit: int = 20, since: str | None = None) -> list | dict:
    """Get user's restacked/shared posts (highest signal)."""
    return await get_restacks(limit=limit, since=since)


@mcp.tool()
async def ss_get_notes_feed(limit: int = 30, since: str | None = None) -> list | dict:
    """Get short-form Notes feed with high-signal flagging."""
    return await get_notes_feed(limit=limit, since=since)


@mcp.tool()
async def ss_get_post_content(url: str | None = None) -> dict:
    """Read the full text of a Substack article. Use this after discovering articles via feed or search tools to get the complete content for deep research."""
    return await get_post_content(url=url)


@mcp.tool()
async def ss_get_subscription_feed(limit: int = 30, since: str | None = None) -> list | dict:
    """Get subscription feed with dedup and RSS fallback."""
    return await get_subscription_feed(limit=limit, since=since)


@mcp.tool()
async def ss_search_trending(query: str, limit: int = 20) -> list | dict:
    """Search for trending/recent Substack articles by keyword. Results ranked by recency and engagement scores. Use ss_get_post_content with a result URL to read the full article."""
    return await search_trending(query=query, limit=limit)


@mcp.tool()
async def ss_get_my_posts(limit: int = 10, offset: int = 0, order_direction: str = "desc") -> list | dict:
    """List your own published Substack posts. Useful for content tracking and cross-referencing with engagement data from ss_get_activity_feed."""
    return await get_my_posts(limit=limit, offset=offset, order_direction=order_direction)


@mcp.tool()
async def ss_mark_seen(id: str, type: str = "post") -> dict:
    """Mark a post or note as seen/read in your Substack feed. type: 'post' or 'note'. Helps keep feeds clean for future ingestion passes."""
    return await mark_seen(id=id, type=type)


@mcp.tool()
async def ss_search_posts(
    query: str,
    page: int = 0,
    filter: str = "all",
    date_range: str | None = None,
    limit: int = 20,
) -> list | dict:
    """Search for Substack articles by keyword. Returns article previews with metadata. Supports filtering by time (day/week/month) and scope (all/subscribed). Use ss_get_post_content with a result URL to read the full article."""
    return await search_posts(query=query, page=page, filter=filter, date_range=date_range, limit=limit)


@mcp.tool()
async def ss_search_publications(query: str, limit: int = 10) -> list | dict:
    """Search for Substack publications/newsletters by keyword. Returns publication profiles. Use ss_search_posts to find articles instead."""
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
async def ss_get_saved_posts(inbox_type: str = "saved", limit: int = 20, since: str | None = None) -> list | dict:
    """Get saved/bookmarked articles, recently read posts, or paid-only content. inbox_type: 'saved' (bookmarks), 'seen' (already read), 'paid' (premium). Use ss_get_post_content with a result URL to read the full article."""
    return await get_saved_posts(inbox_type=inbox_type, limit=limit, since=since)


@mcp.tool()
async def ss_save_post(post_id: str) -> dict:
    """Save/bookmark an article for later. Use ss_get_saved_posts to retrieve your saved queue."""
    return await save_post(post_id=post_id)


@mcp.tool()
async def ss_unsave_post(post_id: str) -> dict:
    """Remove an article from your saved/bookmarked queue. Use after extracting playbooks from saved articles."""
    return await unsave_post(post_id=post_id)


@mcp.tool()
async def ss_like(id: str, type: str) -> dict:
    """Like/heart an article or note. type: 'post' or 'note'."""
    return await like_content(id=id, type=type)


@mcp.tool()
async def ss_react(target_id: str, kind: str, emoji: str = "❤") -> dict:
    """React to a post or note with any emoji. Generalizes ss_like.
    Params: target_id, kind ('post' or 'note'), emoji (default ❤)."""
    return await react(target_id=target_id, kind=kind, emoji=emoji)


@mcp.tool()
async def ss_delete(target_id: str, kind: str, post_id: str | None = None) -> dict:
    """Delete a note or a post comment. For 'post_comment', also pass post_id.
    Params: target_id, kind ('note' or 'post_comment'), post_id (required for post_comment)."""
    return await delete_content(target_id=target_id, kind=kind, post_id=post_id)


@mcp.tool()
async def ss_upload_image(image_data: str) -> dict:
    """Upload an image. Returns CDN URL usable as note attachment.
    Params: image_data (data URI 'data:image/jpeg;base64,...')."""
    return await upload_image(image_data=image_data)


@mcp.tool()
async def ss_publish_note(text: str, attachments: list[str] | None = None, force: bool = False) -> dict:
    """Publish a Note immediately. Voice-checked. Use force=True to bypass voice check.
    Params: text (required), attachments (optional list of attachment IDs from ss_upload_image), force (default False)."""
    return await publish_note(text=text, attachments=attachments, force=force)


@mcp.tool()
async def ss_restack(target_id: str, kind: str, quote_text: str | None = None, force: bool = False) -> dict:
    """Restack a post or note, optionally with a quote-comment Note. Voice-checked when quote_text provided.
    Params: target_id, kind ('post' or 'note'), quote_text (optional), force (bypass voice check)."""
    return await restack_content(target_id=target_id, kind=kind, quote_text=quote_text, force=force)


@mcp.tool()
async def ss_unrestack(target_id: str, kind: str) -> dict:
    """Remove a restack. Params: target_id, kind ('post' or 'note')."""
    return await unrestack_content(target_id=target_id, kind=kind)


@mcp.tool()
async def ss_comment_on_post(post_id: str, text: str, parent_id: str | None = None, force: bool = False) -> dict:
    """Post a comment on a Substack article. Voice-checked. Optionally reply to a parent comment.
    Params: post_id, text, parent_id (optional), force (bypass voice check)."""
    return await comment_on_post(post_id=post_id, text=text, parent_id=parent_id, force=force)


@mcp.tool()
async def ss_get_post_comments(post_id: str, sort: str = "best_first") -> dict:
    """Get the comment tree on a Substack article. Params: post_id, sort ('best_first' default)."""
    return await get_post_comments(post_id=post_id, sort=sort)


@mcp.tool()
async def ss_get_note_replies(note_id: str, cursor: str | None = None) -> dict:
    """Get replies on a Note thread. Params: note_id, cursor (for pagination)."""
    return await get_note_replies(note_id=note_id, cursor=cursor)


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
