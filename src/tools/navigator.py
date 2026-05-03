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
    {"name": "ss_publish_note", "description": "Publish a Note immediately. Voice-checked. Params: text, attachments (optional), force."},
    {"name": "ss_restack", "description": "Restack a post or note, optionally with a quote-comment Note. Params: target_id, kind ('post' or 'note'), quote_text (optional), force."},
    {"name": "ss_unrestack", "description": "Remove a restack. Params: target_id, kind ('post' or 'note')."},
    {"name": "ss_comment_on_post", "description": "Post a comment on an article. Voice-checked. Params: post_id, text, parent_id (optional), force."},
    {"name": "ss_get_post_comments", "description": "Get the comment tree on an article. Params: post_id, sort ('best_first' default)."},
    {"name": "ss_get_note_replies", "description": "Get replies on a Note thread. Params: note_id, cursor (for pagination)."},
    {"name": "ss_react", "description": "React to a post or note with any emoji. Params: target_id, kind ('post' or 'note'), emoji (default ❤)."},
    {"name": "ss_delete", "description": "Delete a note or a post comment. Params: target_id, kind ('note' or 'post_comment'), post_id (required for post_comment)."},
    {"name": "ss_upload_image", "description": "Upload an image. Returns CDN URL usable as note attachment. Params: image_data (data URI)."},
    {"name": "ss_list_drafts", "description": "List your article drafts. Params: limit, offset."},
    {"name": "ss_get_draft", "description": "Fetch a single article draft by id. Params: draft_id."},
    {"name": "ss_create_draft", "description": "Create an article draft. Voice-checked. Params: title, body_markdown, subtitle (optional), force."},
    {"name": "ss_update_draft", "description": "Update fields on an existing article draft. Voice-checked when body changes. Params: draft_id, fields, force."},
    {"name": "ss_delete_draft", "description": "Delete an article draft. Params: draft_id."},
    {"name": "ss_publish_draft", "description": "Publish an article draft now. Params: draft_id, send (email subscribers), share_automatically."},
    {"name": "ss_schedule_post", "description": "Schedule an article draft for a future date. Params: draft_id, post_date_iso (ISO 8601 UTC)."},
    {"name": "ss_unschedule_post", "description": "Cancel a scheduled article publish. Params: draft_id."},
    {"name": "ss_create_note_draft", "description": "Create a Note draft (unscheduled). Voice-checked. Params: text, force."},
    {"name": "ss_schedule_note", "description": "Schedule a Note for a future time. Voice-checked. Params: text, trigger_at_iso, force."},
    {"name": "ss_list_note_drafts", "description": "List Note drafts and scheduled notes (filter by trigger_at)."},
    {"name": "ss_cancel_scheduled_note", "description": "Cancel a scheduled Note or delete a Note draft. Params: comment_id."},
    {"name": "ss_follow", "description": "Follow a Substack user. Params: user_id."},
    {"name": "ss_unfollow", "description": "Unfollow a Substack user. Params: user_id."},
    {"name": "ss_list_following", "description": "List user_ids you follow."},
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

GROWTH_PLAYBOOK = {
    "algorithm_weights": {
        "highest": ["restacks", "replies-on-others"],
        "medium": ["shares", "saves"],
        "low": ["likes"],
        "note": "Substack ML head Mike Cohen has confirmed restacks are the dominant signal. Engagement on others' work outweighs your own posting volume.",
    },
    "note_format": {
        "length_words": "64-255",
        "structure": "4-6 short paragraphs with whitespace",
        "hook_first_words": "7-10",
        "hook_pattern": "specific claim, unexpected stat, or identity statement",
        "best_windows_et": ["Tue-Thu 8-10 AM", "Tue-Thu 2-4 PM"],
        "first_4_hours": "decide reach; if no early traction, the note is dead",
    },
    "restack_pattern": {
        "rule": "restack-with-comment beats naked restack for your visibility",
        "naked_restack": "promotes original author only",
        "quote_restack": "highlight one sentence; works for any article including your own",
        "tip": "@-mention the author when restacking with comment so they get notified",
    },
    "article_amplification_7d": [
        "Day 0: announce note linking the post",
        "Day 1: quote-restack the strongest single sentence",
        "Day 2: standalone note with one chart/stat from the piece (no link)",
        "Day 3: 'thing I almost cut' as standalone note",
        "Day 4: reply to a related note from a peer, citing your article",
        "Day 5: 'tiny tutorial' note teaching one concrete thing",
        "Day 6: behind-the-scenes / how-I-wrote-it note",
        "Day 7: contrarian framing note that links back",
    ],
    "free_to_paid": {
        "honest_median": "~3% (not the 5-10% Substack markets)",
        "lifts": ["paywalled chat replies", "paid-only sections", "email automations (rolling out 2026)"],
    },
    "recommendations": {
        "share_of_new_subs_2026": "~40%",
        "tactic": "swap recommendations with peers at similar size/niche; high-ROI compounding",
    },
    "voice_rules_per_format": {
        "x_twitter": "ALL lowercase except proper nouns; 1-2 sentences; no em-dashes/emoji/hashtags",
        "substack_notes": "sentence case; 2-3 sentences; best stuff under 10 words",
        "banned_words": ["leverage", "synergy", "ensure", "revolutionary", "crucial", "delve", "foster", "comprehensive", "however", "essentially", "literally"],
        "hard_ban_chars": ["em dash —", "semicolon ;", "colon : (except 'Word: value' label)"],
        "ai_pattern_phrases": ["not because X. because Y.", "here's the thing", "let that sink in", "the real X isn't Y", "unpopular opinion", "hot take"],
    },
}

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
        "growth_playbook": GROWTH_PLAYBOOK,
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
