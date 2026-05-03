# Substack MCP Server v1.8 - Complete Reference

> **Purpose:** Complete reference documentation for the Substack MCP Server. Designed for LLM consumption to understand all capabilities, tools, and patterns for interacting with Substack's undocumented API.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Tools Reference](#3-tools-reference)
4. [Business Logic & Constants](#4-business-logic--constants)
5. [Error Handling](#5-error-handling)
6. [Deployment](#6-deployment)
7. [Best Practices](#7-best-practices)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Overview

### 1.1 What Is This Server?

The Substack MCP Server (`ss-navigator`) is a Model Context Protocol (MCP) server providing authenticated, structured access to Substack's undocumented API. It enables LLMs to ingest content from 57+ subscriptions, track engagement, and interact with the platform.

**Key Capabilities:**
- Feed ingestion — FYP (algorithmic), subscriptions (chronological), notes (short-form)
- Signal feeds — liked and restacked content (high-value curation signals)
- Activity tracking — see who liked, restacked, or replied to your content
- Content retrieval — full article with HTML→Markdown conversion
- Server-side dedup — SQLite cache prevents re-processing across sessions
- Publication discovery — search for new sources (no auth required)
- Write operations — like/heart articles and notes

### 1.2 Target Use Case

Optimized for **Option Shift's content engine** — daily ingestion of Substack articles to fuel LinkedIn posts, Substack Notes, and long-form blog content:

- **Perplexity Computer** (7am daily) — automated content ingestion into Notion
- **Claude Cowork** (9am daily) — draft LinkedIn/Notes content from ingested articles
- **Engagement** — track who engages with your content and engage back

### 1.3 Server Information

| Property | Value |
|----------|-------|
| Name | ss-navigator |
| Version | 1.8.0 |
| Protocol | MCP 2025-03-26 |
| Transport | StreamableHTTP (production) or stdio (local) |
| Language | Python 3.12+ |
| Framework | FastMCP (`mcp[server]`) |
| Tools | 36 (14 read + 21 write + 1 navigator) |
| Tests | 292 (pytest + pytest-asyncio) |
| Deployment | Fly.io (LAX region) |

---

## 2. Architecture

### 2.1 Transport Modes

**Stdio Transport (Local):**
- Used for local CLI execution
- Default when `MCP_ENV` is not `production`
- Communicates via stdin/stdout

**StreamableHTTP Transport (Remote — Fly.io):**
- FastMCP's built-in `streamable_http_app()` with Starlette/uvicorn
- `POST /mcp` — JSON-RPC request handling
- Session management via `Mcp-Session-Id` header
- DNS rebinding protection enabled (allowed hosts: fly.dev hostname + localhost)

### 2.2 Key Components

```
src/
├── server.py              # MCP server entry point (28 tools, conditional OAuth)
├── __main__.py            # uvicorn production entrypoint (0.0.0.0:8080)
├── __init__.py
├── substack_client.py     # httpx client (cookie auth, 1 req/sec rate limiting)
├── dedup.py               # SQLite dedup cache with schema versioning
├── oauth/
│   ├── __init__.py
│   ├── db.py              # SQLite OAuth tables (clients, codes, tokens)
│   ├── provider.py        # OAuthAuthorizationServerProvider implementation
│   └── pages.py           # HTML login page
└── tools/
    ├── __init__.py
    ├── navigator.py       # Discovery tool (domain knowledge, workflows)
    ├── auth.py            # Cookie validation + user_id caching
    ├── fyp_feed.py        # For You algorithmic feed
    ├── subscription_feed.py  # Subscription feed + RSS fallback
    ├── notes_feed.py      # Short-form notes
    ├── likes.py           # Liked content (high signal)
    ├── restacks.py        # Restacked content (highest signal)
    ├── post_content.py    # Full article retrieval
    ├── subscriptions.py   # Publication list
    ├── search.py          # Publication search (no auth)
    ├── activity_feed.py   # Engagement notifications
    └── like.py            # Like/heart content (write op)
```

### 2.3 Substack Client

Custom `httpx.AsyncClient` wrapper:
- **Cookie auth:** `substack.sid` session cookie (only — not `connect.sid`)
- **Rate limiting:** 1 request/second enforced via `asyncio.sleep`
- **Response buffering:** `await response.aread()` inside async context manager
- **Redirects:** `follow_redirects=True` (Substack returns 301s)
- **Methods:** `get()` and `post()` with identical rate limiting

### 2.4 Dedup Cache

SQLite on Fly Volume (`/data/ss_navigator.db`):
- `seen_articles` table with indexes on `first_seen_at`, `source`, `status`
- Schema versioning via `schema_version` table
- Atomic check-and-insert: `insert()` returns `False` for duplicates
- Thread-safe with `asyncio.Lock`

---

## 3. Tools Reference

The server provides **28 tools** organized into 6 suites.

### Navigation Suite

#### 3.1 ss_navigator — Discovery Tool

START here. Discover tools, workflows, and Substack API domain knowledge.

**Parameters:** None

**Returns:**
```json
{
  "server": "ss-navigator",
  "version": "1.0.0",
  "tools": [...],
  "workflows": [...],
  "auth_rotation": {...},
  "api_quirks": [...]
}
```

**Annotations:** readOnly, idempotent

---

#### 3.2 ss_auth_check — Validate Session

Validate Substack session cookie and return user profile. Call before any authenticated tool.

**Parameters:** None

**Endpoint:** `GET /api/v1/user/profile/self`

**Returns (success):**
```json
{
  "valid": true,
  "user_id": "383926424",
  "name": "Miles Lozano",
  "handle": "mileslozano"
}
```

**Returns (failure):**
```json
{
  "error": true,
  "code": "AUTH_EXPIRED",
  "message": "Session cookie expired. Rotate via browser DevTools.",
  "retry_after": null
}
```

**Side effect:** Caches `user_id` for use by `ss_get_likes` and `ss_get_restacks`.

---

### Feed Suite

#### 3.3 ss_get_fyp_feed — For You Feed

Get personalized For You feed (algorithmic picks) with dedup. Each article includes the full markdown `content` field.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| limit | int | No | 20 | Max articles to return |
| since | str | No | null | ISO date filter (exclude older) |

**Endpoint:** `GET /api/v1/reader/feed?tab=for-you&type=base`

**Returns:** Array of article objects (see [Article Schema](#42-article-schema))

**Dedup:** Yes — skips already-seen articles, inserts new ones

---

#### 3.4 ss_get_subscription_feed — Subscription Feed

Get all subscription posts by date with RSS fallback on API failure. Each article includes the full markdown `content` field.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| limit | int | No | 30 | Max articles to return |
| since | str | No | null | ISO date filter |

**Endpoint:** `GET /api/v1/reader/feed?tab=subscribed&type=secondary`

**Fallback:** On API failure → iterates subscriptions → fetches per-publication RSS feeds (`{subdomain}.substack.com/feed`). RSS is auth-free but cannot access paywalled content.

**Dedup:** Yes

---

#### 3.5 ss_get_notes_feed — Notes Feed

Get short-form Notes feed with high-signal flagging.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| limit | int | No | 30 | Max notes to return |
| since | str | No | null | ISO date filter |

**Endpoint:** `GET /api/v1/reader/feed` (filtered for type=comment inline)

**Returns:** Array of note objects (distinct schema):
```json
{
  "id": "substack_note_12345",
  "author": "Author Name",
  "content": "Note body text",
  "timestamp": "2026-03-06T10:00:00Z",
  "likes": 15,
  "restacks": 4,
  "comments": 2,
  "url": "https://...",
  "high_signal": true
}
```

**High-signal flagging:** `likes > 10` OR `restacks > 3` → `high_signal: true`

**Dedup:** Yes (by note ID)

---

### Signal Suite

#### 3.6 ss_get_likes — Liked Content

Get user's liked/hearted posts and notes (high signal). Requires cached `user_id` from `ss_auth_check`. Each article includes the full markdown `content` field.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| limit | int | No | 20 | Max items to return |
| since | str | No | null | ISO date filter |

**Endpoint:** `GET /api/v1/reader/feed/profile/{user_id}?types[]=like`

**Returns:** Array of article objects. Mixes posts and notes (comments) — both are handled.

**Dedup:** Yes

**Prerequisite:** Call `ss_auth_check` first to cache `user_id`.

---

#### 3.7 ss_get_restacks — Restacked Content

Get user's restacked/shared posts (highest signal). Requires cached `user_id`. Each article includes the full markdown `content` field.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| limit | int | No | 20 | Max items to return |
| since | str | No | null | ISO date filter |

**Endpoint:** `GET /api/v1/reader/feed/profile/{user_id}?types[]=restack`

**Dedup:** Yes

**Prerequisite:** Call `ss_auth_check` first to cache `user_id`.

---

### Content Suite

#### 3.8 ss_get_post_content — Full Article (Deep Read)

Read the full text of a Substack article. Use this after discovering articles via search tools, or any time you need a single article's content. Returns complete markdown — not truncated.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| url | str | Yes | - | Full Substack article URL |

**Endpoint:** `GET https://{subdomain}.substack.com/api/v1/posts/{slug}`

**Returns:** Single article object with full `content` field (complete markdown).

**Two-Tier Pattern:** Search tools return article previews with a `hint` field pointing to this tool. Feed tools already include full content inline; use this tool when you only have a URL.

**Dedup exception:** Does NOT skip already-seen articles, but DOES insert into `seen_articles` to prevent re-appearance in feed pulls.

---

#### 3.9 ss_get_subscriptions — Publication List

List all followed Substack publications with metadata.

**Parameters:** None

**Endpoint:** `GET /api/v1/subscriptions/page`

**Returns:** Array of publication objects:
```json
{
  "name": "Lenny's Newsletter",
  "subdomain": "lennysnewsletter",
  "url": "https://lennysnewsletter.substack.com",
  "rss_url": "https://lennysnewsletter.substack.com/feed",
  "author": "Lenny Rachitsky",
  "description": "..."
}
```

**Dedup:** No (metadata, not content)

**Note:** Endpoint is `/subscriptions/page`, NOT `/subscriptions` (which 301-redirects).

---

#### 3.10 ss_search_posts — Article Search

Search for Substack articles by keyword with time and scope filters. Returns article previews — use `ss_get_post_content` with the result URL to read the full article.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| query | str | Yes | - | Search keyword |
| page | int | No | 0 | Pagination (0-indexed) |
| filter | str | No | "all" | `all` (all Substack) or `subscribed` (your subscriptions only) |
| date_range | str | No | None | `day`, `week`, or `month` |
| limit | int | No | 20 | Max results |

**Endpoint:** `GET /api/v1/post/search?query={q}&page={n}&includePlatformResults={bool}&filter={scope}&dateRange={range}`

**Returns:** Array of article preview objects:
```json
{
  "id": "substack_post_189918781",
  "title": "Article Title",
  "subtitle": "Subtitle text",
  "author": "Author Name",
  "url": "https://pub.substack.com/p/article-slug",
  "published_at": "2026-03-06T05:08:36.227Z",
  "preview": "Truncated body text...",
  "wordcount": 1219,
  "reactions": {"❤": 3},
  "restacks": 2,
  "comment_count": 0,
  "is_new": true,
  "hint": "Use ss_get_post_content with this URL to read the full article"
}
```

**Auth:** Required. **Dedup:** Insert but don't skip (search results always returned).

---

#### 3.11 ss_search_trending — Trending Article Search

Search for trending/recent Substack articles ranked by recency and engagement scores. Complements `ss_search_posts` (keyword relevance) with what's hot right now.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| query | str | Yes | - | Search keyword |
| limit | int | No | 20 | Max results |

**Endpoint:** `GET /api/v1/recent/search?query={q}&fromSuggestedSearch=false`

**Returns:** Array of article objects with `search_score` and `recency_score` for LLM prioritization. Each result includes `hint` field pointing to `ss_get_post_content`.

**Auth:** Required. **Dedup:** Insert but don't skip.

---

#### 3.12 ss_search_publications — Publication Search

Search for Substack publications/newsletters by keyword.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| query | str | Yes | - | Search keyword |
| limit | int | No | 10 | Max results |

**Endpoint:** `GET /api/v1/publication/search?query={q}`

**Returns:** Array of publication objects with name, url, author, description.

**Auth:** Not required. **Dedup:** No.

---

### Engagement Suite

#### 3.11 ss_get_activity_feed — Activity/Notifications

See who liked, restacked, or replied to your posts and notes. Enables engagement-back workflows.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| filter | str | No | "all" | `all`, `replies-and-mentions`, `restacks` |
| limit | int | No | 20 | Max activity items |

**Endpoint:** `GET /api/v1/activity-feed-web?filter={filter}`

**Returns:**
```json
{
  "activities": [
    {
      "type": "note_like",
      "sender_count": 3,
      "senders": [
        {"id": 255841, "name": "Aryn Foland", "handle": "arynfoland", "photo_url": "...", "is_following": false, "can_dm": true}
      ],
      "target_post": {"id": 190215624, "title": "My Article", "url": "https://..."},
      "target_comment": {"id": 214184522, "body": "My note content..."},
      "reply_comment": null,
      "publication": {"id": 12345, "name": "Miles's Newsletter", "subdomain": "miles"},
      "is_new": true,
      "created_at": "2026-02-27T17:35:03.565Z",
      "updated_at": "2026-03-08T21:48:39.019Z"
    }
  ],
  "filter": "all",
  "has_more": true
}
```

**Activity types:**
| Type | Description | target_post | target_comment |
|------|-------------|:-----------:|:--------------:|
| `note_like` | Someone liked your note | — | set |
| `post_like` | Someone liked your post | set | — |
| `restack` | Someone restacked your post | set | — |
| `restack_quote` | Someone quote-restacked your post | set | set (the quote) |
| `note_reply` | Someone replied to your note | — | set (your note) |
| `viral_gift_granted` | Publication granted you gift subs | — | — |

**Enrichment:** Activity items are joined server-side with users, posts, comments, and publications arrays. Senders include name, handle, photo, `is_following`, and `can_dm` for engagement decisions.

**Dedup:** No (notifications, not content).

---

#### 3.12 ss_like — Like/Heart Content

Like/heart an article or note. First write operation.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| id | str | Yes | - | Post ID or comment ID |
| type | str | Yes | - | `post` or `note` |

**Endpoints:**
| Type | Endpoint | Body |
|------|----------|------|
| post | `POST /api/v1/post/{id}/reaction` | `{"reaction": "❤", "surface": "reader", "tabId": "for-you"}` |
| note | `POST /api/v1/comment/{id}/reaction` | `{"publication_id": null, "reaction": "❤", "tabId": "for-you"}` |

**Returns (success):**
```json
{"success": true, "id": "190215624", "type": "post"}
```

#### 3.13 ss_get_saved_posts — Saved/Bookmarked Articles

Get saved articles, recently read posts, or paid-only content. Uses denormalized response with server-side joins.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| inbox_type | str | No | `saved` | `saved` (bookmarks), `seen` (already read), `paid` (premium) |
| limit | int | No | 20 | Max articles to return |
| since | str | No | None | ISO timestamp filter (filters by `saved_at` for saved, `post_date` otherwise) |

**Endpoint:** `GET /api/v1/reader/posts?inboxType={saved|seen|paid}&limit={n}`

**Response shape (API):**
```json
{"posts": [], "publications": [], "savedPosts": [], "inboxItems": [], "more": true}
```

**Returns (per article):**
```json
{
  "id": "substack_post_162633402",
  "title": "89 Best Startup Essays...",
  "author": "VC Corner Author",
  "publication": "The VC Corner",
  "url": "https://thevccorner.substack.com/p/best-startup-essays",
  "published_at": "2025-05-01T18:22:26.577Z",
  "saved_at": "2026-03-17T00:19:52.420Z",
  "read_progress": 0.0,
  "is_new": true,
  "source_feed": "saved",
  "hint": "Use ss_get_post_content with this URL to read the full article"
}
```

**Dedup:** Insert but don't skip (saved posts always returned, like search_posts).

---

#### 3.14 ss_save_post — Save/Bookmark Article

Save an article to your reading list for later processing.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| post_id | str | Yes | - | Numeric post ID |

**Endpoint:** `POST /api/v1/posts/saved` with body `{"post_id": N}`

**Returns (success):**
```json
{"success": true, "post_id": "191270969", "action": "saved"}
```

---

#### 3.15 ss_unsave_post — Remove from Saved Queue

Remove an article from saved/bookmarked queue after extracting playbooks.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| post_id | str | Yes | - | Numeric post ID |

**Endpoint:** `DELETE /api/v1/posts/saved` with body `{"post_id": N}`

**Returns (success):**
```json
{"success": true, "post_id": "184134130", "action": "unsaved"}
```

---

### Tier 1 Write Suite (v1.7.0)

Voice-gated text-posting tools, restacks, reactions, comments, replies, deletes, and image upload. Tools that send user-authored text (`ss_publish_note`, `ss_restack` with `quote_text`, `ss_comment_on_post`) run text through `src/voice_check.py` first. The check enforces hard bans (em dash, en dash, semicolon, colon-with-label-exception, banned words, AI patterns) and returns `VOICE_VIOLATION` on failure. Pass `force=True` to bypass.

#### 3.16 ss_publish_note — Publish a Note

Publish a short-form Note to your Substack feed. Voice-gated.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| text | str | Yes | - | Note body text |
| attachments | list[str] | No | None | Image attachment IDs from `ss_upload_image` |
| force | bool | No | False | Bypass voice check |

**Endpoint:** `POST /api/v1/comment/feed` with body `{"bodyJson": <prosemirror>, "replyMinimumRole": "everyone", "attachmentIds": [...]}`

**Returns (success):**
```json
{"success": true, "id": 214184522, "body": "Note text"}
```

**Returns (voice violation):**
```json
{
  "error": true,
  "code": "VOICE_VIOLATION",
  "violations": [{"rule": "em_dash", "match": "—", "index": 12}],
  "message": "Voice check failed. Use force=True to bypass.",
  "retry_after": null
}
```

---

#### 3.17 ss_restack — Restack Post or Note (Optional Quote)

Restack a post or note. Optionally include `quote_text` to publish a quote-note alongside the restack — quote text is voice-gated.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| target_id | str | Yes | - | Numeric post ID or note (comment) ID |
| kind | str | Yes | - | `post` or `note` |
| quote_text | str | No | None | Quote-note text (voice-gated) |
| force | bool | No | False | Bypass voice check on `quote_text` |

**Endpoint:** `POST /api/v1/restack/feed` with body `{"postId": N | null, "commentId": N | null, "tabId": "for-you", "surface": "feed"}`. When `quote_text` is set, server first POSTs the quote note to `/api/v1/comment/feed`, then issues the restack.

**Returns (success):**
```json
{"success": true, "target_id": "190215624", "kind": "post", "quoted": false}
```

---

#### 3.18 ss_unrestack — Remove a Restack

Remove a previously created restack.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| target_id | str | Yes | - | Numeric post ID or note (comment) ID |
| kind | str | Yes | - | `post` or `note` |

**Endpoint:** `DELETE /api/v1/restack/feed` with body `{"postId": N | null, "commentId": N | null, "tabId": "for-you", "surface": "feed"}`

**Returns (success):**
```json
{"success": true, "target_id": "190215624", "kind": "post", "action": "unrestacked"}
```

---

#### 3.19 ss_comment_on_post — Comment on a Post

Post a comment (or reply) on an article. Server resolves the publication subdomain via `/api/v1/posts/by-id/{post_id}` because the comment endpoint is subdomain-scoped. Voice-gated.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| post_id | str | Yes | - | Numeric post ID |
| text | str | Yes | - | Comment body text |
| parent_id | str | No | None | Numeric ID of a parent comment to reply to |
| force | bool | No | False | Bypass voice check |

**Endpoint:** `POST https://{subdomain}.substack.com/api/v1/post/{post_id}/comment` with body `{"body": text, "parent_id": N?}`

**Returns (success):**
```json
{"success": true, "id": 99887766, "body": "Comment text"}
```

---

#### 3.20 ss_get_post_comments — List Post Comments

Fetch comments on an article (subdomain-scoped). Defaults to `best_first` ordering.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| post_id | str | Yes | - | Numeric post ID |
| sort | str | No | `best_first` | Sort order (`best_first`, `newest_first`, etc.) |

**Endpoint:** `GET https://{subdomain}.substack.com/api/v1/post/{post_id}/comments?all_comments=true&sort={sort}`

**Returns:** Raw API response (passthrough). Typical shape includes a `comments` array with `id`, `body`, `name`, `handle`, `created_at`, and nested `children`.

---

#### 3.21 ss_get_note_replies — List Note Replies

Fetch the reply thread under a Note.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| note_id | str | Yes | - | Numeric note (comment) ID |
| cursor | str | No | None | Pagination cursor |

**Endpoint:** `GET /api/v1/reader/comment/{note_id}/replies?cursor={cursor}`

**Returns:** Raw API response (passthrough) — typically `{"items": [...], "next_cursor": "..."}`.

---

#### 3.22 ss_react — Emoji Reaction (Generalized Like)

Generalized reaction on a post or note. `ss_like` is preserved as a hardcoded ❤ alias; `ss_react` accepts any emoji.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| target_id | str | Yes | - | Numeric post ID or note (comment) ID |
| kind | str | Yes | - | `post` or `note` |
| emoji | str | No | `❤` | Reaction emoji |

**Endpoints:**
| kind | Endpoint | Body |
|------|----------|------|
| post | `POST /api/v1/post/{target_id}/reaction` | `{"reaction": emoji, "surface": "reader", "tabId": "for-you"}` |
| note | `POST /api/v1/comment/{target_id}/reaction` | `{"publication_id": null, "reaction": emoji, "tabId": "for-you"}` |

**Returns (success):**
```json
{"success": true, "target_id": "190215624", "kind": "post", "emoji": "🔥"}
```

---

#### 3.23 ss_delete — Delete Note or Post Comment

Delete a note (top-level Note) or a post comment. Note deletes hit `/api/v1/comment/{id}` directly; post-comment deletes are subdomain-scoped and require `post_id` to resolve the publication.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| target_id | str | Yes | - | Numeric note ID or comment ID |
| kind | str | Yes | - | `note` or `post_comment` |
| post_id | str | No (yes if `kind=post_comment`) | None | Post ID for subdomain resolution |

**Endpoints:**
| kind | Endpoint |
|------|----------|
| note | `DELETE /api/v1/comment/{target_id}` |
| post_comment | `DELETE https://{subdomain}.substack.com/api/v1/comment/{target_id}` |

**Returns (success):**
```json
{"success": true, "target_id": "214184522", "kind": "note", "action": "deleted"}
```

---

#### 3.24 ss_upload_image — Upload Image for Note Attachments

Upload an image and receive the hosted URL. Use the returned URL/ID with `ss_publish_note(attachments=[...])`.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| image_data | str | Yes | - | Data URI: `data:image/jpeg;base64,...` (or png, gif) |

**Endpoint:** `POST /api/v1/image` with body `{"image": "<data-uri>"}`

**Returns (success):**
```json
{
  "success": true,
  "url": "https://substackcdn.com/image/fetch/...",
  "raw": {"url": "...", "id": "..."}
}
```

---

### Article Drafts + Scheduling Suite (v1.8.0)

CRUD for article drafts, plus publish-now and schedule/unschedule. All endpoints are subdomain-scoped (`https://{publication}.substack.com`); the server resolves the user's primary publication subdomain via `ss_auth_check` (`publications[0].subdomain`). Tools that accept user-authored text (`ss_create_draft`, `ss_update_draft` when string fields change) are voice-gated via `src/voice_check.py` with `force=True` bypass.

#### 3.25 ss_list_drafts — List Article Drafts

List your article drafts.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| limit | int | No | 20 | Max drafts to return |
| offset | int | No | 0 | Pagination offset |

**Endpoint:** `GET https://{publication}.substack.com/api/v1/drafts?limit={N}&offset={N}`

**Returns:** Raw API response. Typical shape: `{"drafts": [{"id": N, "title": "...", ...}], "hasMore": false}`.

---

#### 3.26 ss_get_draft — Fetch a Single Draft

Fetch a single article draft by id.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| draft_id | str | Yes | - | Numeric draft ID |

**Endpoint:** `GET https://{publication}.substack.com/api/v1/drafts/{draft_id}`

**Returns:** Raw API response (passthrough). Includes `id`, `draft_title`, `draft_subtitle`, `draft_body` (ProseMirror), and other fields.

---

#### 3.27 ss_delete_draft — Delete a Draft

Delete an article draft.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| draft_id | str | Yes | - | Numeric draft ID |

**Endpoint:** `DELETE https://{publication}.substack.com/api/v1/drafts/{draft_id}`

**Returns (success):**
```json
{"success": true, "draft_id": "42", "action": "deleted"}
```

---

#### 3.28 ss_create_draft — Create an Article Draft

Create an article draft. Title, body, and subtitle are voice-checked.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| title | str | Yes | - | Draft title |
| body_markdown | str | Yes | - | Draft body in markdown (paragraph-only ProseMirror conversion) |
| subtitle | str | No | None | Draft subtitle |
| force | bool | No | False | Bypass voice check |

**Endpoint:** `POST https://{publication}.substack.com/api/v1/drafts` with body `{"draft_title": title, "draft_subtitle": subtitle?, "draft_body": <prosemirror>}`

**Returns (success):**
```json
{"success": true, "id": 99, "raw": {...}}
```

**Returns (voice violation):**
```json
{
  "error": true,
  "code": "VOICE_VIOLATION",
  "violations": [...],
  "message": "Voice check failed. Use force=True to bypass.",
  "retry_after": null
}
```

---

#### 3.29 ss_update_draft — Update a Draft

Update fields on an existing article draft. Voice-checked when string fields change (set `force=True` to bypass).

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| draft_id | str | Yes | - | Numeric draft ID |
| fields | dict | Yes | - | Allowed keys: `title`, `subtitle`, `slug`, `search_engine_title`, `search_engine_description`, `draft_section_id`, `body_markdown` |
| force | bool | No | False | Bypass voice check |

**Endpoint:** `PUT https://{publication}.substack.com/api/v1/drafts/{draft_id}` with body containing the corresponding API field names (`draft_title`, `draft_subtitle`, `draft_body`, etc.).

**Returns (success):**
```json
{"success": true, "draft_id": "42", "raw": {...}}
```

**Returns (validation error on unsupported field):**
```json
{"error": true, "code": "VALIDATION", "message": "unsupported fields: ['unknown_field']", "retry_after": null}
```

---

#### 3.30 ss_publish_draft — Publish a Draft Now

Publish an article draft immediately.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| draft_id | str | Yes | - | Numeric draft ID |
| send | bool | No | True | Email subscribers when publishing |
| share_automatically | bool | No | False | Auto-share to social platforms |

**Endpoint:** `POST https://{publication}.substack.com/api/v1/drafts/{draft_id}/publish` with body `{"send": bool, "share_automatically": bool}`

**Returns (success):**
```json
{"success": true, "draft_id": "42", "raw": {...}}
```

---

#### 3.31 ss_schedule_post — Schedule a Draft for Future Publish

Schedule an article draft for a future date (UTC ISO 8601).

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| draft_id | str | Yes | - | Numeric draft ID |
| post_date_iso | str | Yes | - | Future publish date in ISO 8601 UTC (e.g., `2026-06-01T15:00:00Z`) |

**Endpoint:** `POST https://{publication}.substack.com/api/v1/drafts/{draft_id}/schedule` with body `{"post_date": post_date_iso}`

**Returns (success):**
```json
{"success": true, "draft_id": "42", "scheduled_for": "2026-06-01T15:00:00Z"}
```

---

#### 3.32 ss_unschedule_post — Cancel a Scheduled Publish

Cancel a previously scheduled article publish.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| draft_id | str | Yes | - | Numeric draft ID |

**Endpoint:** `POST https://{publication}.substack.com/api/v1/drafts/{draft_id}/schedule` with body `{"post_date": null}`

**Returns (success):**
```json
{"success": true, "draft_id": "42", "action": "unscheduled"}
```

---

## 4. Business Logic & Constants

### 4.1 Dedup Logic

All feed tools follow the same pattern:
1. Fetch items from Substack API
2. For each item: check `seen_articles` by post ID
3. If exists → **skip** (don't return to client)
4. If new → **insert** into `seen_articles` and return to client

**Exception:** `ss_get_post_content`, `ss_search_posts`, `ss_search_trending`, and `ss_get_saved_posts` insert but do NOT skip — explicit lookups/saved posts always return content.

### 4.2 Article Schema

Standard return object from feed tools — articles always include the full markdown `content` field:
```json
{
  "id": "substack_post_12345",
  "title": "Article Title",
  "author": "Author Name",
  "publication": "Publication Name",
  "url": "https://...",
  "published_at": "2026-03-06T10:00:00Z",
  "platform": "substack",
  "content": "Full article markdown — not truncated",
  "is_new": true,
  "source_feed": "fyp",
  "hint": "Use ss_get_post_content with this URL to read the full article"
}
```

### 4.3 Source Feed Values

| Value | Tool |
|-------|------|
| `fyp` | ss_get_fyp_feed |
| `subscription` | ss_get_subscription_feed |
| `likes` | ss_get_likes |
| `restacks` | ss_get_restacks |
| `notes` | ss_get_notes_feed |
| `saved` | ss_get_saved_posts (inbox_type=saved) |
| `seen` | ss_get_saved_posts (inbox_type=seen) |
| `paid` | ss_get_saved_posts (inbox_type=paid) |

### 4.4 Cookie Auth

- Only `substack.sid` is needed (not `connect.sid`)
- Cookie expiry: ~90 days from login
- Current user ID: `383926424`
- Rotation: browser DevTools → Application → Cookies → copy `substack.sid` → `fly secrets set`

### 4.5 Rate Limiting

- Server enforces 1 request/second via `asyncio.sleep` in the httpx client
- Applies to both `get()` and `post()` methods
- RSS fallback also rate-limited (1 req/sec between feeds)

---

## 5. Error Handling

### 5.1 Error Codes

| Code | Description |
|------|-------------|
| AUTH_EXPIRED | Session cookie missing, expired, or invalid |
| VALIDATION | Invalid input parameters |
| NOT_FOUND | Post or resource not found (404) |
| RATE_LIMITED | Too many requests |
| UNKNOWN | Unexpected error (network, server, etc.) |

### 5.2 Error Response Format

All errors follow a standard shape:
```json
{
  "error": true,
  "code": "AUTH_EXPIRED",
  "message": "Session cookie expired. Rotate via browser DevTools.",
  "retry_after": null
}
```

---

## 6. Deployment

### 6.1 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| SUBSTACK_SESSION_COOKIE | Yes | Substack `substack.sid` cookie value |
| OAUTH_PASSWORD | No | Enables OAuth 2.1 + PKCE when set. Single-user password for the login page. |
| MCP_ENV | No | `production` for StreamableHTTP, else stdio |
| SQLITE_PATH | No | SQLite db path (default: `/data/ss_navigator.db`) |

### 6.2 Fly.io Configuration

| Property | Value |
|----------|-------|
| App name | ss-nav-3950b79a5cc7 |
| Region | LAX |
| Volume | ss_data (1GB) → /data |
| Port | 8080 |
| Image | python:3.12-slim (53MB) |
| Entrypoint | `python -m src` |

### 6.3 HTTP Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/mcp` | POST | Bearer | StreamableHTTP JSON-RPC requests |
| `/health` | GET | Public | Health check → `{"status":"ok","version":"1.0.0"}` |
| `/login` | GET/POST | Public | OAuth login page (password form) |
| `/authorize` | GET/POST | Public | OAuth authorization endpoint (FastMCP) |
| `/token` | POST | Public | OAuth token exchange (FastMCP) |
| `/register` | POST | Public | Dynamic client registration (FastMCP) |
| `/revoke` | POST | Public | Token revocation (FastMCP) |
| `/.well-known/oauth-authorization-server` | GET | Public | OAuth server metadata (RFC 8414) |

### 6.4 OAuth 2.1 + PKCE

Enabled when `OAUTH_PASSWORD` env var is set. Uses FastMCP's built-in `OAuthAuthorizationServerProvider`.

**Flow:**
1. Client discovers endpoints via `/.well-known/oauth-authorization-server`
2. Client registers via `POST /register` → gets `client_id`
3. Client sends `GET /authorize?client_id=...&code_challenge=...&redirect_uri=...`
4. User sees login page at `/login`, enters password
5. On success, redirects to `redirect_uri?code=...&state=...`
6. Client exchanges code at `POST /token` with PKCE `code_verifier`
7. Client uses `Authorization: Bearer <token>` for all `/mcp` requests

**Token lifetimes:** Auth code 5min, access token 1hr, refresh token 30 days (rotated).

**Storage:** OAuth clients, codes, and tokens stored in same SQLite DB as dedup cache (`/data/ss_navigator.db`), migration v2.

### 6.5 Secrets (1Password vault: substack-mcp)

| Secret | Purpose |
|--------|---------|
| SUBSTACK_SESSION_COOKIE | Substack auth (~90 day expiry) |
| OAUTH_PASSWORD | OAuth login page password |

### 6.5 Deploy Commands

```bash
fly deploy                                              # Deploy
fly status                                              # Check status
fly logs                                                # View logs
fly secrets set SUBSTACK_SESSION_COOKIE="new_value"     # Rotate cookie
curl https://ss-nav-3950b79a5cc7.fly.dev/health         # Health check
```

---

## 7. Best Practices

### 7.1 Workflow: Daily Ingestion (Perplexity 7am)

1. `ss_auth_check` — validate cookie
2. `ss_get_fyp_feed(limit=20)` — algorithmic picks
3. `ss_get_subscription_feed(limit=30)` — subscription posts
4. `ss_get_likes(limit=20)` — high-signal liked posts
5. `ss_get_restacks(limit=20)` — highest-signal restacked posts
6. `ss_get_notes_feed(limit=30)` — short-form notes

### 7.2 Workflow: Content Drafting (Claude 9am)

1. Read ingested articles from Notion (stored by 7am task)
2. `ss_get_post_content(url=...)` — deep-read high-relevance articles
3. Draft content using article summaries, key quotes, and angles

### 7.3 Workflow: Engagement (on-demand)

1. `ss_get_activity_feed(filter="all")` — see who engaged
2. Review senders — check `is_following` and `can_dm` fields
3. `ss_like(id=..., type="note")` — like back their content
4. Follow up via Substack DM or Notes reply

### 7.4 Always Auth First

Call `ss_auth_check` before any authenticated tool. It caches `user_id` needed by likes/restacks feeds and provides clear error messages on expiry.

### 7.5 Dedup Is Automatic

Don't worry about duplicate articles across sessions. The server tracks all seen articles in SQLite. Calling the same feed tool twice returns only new content.

---

## 8. Troubleshooting

### 8.1 Common Issues

**Issue: All tools return AUTH_EXPIRED**
- Cause: Session cookie expired (~90 days) or not set
- Solution: Rotate cookie — browser DevTools → Application → Cookies → copy `substack.sid` → `fly secrets set SUBSTACK_SESSION_COOKIE="new_value"`

**Issue: ss_get_likes returns "User ID not cached"**
- Cause: `ss_auth_check` not called first
- Solution: Call `ss_auth_check` before `ss_get_likes` or `ss_get_restacks`

**Issue: Empty feed results**
- Cause: All articles already seen (dedup) or `since` filter too restrictive
- Solution: Check `since` param, or note that dedup is working correctly

**Issue: MCP endpoint returns 307 redirect**
- Cause: Using `/mcp/` (trailing slash) instead of `/mcp`
- Solution: Use `POST /mcp` without trailing slash

**Issue: MCP endpoint returns 421**
- Cause: DNS rebinding protection — hostname not in allowed_hosts
- Solution: Ensure `FLY_APP_NAME` env var matches or add hostname to `allowed_hosts` in server.py

**Issue: Subscription feed returns empty but FYP works**
- Cause: Primary API failure triggering RSS fallback (which only gets free posts)
- Solution: Check Substack API status; RSS fallback is auth-free but limited to free content

---

## Quick Reference Card

### Tool Map
```
ss_navigator            — START here. Discover tools, workflows, API quirks
ss_auth_check           — Validate cookie, cache user_id
ss_get_fyp_feed         — For You feed (algorithmic, dedup)
ss_get_subscription_feed — Subscription feed (chronological, RSS fallback)
ss_get_notes_feed       — Notes feed (short-form, high_signal flagging)
ss_get_likes            — Liked content (high signal, needs user_id)
ss_get_restacks         — Restacked content (highest signal, needs user_id)
ss_get_post_content     — Full article by URL (deep read, no truncation)
ss_get_subscriptions    — List followed publications
ss_search_posts         — Search articles by keyword (time/scope filters)
ss_search_publications  — Search publications/newsletters
ss_get_activity_feed    — Who engaged with your content
ss_like                 — Like/heart a post or note (❤ alias of ss_react)
ss_mark_seen            — Mark post/note as seen/read in feed
ss_get_my_posts         — List your own published posts
ss_search_trending      — Trending articles by recency + engagement
ss_get_saved_posts      — Saved/bookmarked articles (saved/seen/paid filters)
ss_save_post            — Bookmark an article for later
ss_unsave_post          — Remove from saved queue after processing
ss_publish_note         — Publish a Note (voice-gated)
ss_restack              — Restack post/note (optional voice-gated quote)
ss_unrestack            — Remove a restack
ss_comment_on_post      — Comment on an article (voice-gated)
ss_get_post_comments    — List post comments (subdomain-scoped)
ss_get_note_replies     — List replies under a note
ss_react                — Generalized emoji reaction
ss_delete               — Delete a note or post comment
ss_upload_image         — Upload image (returns URL for note attachments)
ss_list_drafts          — List your article drafts
ss_get_draft            — Fetch a single article draft
ss_delete_draft         — Delete an article draft
ss_create_draft         — Create an article draft (voice-gated)
ss_update_draft         — Update fields on a draft (voice-gated)
ss_publish_draft        — Publish a draft now
ss_schedule_post        — Schedule a draft for a future date
ss_unschedule_post      — Cancel a scheduled article publish
```

### API Endpoints (All HAR-Verified)
```
GET  /api/v1/user/profile/self                              Auth check
GET  /api/v1/reader/feed?tab=for-you&type=base              FYP feed
GET  /api/v1/reader/feed?tab=subscribed&type=secondary      Subscription feed
GET  /api/v1/subscriptions/page                             Publication list
GET  /api/v1/reader/feed/profile/{user_id}?types[]=like     Likes
GET  /api/v1/reader/feed/profile/{user_id}?types[]=restack  Restacks
GET  /api/v1/post/search?query={q}&page={n}&filter={scope}   Article search
GET  /api/v1/recent/search?query={q}                        Trending search
GET  /api/v1/publication/search?query={q}                   Publication search
GET  {sub}.substack.com/api/v1/post_management/published    My published posts
POST /api/v1/reader/feed/{p|c}-{id}/seen                    Mark as seen
GET  /api/v1/activity-feed-web?filter={filter}              Activity feed
POST /api/v1/post/{id}/reaction                             React on article (❤ or any emoji)
POST /api/v1/comment/{id}/reaction                          React on note (❤ or any emoji)
POST /api/v1/activity/unread                                Mark as read
GET  /api/v1/reader/posts?inboxType={saved|seen|paid}       Saved/reading list
POST /api/v1/posts/saved                                    Save/bookmark article
DEL  /api/v1/posts/saved                                    Unsave/unbookmark
POST /api/v1/comment/feed                                   Publish note (prosemirror body)
POST /api/v1/restack/feed                                   Restack post/note
DEL  /api/v1/restack/feed                                   Unrestack post/note
GET  /api/v1/posts/by-id/{post_id}                          Resolve publication subdomain
POST {sub}.substack.com/api/v1/post/{id}/comment            Comment on a post
GET  {sub}.substack.com/api/v1/post/{id}/comments           List post comments
GET  /api/v1/reader/comment/{note_id}/replies               List note replies
DEL  /api/v1/comment/{id}                                   Delete a note
DEL  {sub}.substack.com/api/v1/comment/{id}                 Delete a post comment
POST /api/v1/image                                          Upload image (data URI in)
GET  {sub}.substack.com/api/v1/drafts                       List article drafts
GET  {sub}.substack.com/api/v1/drafts/{draft_id}            Get article draft by id
PUT  {sub}.substack.com/api/v1/drafts/{draft_id}            Update article draft
DEL  {sub}.substack.com/api/v1/drafts/{draft_id}            Delete article draft
POST {sub}.substack.com/api/v1/drafts                       Create article draft
POST {sub}.substack.com/api/v1/drafts/{id}/publish          Publish draft now
POST {sub}.substack.com/api/v1/drafts/{id}/schedule         Schedule (or unschedule with post_date=null)
```

### Feed Response Format
```
All feeds return items[] with: { entity_key, type, post, comment, context }
NOT posts[] — this is a common mistake.
```

### Auth Quick Reference
```
Cookie:     substack.sid only (NOT connect.sid)
Expiry:     ~90 days from login
User ID:    383926424
Rotate:     fly secrets set SUBSTACK_SESSION_COOKIE="new_value"
Validate:   ss_auth_check (caches user_id)
```

---

*Document Version: 1.8.0*
*Last Updated: May 2, 2026*
*Compatible with: Substack MCP Server v1.8*

### Changelog
- **1.8.0** (2026-05-02): Sprint 7 Batch 4 — 8 article drafts + post scheduling tools (ss_list_drafts, ss_get_draft, ss_delete_draft, ss_create_draft, ss_update_draft, ss_publish_draft, ss_schedule_post, ss_unschedule_post). Subdomain-scoped via `auth.get_my_publication_subdomain()`. Voice gate on create/update.
- **1.7.0** (2026-05-02): Sprint 7 Batch 3 — 9 Tier 1 write tools (publish_note, restack, unrestack, comment_on_post, get_post_comments, get_note_replies, react, delete, upload_image). Voice gate enforced via src/voice_check.py.
- **1.6.0** (2026-05-02): Removed summarizer (Sprint 7 Batch 1). Dropped `google-genai` dependency, removed `summarize` param from all read tools. Feed tools now always return full markdown via `content` field. 19 tools total, 222 tests.
- **1.5.0**: Saved Posts & Playbook Pipeline. Added `ss_get_saved_posts` (reading list with inbox_type filters: saved/seen/paid, server-side joins of posts+publications+savedPosts+inboxItems, read_progress tracking), `ss_save_post` (bookmark articles), `ss_unsave_post` (remove from queue after processing). Added `delete()` to SubstackClient. 2 new workflows (Saved Posts → Playbook, Morning Engagement Check). 19 tools total, 235 tests.
- **1.4.0**: Added `ss_search_trending` (trending articles with recency/engagement scores), `ss_get_my_posts` (creator's published posts, subdomain-scoped), `ss_mark_seen` (mark feed items as read). 16 tools total, 200 tests.
- **1.3.0**: Deep Research Enablement. Two-tier content architecture: feed tools return summaries with `hint` field, `ss_get_post_content` returns full untruncated markdown. New `ss_search_posts` tool for article search with time/scope filters (HAR-verified `/api/v1/post/search`). Removed 2000-char content truncation. Summarizer key allowlisting to prevent field clobbering. 13 tools total, 171 tests.
- **1.2.0**: Added OAuth 2.1 + PKCE authentication via FastMCP's built-in OAuthAuthorizationServerProvider. Single-user password-based flow with dynamic client registration, PKCE S256, token rotation. SQLite-backed (migration v2). Enabled when OAUTH_PASSWORD env var is set. Allows Perplexity and other MCP clients to authenticate via standard OAuth flow.
- **1.1.0**: Added `ss_get_activity_feed` (engagement notifications, 3 filters, enriched senders). Added `ss_like` (first write operation). 12 tools total, 145 tests. HAR-verified all endpoints.
- **1.0.0**: Initial release. 10 read tools, server-side dedup + summarization, Fly.io deployment. 121 tests.
