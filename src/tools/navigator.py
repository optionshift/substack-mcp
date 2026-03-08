TOOLS = [
    {
        "name": "ss_navigator",
        "description": "START here. Discover tools, workflows, and Substack API domain knowledge.",
    },
    {
        "name": "ss_auth_check",
        "description": "Validate session cookie and cache user_id. Call before any authenticated tool.",
    },
    {
        "name": "ss_get_fyp_feed",
        "description": "Personalized 'For You' feed (algorithmic). Params: limit, since, summarize.",
    },
    {
        "name": "ss_get_subscription_feed",
        "description": "All subscription posts by date. RSS fallback on API failure. Params: limit, since, summarize.",
    },
    {
        "name": "ss_get_notes_feed",
        "description": "Short-form Notes feed. High-signal flagging (likes>10 or restacks>3). Params: limit, since.",
    },
    {
        "name": "ss_get_likes",
        "description": "User's liked posts (high signal). Requires cached user_id from ss_auth_check. Params: limit, since, summarize.",
    },
    {
        "name": "ss_get_restacks",
        "description": "User's restacked posts (highest signal). Requires cached user_id. Params: limit, since, summarize.",
    },
    {
        "name": "ss_get_post_content",
        "description": "Full article by URL. HTML→Markdown conversion. Does not skip seen articles. Params: url, summarize.",
    },
    {
        "name": "ss_get_subscriptions",
        "description": "List all followed publications with metadata (name, subdomain, RSS URL).",
    },
    {
        "name": "ss_search_publications",
        "description": "Search for publications by keyword. No auth required. Params: query, limit.",
    },
]

WORKFLOWS = [
    {
        "name": "Daily Ingestion (Perplexity 7am)",
        "description": "Automated daily content ingestion workflow.",
        "steps": [
            "1. ss_auth_check — validate cookie",
            "2. ss_get_fyp_feed(limit=20) — algorithmic picks",
            "3. ss_get_subscription_feed(limit=30) — subscription posts",
            "4. ss_get_likes(limit=20) — high-signal liked posts",
            "5. ss_get_restacks(limit=20) — highest-signal restacked posts",
            "6. ss_get_notes_feed(limit=30) — short-form notes",
        ],
    },
    {
        "name": "Content Drafting (Claude 9am)",
        "description": "Use ingested articles to draft LinkedIn/Notes content.",
        "steps": [
            "1. Read ingested articles from Notion (already stored by 7am task)",
            "2. ss_get_post_content(url=...) — deep-read high-relevance articles",
            "3. Draft content using article summaries, key quotes, and angles",
        ],
    },
]

AUTH_ROTATION = {
    "description": "How to rotate the Substack session cookie when it expires.",
    "steps": [
        "1. Log in to substack.com in your browser",
        "2. Open DevTools → Application → Cookies → substack.com",
        "3. Copy the value of 'substack.sid'",
        "4. Run: fly secrets set SUBSTACK_SESSION_COOKIE=\"new_value\"",
        "5. Verify: call ss_auth_check to confirm the new cookie works",
    ],
    "notes": "Cookie expiry is months if user does not log out. ss_auth_check will return AUTH_EXPIRED when rotation is needed.",
}


def get_navigator() -> dict:
    return {
        "server": "ss-navigator",
        "version": "1.0.0",
        "description": "Substack Content Navigator MCP Server. Start with ss_auth_check, then use feed tools for content ingestion.",
        "tools": TOOLS,
        "workflows": WORKFLOWS,
        "auth_rotation": AUTH_ROTATION,
        "api_quirks": [
            "Substack has no official API — all endpoints are undocumented and may change.",
            "Auth uses session cookie (substack.sid only), not API keys or bearer tokens.",
            "FYP feed: /api/v1/reader/feed?tab=for-you&type=base — returns items[] mixing posts and notes.",
            "Subscription feed: /api/v1/reader/feed?tab=subscribed&type=secondary — same items[] format.",
            "Subscriptions list: /api/v1/subscriptions/page (NOT /subscriptions — that 301-redirects).",
            "Feed responses use base64-encoded opaque cursors for pagination.",
            "Cookie expiry is ~90 days. Only substack.sid is needed (not connect.sid).",
            "Likes/restacks require user_id from ss_auth_check response.",
            "Rate limit: 1 request/second enforced server-side.",
        ],
    }
