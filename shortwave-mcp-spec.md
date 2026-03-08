# MCP Server Spec: substack-mcp
## Substack Content Navigator for Automated Ingestion
### Version 1.0 — March 7, 2026

---

## Overview

A remote MCP server hosted on Fly.io that provides authenticated, structured access to Substack's undocumented API for content ingestion. Designed to be consumed by Perplexity Computer and Claude Cowork scheduled tasks as the ingestion layer of a personal brand content engine.

**Primary consumer:** Perplexity Computer (daily scheduled task) + Claude Cowork (daily drafting task)
**Runtime:** Python 3.12+ on Fly.io (remote MCP over SSE)
**Auth:** Substack session cookie (`substack.sid` / `connect.sid`)
**Dependencies:** `httpx`, `mcp[server]`, `google-genai` (for optional summarization), `sqlite3` (for dedup cache)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Clients                          │
│  ┌──────────────────┐  ┌──────────────────────────┐     │
│  │ Perplexity       │  │ Claude Cowork            │     │
│  │ Computer         │  │ Scheduled Tasks          │     │
│  │ (daily 7am)      │  │ (daily 9am)              │     │
│  └────────┬─────────┘  └────────┬─────────────────┘     │
│           │                     │                       │
│           └─────────┬───────────┘                       │
│                     │ SSE                               │
│                     ▼                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │           ss-navigator MCP Server                │   │
│  │           (Fly.io — Remote SSE)                  │   │
│  │                                                  │   │
│  │  ┌────────────┐ ┌──────────┐ ┌───────────────┐  │   │
│  │  │ Substack   │ │ SQLite   │ │ Gemini Flash  │  │   │
│  │  │ API Client │ │ Dedup    │ │ Summarizer    │  │   │
│  │  │ (httpx)    │ │ Cache    │ │ (optional)    │  │   │
│  │  └─────┬──────┘ └────┬─────┘ └──────┬────────┘  │   │
│  │        │              │              │           │   │
│  └────────┼──────────────┼──────────────┼───────────┘   │
│           │              │              │               │
│           ▼              ▼              ▼               │
│     substack.com    Fly Volume    Gemini Flash API      │
│     (undoc API)     (persistent)  ($0.10/1M tokens)     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Authentication

Substack uses a session cookie for all authenticated endpoints. Two cookie names have been observed in the wild:

- `substack.sid` (newer)
- `connect.sid` (older, still works)

### How to obtain:
1. Log in to substack.com in Chrome
2. DevTools → Application → Cookies → substack.com
3. Copy the value of `substack.sid` (or `connect.sid`)

### Storage:
- Stored as `SUBSTACK_SESSION_COOKIE` env var on Fly.io
- Passed as `Cookie: substack.sid={value}` header on all authenticated requests
- Session cookies expire periodically (~30 days). The MCP server should return a clear error when auth fails so the user knows to rotate the cookie.

### Auth validation tool:
The server exposes a `ss_auth_check` tool that verifies the cookie is still valid before running any feed pulls.

---

## Data Layer: SQLite Dedup Cache

**Purpose:** Prevent re-processing articles that have already been ingested. The MCP server, not the client, is responsible for dedup.

**Location:** Fly Volume (persistent across deploys)

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS seen_articles (
    id TEXT PRIMARY KEY,           -- Substack post ID or URL hash
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,          -- Publication name
    first_seen_at TEXT NOT NULL,   -- ISO 8601
    status TEXT DEFAULT 'new'      -- new | returned | error
);

