# PRD: substack-mcp (ss-navigator)
## Substack Content Navigator MCP Server
### Version 1.0 — March 7, 2026

---

## Problem Statement

Option Shift's content engine requires daily ingestion of Substack articles from 57+ subscriptions to fuel LinkedIn posts, Substack Notes, and long-form blog content. Today this is manual — browse Substack, save interesting articles, summarize later. This creates a bottleneck: content ideation depends on Miles remembering to read, and high-signal articles get lost in the feed.

## Solution

A remote MCP server (`ss-navigator`) hosted on Fly.io that provides authenticated, structured access to Substack's undocumented API. The server handles:
- **Feed ingestion** — FYP, subscriptions, likes, restacks, notes
- **Dedup** — SQLite cache prevents re-processing (pattern from memory-mcp)
- **Summarization** — Gemini Flash-Lite compresses articles server-side
- **Discovery** — Publication search for new sources

**Primary consumers:**
- Perplexity Computer (daily 7am scheduled task — ingestion)
- Claude Cowork (daily 9am scheduled task — drafting from Notion)

---

## Architecture

```
MCP Clients (Perplexity Computer, Claude Cowork)
    │ StreamableHTTP (remote, production)
    │ stdio (local dev)
    ▼
ss-navigator MCP Server (Fly.io, Python 3.12+)
    ├── Substack API Client (httpx, cookie auth)
    ├── SQLite Dedup Cache (Fly Volume, persistent)
    ├── Gemini Flash-Lite Summarizer (optional, server-side)
    └── Navigator Tool (domain knowledge, tool discovery)
```

> **Transport Note:** Uses StreamableHTTP (not SSE) per D009. This matches the memory-mcp production pattern and is the current MCP standard as of late 2025. SSE transport is being superseded.

### Technology Stack
- **Runtime:** Python 3.12+
- **MCP SDK:** `mcp[server]` (FastMCP pattern)
- **HTTP Client:** `httpx` (async)
- **Summarization:** `google-genai` (Gemini 2.0 Flash-Lite)
- **Database:** SQLite3 (Fly Volume mount at `/data/ss_navigator.db`)
- **HTML Processing:** `markdownify` (HTML → Markdown)
- **Testing:** `pytest` + `pytest-asyncio` (TDD mandatory)
- **Deployment:** Fly.io (LAX region, StreamableHTTP transport)

---

## Tool Suite (10 tools)

### Navigation Suite
| Tool | Purpose | Auth | Dedup |
|---|---|---|---|
| `ss_navigator` | START tool — discover tools, domain knowledge, workflow guides | No | No |
| `ss_auth_check` | Validate session cookie (endpoint: `/api/v1/user/profile/self`) | Yes | No |

### Feed Suite
| Tool | Purpose | Auth | Dedup |
|---|---|---|---|
| `ss_get_fyp_feed` | Personalized "For You" feed (algorithmic) | Yes | Yes |
| `ss_get_subscription_feed` | All subscription posts (deterministic, by date) | Yes | Yes |
| `ss_get_notes_feed` | Short-form Notes feed (endpoint: `/api/v1/notes`, NOT `/reader/notes/feed`) | Yes | Yes |

### Signal Suite
| Tool | Purpose | Auth | Dedup |
|---|---|---|---|
| `ss_get_likes` | User's liked/hearted posts (high signal) | Yes | Yes |
| `ss_get_restacks` | User's restacked/shared posts (highest signal) | Yes | Yes |

### Content Suite
| Tool | Purpose | Auth | Dedup |
|---|---|---|---|
| `ss_get_post_content` | Full article by URL/ID (explicit lookup) | Yes | No |
| `ss_get_subscriptions` | List all followed publications + metadata | Yes | No |
| `ss_search_publications` | Search for new publications by keyword | No | No |

---

## Data Layer: SQLite Dedup Cache

**Pattern:** Borrowed from memory-mcp's dedup tables. Server-side dedup — clients never see duplicates.

```sql
CREATE TABLE IF NOT EXISTS seen_articles (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    status TEXT DEFAULT 'new',
    source_feed TEXT,
    relevance_score INTEGER
);

CREATE INDEX idx_seen_articles_first_seen ON seen_articles(first_seen_at);
CREATE INDEX idx_seen_articles_source ON seen_articles(source);
CREATE INDEX idx_seen_articles_status ON seen_articles(status);
```

**Dedup logic:** Before returning any article from any feed tool, check `seen_articles` by post ID. If exists → skip. If new → insert and return.

**Exception:** `ss_get_post_content` (explicit single-article lookup) does NOT skip if already seen, but DOES insert into `seen_articles` to mark the article as processed. This prevents the article from appearing in subsequent feed pulls while still returning the content the user explicitly requested.

---

## Summarization Layer

**Model:** Gemini 2.0 Flash-Lite via `google-genai` SDK
**Cost:** ~$0.0006/article (5K input, 200 output tokens)
**Behavior:**
- Default `summarize=true` on all feed tools
- When true: article → Flash-Lite → structured JSON summary returned
- When false: raw content truncated to 2000 chars returned
- Failure mode: graceful fallback to raw content, never blocks

**Summary schema:**
```json
{
  "summary": "2-3 sentence key argument",
  "tags": ["creator-economy", "AI-agents"],
  "relevance": 8,
  "key_quote": "One notable sentence",
  "angle": "Content hook for LinkedIn/Notes"
}
```

**Fixed tag vocabulary:** `creator-economy`, `AI-agents`, `monetization`, `platform-strategy`, `content-strategy`, `fundraising`, `product`, `engineering`, `culture`, `other`

