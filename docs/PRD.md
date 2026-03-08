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
- When true: article → truncate to 15K chars → Flash-Lite → structured JSON summary returned
- When false: raw content truncated to 2000 chars returned as `raw_content` field
- Failure mode: graceful fallback to raw content (2000 chars), never blocks
- Pre-summarization truncation: 15K chars max before sending to Gemini (controls cost/reliability)

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
  // Present when summarize=false
  "raw_content": "First 2000 chars of markdown...",

  // Always present
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

**Target: 100+ tests** (per D011, benchmarking memory-mcp's 131 test suite).
Structural model: Shortwave MCP pattern (91 tests).

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

## Build Order — Mini PRD Batches

Each batch follows the Sprint Protocol defined in CLAUDE.md: Plan → RED (tests) → CODE → GREEN (pass) → Checkpoint → Review → Approve.

---

### Batch 1 — Server Scaffold
**Scope:** Project setup, MCP server init, StreamableHTTP transport, health endpoint.
**Files to create:**
- `pyproject.toml` — dependencies and tool config
- `src/__init__.py`, `src/tools/__init__.py` — package init
- `src/server.py` — MCP server entry point (FastMCP)
- `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/fixtures/__init__.py`
- `tests/unit/test_server.py` — server + health endpoint tests

**Spec:**
- Health endpoint: `GET /health` → `200 OK` with `{"status": "ok", "version": "1.0.0"}`
- Transport: StreamableHTTP on port 8080 in production, stdio in dev
- Environment switch: `MCP_ENV=production` → StreamableHTTP, else stdio
- Server must initialize without error and register all tool stubs

**Tests:** Server starts, health returns 200, correct response body, transport selection by env var.
**Gate:** All tests pass, server starts, health endpoint responds 200.

---

### Batch 2 — Auth Layer
**Scope:** `ss_auth_check` tool, base HTTP client, cookie handling, user_id extraction and caching.
**Files to create:**
- `src/substack_client.py` — base Substack API client (httpx, cookie auth, rate limiting)
- `src/tools/auth.py` — auth check tool
- `tests/unit/test_auth.py` — auth test suite

**Spec:**
- Endpoint: `GET /api/v1/user/profile/self` (CORRECTED per D012)
- Cookie: send as `Cookie: substack.sid={value}; connect.sid={value}` (dual-name, single env var value)
- Params: none
- Returns: `{ valid: bool, user_id: str, name: str, email: str, expires_warning: bool }`
- Cache `user_id` from response — needed for likes/restacks endpoints in Batch 9
- Error cases: valid cookie → user profile, expired cookie → 401 → `AUTH_EXPIRED`, missing cookie → `AUTH_EXPIRED`

**Tests:** Valid cookie returns profile, expired returns AUTH_EXPIRED, missing cookie returns AUTH_EXPIRED, network error returns UNKNOWN, user_id is cached after successful auth.
**Gate:** Auth test suite passes + Live-test `/api/v1/user/profile/self` endpoint + Live-test FYP endpoint (`/api/v1/reader/feed`) per D012.

---

### Batch 3 — Subscriptions
**Scope:** `ss_get_subscriptions` tool — simplest authenticated read, validates API client works.
**Files to create:**
- `src/tools/subscriptions.py` — subscriptions tool
- `tests/unit/test_subscriptions.py`
**Depends on:** Batch 2 (`src/substack_client.py` — base HTTP client)

**Spec:**
- Endpoint: `GET /api/v1/subscriptions`
- Params: none
- Returns: `[{ name: str, subdomain: str, url: str, rss_url: str, author: str, description: str }]`
- No dedup (metadata, not content)

**Tests:** Returns valid subscription list, handles empty list, handles auth failure, rate limiting (1 req/sec).
**Gate:** Returns valid data with mocked responses.

---

### Batch 4 — Dedup Cache
**Scope:** SQLite dedup layer with schema versioning.
**Files to create:**
- `src/dedup.py` — SQLite dedup cache
- `tests/unit/test_dedup.py`
- `tests/integration/test_dedup_integration.py`

**Spec:**
- Schema: `seen_articles` table + 3 indexes (first_seen_at, source, status)
- Schema versioning: `schema_version` table with `INSERT OR REPLACE` idempotency (per D010)
- Operations: insert article, lookup by post ID, skip if exists, list by source_feed
- Migration: v1 creates initial schema

**Tests:** Insert new article, lookup returns existing, skip duplicate, concurrent access, migration creates tables, migration is idempotent, in-memory SQLite for test isolation.
**Gate:** All dedup tests pass.

---

### Batch 5 — Summarization
**Scope:** Gemini Flash-Lite summarization layer (must be before feed tools that default `summarize=true`).
**Files to create:**
- `src/summarizer.py` — Gemini summarizer
- `tests/unit/test_summarizer.py`

**Spec:**
- Model: Gemini 2.0 Flash-Lite via `google-genai` SDK
- Pre-summarization truncation: 15K chars max input to Gemini
- Output schema: `{ summary: str, tags: [str], relevance: int (1-10), key_quote: str, angle: str }`
- Fixed tag vocabulary: `creator-economy`, `AI-agents`, `monetization`, `platform-strategy`, `content-strategy`, `fundraising`, `product`, `engineering`, `culture`, `other`
- Fallback: on Gemini failure → return `raw_content` (first 2000 chars of markdown), never block
- Cost target: ~$0.0006/article

**Tests:** Successful summarization returns valid schema, tags are from fixed vocabulary, relevance is 1-10, content > 15K chars is truncated before sending, Gemini failure returns raw_content fallback, empty content handled gracefully.
**Gate:** Summary + fallback tests pass.

---

### Batch 6 — FYP Feed
**Scope:** `ss_get_fyp_feed` — core feed with pagination + dedup + summarization.
**Files to create:**
- `src/tools/fyp_feed.py`
- `tests/unit/test_fyp_feed.py`

**Spec:**
- Endpoint: `GET /api/v1/reader/feed` (UNVERIFIED — live-tested in Batch 2)
- Params: `limit: int = 20`, `since: str (ISO date) = None`, `summarize: bool = true`
- Pagination: cursor-based via `after` param in API response, handled internally up to `limit`
- Rate limiting: `asyncio.sleep(1)` between paginated requests
- Dedup: check `seen_articles` by post ID → skip if exists → insert new → return
- Returns (summarize=true): array of article objects with summary/tags/relevance/key_quote/angle
- Returns (summarize=false): array of article objects with `raw_content` (2000 chars)

**Tests:** Returns articles with dedup applied, skips seen articles, inserts new articles, pagination fetches multiple pages, since param filters by date, summarize=true returns summary fields, summarize=false returns raw_content, empty feed returns empty array.
**Gate:** Feed + dedup + summary tests pass.

---

### Batch 7 — Subscription Feed
**Scope:** `ss_get_subscription_feed` — deterministic feed with RSS fallback per D013.
**Files to create:**
- `src/tools/subscription_feed.py`
- `tests/unit/test_subscription_feed.py`

**Spec:**
- Primary endpoint: `GET /api/v1/reader/feed?filter=subscription` (UNVERIFIED — needs live test)
- Fallback (per D013): if primary endpoint fails → iterate subscriptions → fetch per-publication RSS feeds
- RSS feeds: `{subdomain}.substack.com/feed` (auth-free, rate-limit-free)
- Params: `limit: int = 30`, `since: str (ISO date) = None`, `summarize: bool = true`
- Dedup: yes
- Note: RSS fallback cannot access paywalled content — only free posts

**Tests:** Primary API returns articles, primary API failure triggers RSS fallback, RSS returns articles with dedup, since param filters, summarization applied, empty feed handled.
**Gate:** Feed tests pass + RSS fallback tests pass.

---

### Batch 8 — Post Content
**Scope:** `ss_get_post_content` — single article lookup with URL parsing.
**Files to create:**
- `src/tools/post_content.py`
- `tests/unit/test_post_content.py`

**Spec:**
- Endpoint: `GET https://{subdomain}.substack.com/api/v1/posts/{slug}`
- Params: `url: str` OR `post_id: str`, `summarize: bool = true`
- URL parsing: extract subdomain and slug from Substack URL
- HTML processing: `body_html` → `markdownify` → markdown
- Pre-summarization truncation: 15K chars before sending to Gemini
- Dedup exception: does NOT skip if already seen, but DOES insert into `seen_articles`

**Tests:** Returns full article by URL, returns by post_id, URL parsing extracts subdomain/slug correctly, HTML converts to markdown, content > 15K truncated before summarization, inserts into seen_articles but doesn't skip existing, handles missing post (404 → NOT_FOUND).
**Gate:** Content tests pass.

---

### Batch 9 — Likes + Restacks
**Scope:** `ss_get_likes` + `ss_get_restacks` — signal feeds (high-value content).
**Files to create:**
- `src/tools/likes.py`, `src/tools/restacks.py`
- `tests/unit/test_likes.py`, `tests/unit/test_restacks.py`

**Spec:**
- Likes endpoint: `GET /api/v1/reader/feed/profile/{user_id}?types[]=like`
- Restacks endpoint: `GET /api/v1/reader/feed/profile/{user_id}?types[]=restack`
- `user_id`: from cached `ss_auth_check` response (Batch 2)
- Params (both): `limit: int = 20`, `since: str (ISO date) = None`, `summarize: bool = true`
- Dedup: yes
- Signal weighting: liked posts = high signal, restacked posts = highest signal

**Tests:** Returns liked/restacked articles, uses cached user_id, fails gracefully if user_id not cached, dedup applied, since param filters, summarization applied.
**Gate:** Signal feed tests pass.

---

### Batch 10 — Notes Feed
**Scope:** `ss_get_notes_feed` — short-form content with distinct schema.
**Files to create:**
- `src/tools/notes_feed.py`
- `tests/unit/test_notes_feed.py`

**Spec:**
- Endpoint: `GET /api/v1/notes?cursor={cursor}` (CORRECTED per D012, NOT `/reader/notes/feed`)
- Params: `limit: int = 30`, `since: str (ISO date) = None`
- No `summarize` param — Notes are short-form, return raw content always
- Returns (distinct schema, NOT standard article object):
  ```json
  { "id": "str", "author": "str", "content": "str", "timestamp": "str",
    "likes": "int", "restacks": "int", "comments": "int", "url": "str",
    "high_signal": "bool" }
  ```
- High-signal flagging: `likes > 10` OR `restacks > 3` → `high_signal: true`
- Dedup: yes (by note ID)

**Tests:** Returns notes with correct schema (not article schema), high_signal flagged correctly, cursor pagination works, dedup applied, since param filters, empty feed handled.
**Gate:** Notes tests pass.

---

### Batch 11 — Search
**Scope:** `ss_search_publications` — publication discovery (no auth required).
**Files to create:**
- `src/tools/search.py`
- `tests/unit/test_search.py`

**Spec:**
- Endpoint: `GET /api/v1/publication/search?query={q}` (CONFIRMED, no auth needed)
- Params: `query: str`, `limit: int = 10`
- Returns (distinct schema):
  ```json
  { "name": "str", "url": "str", "author": "str", "description": "str", "subscriber_count": "int" }
  ```
- No auth, no dedup

**Tests:** Returns publications matching query, respects limit, handles empty results, handles special characters in query.
**Gate:** Search tests pass.

---

### Batch 12 — Navigator
**Scope:** `ss_navigator` — START tool with domain knowledge and tool discovery.
**Files to create:**
- `src/tools/navigator.py`
- `tests/unit/test_navigator.py`

**Spec:**
- No auth, no dedup
- Domain knowledge: available tools, Substack API quirks, auth rotation procedure, feed semantics
- Workflow guides: daily ingestion (Perplexity 7am), content drafting (Claude 9am)
- Tool discovery: list all 10 tools with descriptions and suggested call order

**Tests:** Returns valid navigator response, includes all 10 tool names, includes auth rotation instructions, includes workflow guides.
**Gate:** Navigator tests pass.

---

### Batch 13 — Deploy
**Scope:** Fly.io deployment and client configuration.
**Files to create:**
- `Dockerfile` (Python 3.12-slim, NOT Alpine — per memory-mcp pattern)
- `fly.toml` (app: ss-navigator, region: lax, port: 8080, volume: ss_data 1GB)

**Spec:**
- Secrets: `SUBSTACK_SESSION_COOKIE`, `GOOGLE_AI_API_KEY`, `MCP_AUTH_TOKEN`
- StreamableHTTP transport URL for clients
- Post-deploy verification: (1) `fly status`, (2) health endpoint, (3) smoke test — all 3 must pass

**Tests:** N/A (deployment verification is manual).
**Gate:** All 3 post-deploy checks pass.

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