CREATE INDEX idx_seen_articles_first_seen ON seen_articles(first_seen_at);
CREATE INDEX idx_seen_articles_source ON seen_articles(source);
```

**Dedup logic:** Before returning any article from any feed tool, check `seen_articles` by post ID. If exists, skip. If new, insert and return. This means clients can call the same tool repeatedly without getting duplicates.

---

## Summarization Layer (Optional, Server-Side)

**Purpose:** Compress full article content into structured summaries BEFORE returning to the MCP client. This keeps Claude/Perplexity token usage minimal — the client never sees raw article markdown.

**Model:** Gemini 2.0 Flash-Lite via `google-genai` SDK
**Cost:** ~$0.0006 per article (5K input tokens, 200 output tokens)
**API Key:** Stored as `GOOGLE_AI_API_KEY` env var on Fly.io

**Summarization schema (returned as JSON):**
```json
{
  "summary": "2-3 sentence summary of the key argument or insight",
  "tags": ["creator-economy", "AI-agents", "platform-strategy"],
  "relevance": 8,
  "key_quote": "One notable sentence from the article",
  "angle": "One sentence content hook for LinkedIn or Substack Note"
}
```

**Behavior:**
- Every read tool accepts an optional `summarize: bool` param (default: `true`)
- When `summarize=true`: full article content is sent to Flash-Lite, structured summary is returned, raw content is discarded
- When `summarize=false`: raw content (truncated to 2000 chars) is returned directly
- Tag vocabulary is fixed: `creator-economy`, `AI-agents`, `monetization`, `platform-strategy`, `content-strategy`, `fundraising`, `product`, `engineering`, `culture`, `other`
- Relevance scoring prompt includes context: "Score 1-10 for relevance to a founder building an AI creator platform, focused on creator economy, AI agents, and content monetization"

---

## MCP Tools

### `ss_auth_check`
Validates that the stored session cookie is still active.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/user/me` |
| **Auth** | Required |
| **Params** | None |
| **Returns** | `{ valid: bool, user_id: string, name: string, email: string, expires_warning: bool }` |
| **Notes** | Call this first in any scheduled workflow. If `valid=false`, surface error to client immediately. |

---

### `ss_get_fyp_feed`
Returns your personalized "For You" page feed — algorithmically recommended content from subscriptions + Substack's recommendation engine.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/reader/feed` |
| **Auth** | Required |
| **Params** | `limit: int = 20`, `since: str (ISO date) = None`, `summarize: bool = true` |
| **Returns** | Array of article objects (see Article Schema below) |
| **Dedup** | Yes — filters through SQLite cache |
| **Notes** | This is the actual FYP. Supports cursor-based pagination via `after` param in the API. The tool handles pagination internally up to `limit`. |

---

### `ss_get_subscription_feed`
Returns recent posts from ALL publications you subscribe to, sorted by publish date. This is the deterministic "everything my subscriptions posted" feed — no algorithm.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/reader/feed?filter=subscription` (or iterate `/api/v1/subscriptions` → per-publication `/api/v1/archive`) |
| **Auth** | Required |
| **Params** | `limit: int = 30`, `since: str (ISO date) = None`, `summarize: bool = true` |
| **Returns** | Array of article objects |
| **Dedup** | Yes |
| **Notes** | Prefer the `/reader/feed?filter=subscription` endpoint if it exists; otherwise fall back to iterating subscriptions + archive endpoints. Test both during development. |

---

### `ss_get_subscriptions`
Returns all publications the user follows, with metadata and RSS feed URLs.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/subscriptions` |
| **Auth** | Required |
| **Params** | None |
| **Returns** | Array of `{ name: str, subdomain: str, url: str, rss_url: str, author: str, description: str }` |
| **Dedup** | No (this is metadata, not content) |
| **Notes** | Useful for clients to discover what feeds are available. Each publication's RSS is at `{url}/feed`. |

---

### `ss_get_post_content`
Returns the full content of a single article by URL or post ID.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://{subdomain}.substack.com/api/v1/posts/{slug}` |
| **Auth** | Required (for paywalled content) |
| **Params** | `url: str` OR `post_id: str`, `summarize: bool = true` |
| **Returns** | Single article object with full content or summary |
| **Dedup** | No (this is an explicit lookup, not a feed scan) |
| **Notes** | Parse the URL to extract subdomain and slug. The API returns full HTML body in `body_html` field — convert to markdown server-side using a lightweight HTML-to-markdown converter (e.g., `markdownify`). Truncate raw content to 15K chars before summarization. |

---