---

## Authentication

### Substack Auth
- Session cookie: `substack.sid` or `connect.sid` (both observed in the wild)
- Implementation must try both cookie names: send as `Cookie: substack.sid={value}; connect.sid={value}`
- Stored as `SUBSTACK_SESSION_COOKIE` env var on Fly.io (single value, sent under both names)
- Expiry: months if user does not log out (per D012; original spec said ~30 days, research found this was wrong)
- `ss_auth_check` validates before any workflow — clear error returned on expiry
- Cookie rotation procedure: (1) Log in to substack.com in browser, (2) DevTools → Application → Cookies → copy `substack.sid` or `connect.sid`, (3) `fly secrets set SUBSTACK_SESSION_COOKIE="new_value"`

### MCP Transport Auth
- Bearer token on all StreamableHTTP connections (`MCP_AUTH_TOKEN`)
- Reject unauthorized clients at transport layer

---

## Article Schema (Standard Return Object)

```json
{
  "id": "substack_post_12345",
  "title": "Article Title",
  "author": "Author Name",
  "publication": "Publication Name",
  "url": "https://...",
  "published_at": "2026-03-06T10:00:00Z",
  "platform": "substack",
  "summary": "...",
  "tags": ["..."],
  "relevance": 9,
  "key_quote": "...",
  "angle": "...",
  "is_new": true,
  "source_feed": "fyp | subscription | likes | restacks | notes"
}
```

---

## Error Handling

Standard error shape across all tools (pattern from QB/Shortwave MCP):
```json
{
  "error": true,
  "code": "AUTH_EXPIRED | RATE_LIMITED | NOT_FOUND | SUMMARIZATION_FAILED | UNKNOWN",
  "message": "Human-readable description",
  "retry_after": null
}
```

---

## Rate Limiting & Safety

| Concern | Mitigation |
|---|---|
| Substack rate limiting | Max 1 req/sec, `asyncio.sleep(1)` between paginated calls |
| Session cookie expiry | `ss_auth_check` first in every workflow |
| Gemini failures | try/except → fallback to raw_content |
| MCP auth | Bearer token on StreamableHTTP, reject unauthorized |
| Data volume | Default limits 20-30, `since` param bounds history |

---

## Testing Strategy (TDD Mandatory)

Following Shortwave MCP pattern (91 tests):

### Test Categories
1. **Unit tests** — Each tool function in isolation with mocked HTTP responses
2. **Dedup tests** — Verify SQLite cache insertion, lookup, and skip behavior
3. **Summarization tests** — Mock Gemini calls, verify schema, test fallback
4. **Auth tests** — Valid cookie, expired cookie, missing cookie
5. **Integration tests** — End-to-end tool calls against mock Substack responses
6. **Error tests** — Rate limiting, network failures, malformed responses

### Test Infrastructure
- `pytest` + `pytest-asyncio`
- `httpx` mock transport for Substack API responses
- Fixtures for sample article HTML, feed JSON responses
- Temporary SQLite databases for dedup tests

---

## Deployment

### Fly.io Configuration
- App name: `ss-navigator`
- Region: `lax`
- Volume: `ss_data` (1GB, persistent SQLite)
- Port: 8080

### Secrets
```
SUBSTACK_SESSION_COOKIE — Substack session cookie
GOOGLE_AI_API_KEY — Gemini Flash-Lite API key
MCP_AUTH_TOKEN — Shared secret for MCP client auth
```

### Post-Deploy Verification (mandatory)
1. `fly status` → confirm deploy succeeded
2. Hit health endpoint → verify response
3. Run smoke test against production
4. All 3 must pass before marking deploy done

---

## Build Order

| Batch | Tasks | Gate |
|---|---|---|
| 1 | Scaffold project, MCP server init, StreamableHTTP transport, health endpoint (`GET /health` → 200 OK) | Tests pass, server starts, health endpoint responds |
| 2 | Auth layer (`ss_auth_check`), cookie handling | Auth test suite passes |
| 3 | `ss_get_subscriptions` — simplest read, validates API | Returns valid data |
| 4 | SQLite dedup cache layer | Dedup tests pass |
| 5 | Gemini Flash-Lite summarization layer (must be before feed tools that default `summarize=true`) | Summary + fallback tests pass |
| 6 | `ss_get_fyp_feed` — core feed with pagination + dedup + summarization | Feed + dedup + summary tests pass |
| 7 | `ss_get_subscription_feed` — deterministic feed | Feed tests pass |
| 8 | `ss_get_post_content` — single article lookup | Content tests pass |
| 9 | `ss_get_likes` + `ss_get_restacks` — signal feeds | Signal feed tests pass |
| 10 | `ss_get_notes_feed` — short-form content | Notes tests pass |
| 11 | `ss_search_publications` — discovery tool | Search tests pass |
| 12 | `ss_navigator` — START tool with domain knowledge | Navigator tests pass |
| 13 | Deploy to Fly.io, configure clients | Post-deploy verification passes |

---

## V2 Extensions (Future)

- X/Twitter integration (`content-navigator` expansion)
- LinkedIn feed via RSSHub
- Notion write-through (MCP → Notion, client reads only)
- Webhook notifications for high-relevance articles (score >= 8)
- Playwright-based cookie auto-refresh

---

## Success Metrics

- Daily ingestion of 20-50 new articles with zero duplicates
- < 3 seconds per feed pull (excluding summarization)
- < $0.05/day Gemini costs
- Cookie rotation alerts surfaced before auth failure blocks workflows
- Zero manual browsing required for content ideation
