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
        "description": "Personalized 'For You' feed (algorithmic). Params: limit, since.",
    },
    {
        "name": "ss_get_subscription_feed",
        "description": "All subscription posts by date. RSS fallback on API failure. Params: limit, since.",
    },
    {
        "name": "ss_get_notes_feed",
        "description": "Short-form Notes feed. High-signal flagging (likes>10 or restacks>3). Params: limit, since.",
    },
    {
        "name": "ss_get_likes",
        "description": "User's liked posts (high signal). Requires cached user_id from ss_auth_check. Params: limit, since.",
    },
    {
        "name": "ss_get_restacks",
        "description": "User's restacked posts (highest signal). Requires cached user_id. Params: limit, since.",
    },
    {
        "name": "ss_get_post_content",
        "description": "Read the FULL text of any article by URL. Use this after discovering articles via feed or search tools. Returns complete markdown. Params: url.",
    },
    {
        "name": "ss_get_subscriptions",
        "description": "List all followed publications with metadata (name, subdomain, RSS URL).",
    },
    {
        "name": "ss_search_posts",
        "description": "Search for articles by keyword. Supports time filters (day/week/month) and scope (all/subscribed). Returns previews — use ss_get_post_content for full text. Params: query, page, filter, date_range, limit.",
    },
    {
        "name": "ss_search_trending",
        "description": "Search for trending/recent articles by keyword. Ranked by recency + engagement scores. Params: query, limit.",
    },
    {
        "name": "ss_search_publications",
        "description": "Search for publications/newsletters by keyword. Params: query, limit.",
    },
    {
        "name": "ss_get_my_posts",
        "description": "List your own published posts. Supports pagination and sort order. Params: limit, offset, order_direction.",
    },
    {
        "name": "ss_mark_seen",
        "description": "Mark a post or note as seen/read in your feed. Params: id, type ('post' or 'note').",
    },
    {
        "name": "ss_get_activity_feed",
        "description": "See who liked, restacked, or replied to your content. Params: filter ('all', 'replies-and-mentions', 'restacks'), limit.",
    },
    {
        "name": "ss_get_saved_posts",
        "description": "Get saved/bookmarked articles, recently read posts, or paid-only content. Params: inbox_type ('saved', 'seen', 'paid'), limit, since.",
    },
    {
        "name": "ss_save_post",
        "description": "Save/bookmark an article for later. Params: post_id.",
    },
    {
        "name": "ss_unsave_post",
        "description": "Remove an article from saved queue (after extracting playbook). Params: post_id.",
    },
    {
        "name": "ss_like",
        "description": "Like/heart an article or note. Params: id (post or comment ID), type ('post' or 'note').",
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
    {
        "name": "Saved Posts → Playbook Pipeline",
        "description": "Review saved articles and turn them into actionable playbooks for prompting, GTM, VC strategy, etc.",
        "steps": [
            "1. ss_auth_check — validate cookie",
            "2. ss_get_saved_posts(inbox_type='saved') — retrieve bookmarked articles",
            "3. ss_get_post_content(url=...) — deep-read each saved article",
            "4. Extract playbook/framework from article content",
            "5. ss_unsave_post(post_id=...) — remove from saved queue once processed",
        ],
    },
    {
        "name": "Morning Engagement Check",
        "description": "Check recently posted paid content and get early on replies.",
        "steps": [
            "1. ss_auth_check — validate cookie",
            "2. ss_get_saved_posts(inbox_type='paid') — see new premium content",
            "3. ss_get_saved_posts(inbox_type='seen') — review recently read articles",
            "4. ss_get_post_content(url=...) — re-read articles worth engaging with",
            "5. Use insights to craft early, thoughtful replies",
        ],
    },
    {
        "name": "Two-Tier Deep Research",
        "description": "Discover articles via feeds/search (Tier 1: summaries), then read full content (Tier 2: complete text).",
        "steps": [
            "1. ss_auth_check — validate cookie",
            "2. Use feed tools (ss_get_fyp_feed, ss_get_subscription_feed) or ss_search_posts to discover articles — returns summaries with hints",
            "3. Pick interesting articles from results",
            "4. ss_get_post_content(url=article_url) — returns complete article markdown for deep reading",
            "5. Repeat step 4 for each article you want to read in full",
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
            "Like article: POST /api/v1/post/{id}/reaction with {reaction: ❤, surface: reader, tabId: for-you}.",
            "Like note: POST /api/v1/comment/{id}/reaction with {publication_id: null, reaction: ❤, tabId: for-you}.",
            "Activity feed: GET /api/v1/activity-feed-web?filter={all|replies-and-mentions|restacks} — shows who engaged with your content.",
            "Activity feed returns denormalized data: activityItems[] + users[] + posts[] + comments[] + pubs[] for client-side join.",
            "Activity types: note_like, post_like, restack, restack_quote, note_reply, viral_gift_granted.",
            "Mark activity as read: POST /api/v1/activity/unread with {after: ISO timestamp}.",
            "Article search: GET /api/v1/post/search?query={q}&page={n}&includePlatformResults={bool}&filter={all|subscribed}&dateRange={day|week|month}.",
            "Article search returns: title, subtitle, truncated_body_text, wordcount, reactions, canonical_url — use ss_get_post_content for full text.",
            "Rate limit: 1 request/second enforced server-side.",
            "Saved posts: GET /api/v1/reader/posts?inboxType=saved&limit=20 — returns posts[] + publications[] + savedPosts[] (denormalized, server joins them).",
            "Reading list filters: inboxType=saved (bookmarks), seen (already read), paid (premium content).",
            "Save article: POST /api/v1/posts/saved with {post_id: N} — returns {}.",
            "Unsave article: DELETE /api/v1/posts/saved with {post_id: N} — returns {}.",
            "Saved posts pagination: use &after=ISO_TIMESTAMP for cursor-based paging.",
        ],
    }