### `ss_get_likes`
Returns posts the user has liked (hearted) on Substack.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/reader/feed/profile/{user_id}?types[]=like` |
| **Auth** | Required |
| **Params** | `limit: int = 20`, `since: str (ISO date) = None`, `summarize: bool = true` |
| **Returns** | Array of article objects |
| **Dedup** | Yes |
| **Notes** | `user_id` is obtained from `ss_auth_check` response and cached. Liked posts are high-signal — these are articles the user explicitly endorsed. Clients should weight these higher for content drafting. |

---

### `ss_get_restacks`
Returns posts the user has restacked (shared) on Substack.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/reader/feed/profile/{user_id}?types[]=restack` |
| **Auth** | Required |
| **Params** | `limit: int = 20`, `since: str (ISO date) = None`, `summarize: bool = true` |
| **Returns** | Array of article objects |
| **Dedup** | Yes |
| **Notes** | Restacked posts indicate the user's public endorsement — highest signal content. |

---

### `ss_get_notes_feed`
Returns recent Notes (Substack's short-form content) from the user's feed.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/reader/notes/feed` |
| **Auth** | Required |
| **Params** | `limit: int = 30`, `since: str (ISO date) = None` |
| **Returns** | Array of `{ id: str, author: str, content: str, timestamp: str, likes: int, restacks: int, comments: int, url: str }` |
| **Dedup** | Yes |
| **Notes** | Notes are short-form so no summarization needed — return raw content. High engagement notes (likes > 10 or restacks > 3) should be flagged with `high_signal: true`. |

---

### `ss_search_publications`
Search for Substack publications by keyword.

| Field | Value |
|---|---|
| **Method** | GET |
| **Endpoint** | `https://substack.com/api/v1/publication/search?query={query}` |
| **Auth** | Not required |
| **Params** | `query: str`, `limit: int = 10` |
| **Returns** | Array of `{ name: str, url: str, author: str, description: str, subscriber_count: int }` |
| **Dedup** | No |
| **Notes** | Useful for discovering new publications to follow. No auth required. |

---

## Article Schema (Standard Return Object)

Every feed tool returns articles in this normalized shape:

```json
{
  "id": "substack_post_12345",
  "title": "Why AI Agents Will Replace SaaS Dashboards",
  "author": "Packy McCormick",
  "publication": "Not Boring",
  "url": "https://www.notboring.co/p/why-ai-agents-will-replace-saas",
  "published_at": "2026-03-06T10:00:00Z",
  "platform": "substack",

  // Present when summarize=true (default)
  "summary": "McCormick argues that AI agents will collapse the SaaS dashboard paradigm...",
  "tags": ["AI-agents", "platform-strategy"],
  "relevance": 9,
  "key_quote": "The dashboard is dead. The agent is the interface.",
  "angle": "Connect to Veri's thesis — the creator OS IS the agent, not a dashboard",

  // Present when summarize=false
  "raw_content": "First 2000 chars of markdown...",

  // Always present
  "is_new": true,
  "source_feed": "fyp | subscription | likes | restacks | notes"
}
```

---

## Fly.io Deployment

### `fly.toml`
```toml
app = "ss-navigator"
primary_region = "lax"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8080"
  SQLITE_PATH = "/data/ss_navigator.db"

[mounts]
  source = "ss_data"
  destination = "/data"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.ports]]
    handlers = ["http"]
    port = 80
```

### Secrets (set via `fly secrets set`)
```bash
fly secrets set SUBSTACK_SESSION_COOKIE="your_substack_sid_value"
fly secrets set GOOGLE_AI_API_KEY="your_gemini_api_key"
fly secrets set MCP_AUTH_TOKEN="your_shared_secret_for_mcp_clients"
```

### Volume (persistent SQLite)
```bash
fly volumes create ss_data --region lax --size 1
```

---

## MCP Server Configuration

### For Perplexity Computer (remote MCP)
Add in Perplexity Settings → MCP Servers:
```json
{
  "name": "ss-navigator",
  "transport": "sse",
  "url": "https://ss-navigator.fly.dev/sse",
  "headers": {
    "Authorization": "Bearer {MCP_AUTH_TOKEN}"
  }
}
```

### For Claude Desktop (remote MCP)
Add in `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ss-navigator": {
      "transport": "sse",
      "url": "https://ss-navigator.fly.dev/sse",
      "headers": {
        "Authorization": "Bearer {MCP_AUTH_TOKEN}"
      }
    }
  }
}
```

---

## Rate Limiting & Safety

| Concern | Mitigation |
|---|---|
| Substack rate limiting | Max 1 request/second. Add `asyncio.sleep(1)` between paginated calls. Dedup cache prevents redundant fetches. |
| Session cookie expiry | `ss_auth_check` runs first in every workflow. Returns clear error with instructions to rotate. |
| Gemini Flash failures | Summarization is wrapped in try/except. On failure, return `raw_content` (truncated) instead. Never block on summarization failure. |
| MCP auth | Bearer token on all SSE connections. Reject unauthorized clients at transport layer. |
| Data volume | Default limits on all feed tools (20-30 items). `since` param prevents unbounded historical pulls. |

---

## Error Handling

All tools return errors in a standard shape:
```json
{
  "error": true,
  "code": "AUTH_EXPIRED | RATE_LIMITED | NOT_FOUND | SUMMARIZATION_FAILED | UNKNOWN",
  "message": "Human-readable description",
  "retry_after": null  // seconds, if rate limited
}
```

---

## Testing Plan

1. **Auth:** Call `ss_auth_check` → verify user info returns correctly
2. **FYP:** Call `ss_get_fyp_feed(limit=5)` → verify 5 unique articles with summaries
3. **Subscriptions:** Call `ss_get_subscriptions` → verify all followed publications appear
4. **Subscription feed:** Call `ss_get_subscription_feed(limit=5, since="2026-03-06")` → verify recent posts only
5. **Post content:** Call `ss_get_post_content(url="...")` → verify full summary returns
6. **Likes/Restacks:** Call both → verify liked/restacked posts return
7. **Notes:** Call `ss_get_notes_feed(limit=10)` → verify notes with engagement metrics
8. **Dedup:** Call `ss_get_fyp_feed` twice → verify second call returns 0 new articles
9. **Summarization off:** Call any feed with `summarize=false` → verify raw content returns
10. **Auth failure:** Set bad cookie → verify clear error from `ss_auth_check`

---

## Future Extensions (V2)

- **X/Twitter tool:** `ss_navigator` becomes the broader `content-navigator` MCP. Add `x_get_timeline`, `x_search` tools using RSSHub or Apify under the hood.
- **LinkedIn tool:** `li_get_feed` via RSSHub or scraping proxy.
- **Notion write-through:** Add `notion_write_article` tool so the MCP can write directly to Notion, removing that responsibility from the client entirely. The full pipeline becomes: MCP fetches → MCP summarizes → MCP writes to Notion → Client only reads summaries for drafting.
- **Webhook notifications:** Add a `/webhook` endpoint that fires a Slack/email notification when new high-relevance (score >= 8) articles are ingested.
- **Cookie auto-refresh:** Explore Playwright-based cookie rotation to avoid manual refresh every 30 days.

---

## Build Order

1. Scaffold MCP server with `mcp` SDK (Python), SSE transport
2. Implement auth layer (`SUBSTACK_SESSION_COOKIE` + `MCP_AUTH_TOKEN`)
3. Build `ss_auth_check` tool — test against live Substack
4. Build `ss_get_subscriptions` tool — simplest read, validates API access
5. Build `ss_get_fyp_feed` tool — the core feed, with pagination + dedup
6. Build `ss_get_subscription_feed` tool — deterministic feed
7. Add SQLite dedup cache layer across all feed tools
8. Add Gemini Flash-Lite summarization layer (optional param)
9. Build `ss_get_post_content` tool — single article lookup
10. Build `ss_get_likes` + `ss_get_restacks` tools — signal feeds
11. Build `ss_get_notes_feed` tool — short-form content
12. Build `ss_search_publications` tool — discovery
13. Deploy to Fly.io with volume + secrets
14. Configure in Perplexity Computer + Claude Desktop
15. Create Perplexity Computer daily scheduled task consuming the MCP
16. Create Claude Cowork daily scheduled task for drafting from Notion
