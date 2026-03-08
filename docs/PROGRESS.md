# Progress Log: substack-mcp

## Status: Sprint 2-3 APPROVED
**Last Updated:** 2026-03-08

---

## Session 1 — March 7, 2026 (Scaffolding)

### Completed
- [x] Created GitHub repo: `optionshift/substack-mcp` (public)
- [x] Initialized local git repo with `main` branch
- [x] Read and analyzed spec (`shortwave-mcp-spec.md`)
- [x] Parsed subscription feeds (57 publications from OPML export)
- [x] Reviewed memory-mcp server patterns (dedup tables, vector search, confidence scoring)
- [x] Reviewed quickbooks-mcp server patterns (STRAP CRUD, navigator, suites, CDC)
- [x] Reviewed shortwave-mcp server patterns (17 tools, 91 tests, safety gates, Vitest)
- [x] Scaffolded PRD v1.0
- [x] Created progress log
- [x] Created decisions log
- [x] Researched Substack API endpoints for verification

### Also Completed (after agents returned)
- [x] Created empty project directories (src/tools/, tests/unit/, tests/integration/, tests/fixtures/) — no __init__.py files yet
- [x] Created CLAUDE.md with all project rules (agent teams, caching, TDD, deployment)
- [x] Created .gitignore
- [x] Verified Substack API endpoints via research agent (2 corrections found, 1 unverified)
- [x] Updated PRD + CLAUDE.md with corrected endpoints
- [x] Added decisions D009-D013 (StreamableHTTP, migrations, test target, endpoint corrections, RSS fallback)

### Pending (from Session 1 — completed in Sprints 1-3)
- [x] Create pyproject.toml with dependencies (Batch 1)
- [x] Implement Batch 1 (server scaffold + StreamableHTTP transport)
- [x] Begin TDD cycle (Sprint 1)
- [ ] Live-test unverified FYP endpoint (`/api/v1/reader/feed` vs `/api/v1/comment/feed`) — still pending

### Findings from MCP Server Pattern Review (3 agents)

**Memory MCP (131 tests, 11 tools, 7 SQLite tables):**
- Location: `/Users/mileslozano/mcp-servers/os-tools/memory-mcp-server`
- TypeScript, `@modelcontextprotocol/sdk@^1.26.0`, Vitest
- StreamableHTTP transport in production (not SSE) — adopted for this project (D009)
- Singleton DB pattern with poisoned-state prevention
- Schema versioning: non-transactional migrations v1→v2→v3 — adopted (D010)
- Vector search: Voyage-4 embeddings + LIKE fallback
- Voice pattern dedup: exact match → increment frequency
- 7 tables: memories, memory_embeddings, voice_patterns, draft_diffs, agent_decisions, safety_log, schema_version
- Fly.io LAX, 1GB volume, Dockerfile (node:20-slim, NOT Alpine)

**QuickBooks MCP (20 tools, 0 tests):**
- Location: `/Users/mileslozano/mcp-servers/os-tools/quickbooks-mcp`
- TypeScript, `@modelcontextprotocol/sdk@^1.20.1`, no test framework
- "DUMB tools" (13 CRUD wrappers) + "SMART tools" (6 analysis)
- In-memory caching with TTL (1hr customers/vendors, 24hr classes/accounts)
- Error hierarchy: QBError → QBAuthError, QBRateLimitError, QBValidationError, QBNotFoundError
- Exponential backoff retry (1s, 2s, 4s, max 3 attempts)
- OAuth 2.0 with auto-refresh, token persisted to .env + Claude Desktop config + Shortwave config
- Local stdio transport only (no Fly.io)

**Substack API Research (verified with real evidence):**
- 2 endpoint paths WRONG in spec (corrected: /user/me → /user/profile/self, /reader/notes/feed → /notes)
- 1 endpoint UNVERIFIED (FYP feed — needs live testing)
- Cookie auth CONFIRMED (both substack.sid and connect.sid work)
- Cookie expiry MONTHS (not 30 days as spec said)
- No official rate limits from Substack
- Publication search CONFIRMED (no auth needed)
- Likes/restacks profile endpoints CONFIRMED
- 3 existing Substack MCP servers found — all public-only, none authenticated
- RSS fallback available for all 57 subscriptions

---

## Batch Tracking

| Batch | Status | Tests | Notes |
|---|---|---|---|
| 1 — Scaffold | Complete | 11 | pyproject.toml, src/server.py, __init__.py files, test_server.py. Sprint review: registered MCP tools. |
| 2 — Auth | Complete | 13 | Live-test deferred (cookie empty). Sprint review: +3 tests (500 error, env var wiring). Response buffering fix. |
| 3 — Subscriptions | Complete | 9 | Sprint review: +2 tests (custom_domain, rate limiting). custom_domain URL fix. |
| 4 — Dedup Cache | Complete | 15 | Sprint review: exists() thread lock fix, list_by_feed() thread lock fix. |
| 5 — Summarization | Complete | 13 | Gemini Flash-Lite via google-genai, 15K truncation, tag validation, relevance clamping, graceful fallback |
| 6 — FYP Feed | Complete | 10 | Endpoint, dedup, since filter, summarize toggle, auth errors. Registered in server.py. |
| 7 — Sub Feed | Complete | 8 | Primary API + RSS fallback (D013), dedup, since filter, summarize. Registered in server.py. |
| 8 — Post Content | Complete | 9 | URL parsing, HTML→markdown, dedup exception (insert but don't skip), 404 handling. Registered in server.py. |
| 9 — Likes/Restacks | Complete | 11 | Uses cached user_id, dedup, since filter, summarize. Both registered in server.py. |
| 10 — Notes Feed | Complete | 7 | Distinct schema, high_signal flagging (likes>10 OR restacks>3), dedup by note ID. Registered in server.py. |
| 11 — Search | Complete | 6 | No auth, no dedup, limit support, special chars handled. Registered in server.py. |
| 12 — Navigator | Complete | 9 | All 10 tools listed, workflow guides, auth rotation instructions, API quirks. Registered in server.py. |
| 13 — Deploy | Complete | 4 | Dockerfile, fly.toml, bearer auth middleware, __main__.py. Deployed to substack-mcp.fly.dev. |

---

## Sprint 1 Review Findings

1. **FIXED** — `substack_client.py`: httpx response not buffered before AsyncClient closes. Added `await response.aread()` inside context manager.
2. **FIXED** — `dedup.py`: `exists()` and `list_by_feed()` accessed `self.conn` without `self._lock`. Added lock acquisition.
3. **FIXED** — `substack_client.py`: Rate limiting absent. Added 1 req/sec enforcement via `asyncio.sleep` in `SubstackClient.get()`.
4. **FIXED** — `server.py`: No MCP tools registered. Added `@mcp.tool()` decorators for `ss_auth_check` and `ss_get_subscriptions`.
5. **FIXED** — `subscriptions.py`: `custom_domain` ignored, always generated `.substack.com` URLs. Now uses `custom_domain` when present.
6. **SKIPPED** — Duplicate `get_client()` wrapper in tool files. Intentional for test mocking (`unittest.mock.patch` targets).
7. **FIXED** — Added test for non-401 HTTP error codes (500) in auth — `test_server_error_returns_unknown`.
8. **FIXED** — Added tests for `create_client()` env var wiring — `test_create_client_with_env_var`, `test_create_client_without_env_var`.

---

## Sprint 2-3 Review Findings

1. **FIXED** — `post_content.py:58`: Dead branch `subdomain.endswith(".substack.com")` always false after `parse_substack_url` strips it. Simplified to `"." not in subdomain`.
2. **FIXED** — `subscription_feed.py:79`: `import hashlib` inside function body. Moved to top-level imports.
3. **FIXED** — `subscription_feed.py:83`: RSS dedup ID `substack_post_rss_xxx` uses guid-based hash. Changed to URL-based hash for more stable IDs.
4. **FIXED** — `summarizer.py:45`: Sync `client.models.generate_content()` blocked async event loop. Changed to `await client.aio.models.generate_content()`.
5. **FIXED** — `post_content.py:45`: `post_id` param accepted but non-functional (PRD spec, but no API path to look up by ID alone). Removed param from signature and server.py registration.
6. **FIXED** — `subscription_feed.py:102-115`: No rate limiting in RSS fallback loop. Added `asyncio.sleep(1)` between RSS requests.
7. **DEFERRED** — FYP/Notes cursor pagination: PRD specifies cursor-based pagination but API response format is UNVERIFIED (D012). Will implement when live-tested.
8. **SKIPPED** — Duplicate `_parse_article` across feed tools. Intentional per Sprint 1 pattern — each tool file is self-contained for test mocking.

---

## Sprint 1 Summary

**APPROVED** — 2026-03-08
**Total tests:** 48 passing, 0 failing
**Batches completed:** 1-4 (Scaffold, Auth, Subscriptions, Dedup Cache)
**Sprint review:** 8 findings total → 7 fixed, 1 skipped (intentional design)
**Final gate:** PASS (all 4 criteria verified by code-review agent)

---

## Sprint 2-3 Summary

**APPROVED** — 2026-03-08
**Total tests:** 121 passing, 0 failing
**Batches completed:** 5-12 (Summarization, FYP Feed, Subscription Feed, Post Content, Likes/Restacks, Notes Feed, Search, Navigator)
**Sprint review:** 8 findings → 6 fixed, 1 deferred (pagination — UNVERIFIED endpoints), 1 skipped (intentional design)
**Final gate:** PASS (all 6 criteria verified by code-review agent)
**Files created:** 16 (8 source, 8 test)
**Tools registered:** All 10 tools registered in server.py with `@mcp.tool()` decorators

---

## HAR Analysis Review — March 8, 2026

### Source
User captured two HAR files from live substack.com browsing:
- `substack.com.har` — initial navigation (feeds, subscriptions, profile)
- `substack.com-additional-clicks-and-nav.har.har` — deeper navigation (inbox, explore, publisher dashboard)

### Critical Fixes Applied (D014)

| # | Fix | Files Changed |
|---|---|---|
| 1 | FYP feed: added `tab=for-you&type=base` params | `src/tools/fyp_feed.py`, `tests/unit/test_fyp_feed.py` |
| 2 | FYP/sub feed: changed response parsing from `posts[]` to `items[].post` | `src/tools/fyp_feed.py`, `src/tools/subscription_feed.py` + tests |
| 3 | Subscription feed: fixed params from `filter=subscription` to `tab=subscribed&type=secondary` | `src/tools/subscription_feed.py`, `tests/unit/test_subscription_feed.py` |
| 4 | Subscriptions: endpoint `/api/v1/subscriptions` → `/api/v1/subscriptions/page` | `src/tools/subscriptions.py`, `tests/unit/test_subscriptions.py` |
| 5 | Subscriptions: response parsing from flat array to nested `{subscriptions[], publications[]}` | Same as above |
| 6 | Cookie: removed `connect.sid` (only `substack.sid` observed in HAR) | `src/substack_client.py`, `tests/unit/test_auth.py` |
| 7 | httpx: added `follow_redirects=True` to handle 301 redirects | `src/substack_client.py` |
| 8 | Navigator: updated api_quirks with HAR-verified endpoint info | `src/tools/navigator.py` |

### Live API Test Results
| Endpoint | Status | Action |
|---|---|---|
| `/api/v1/user/profile/self` | **200 OK** — returns full profile (id, name, handle, bio) | Auth check CONFIRMED working |
| `/api/v1/notes` | **404 Not Found** | Rewrote to use reader/feed filtered for comments |
| `/api/v1/reader/feed?tab=for-you&type=base` | **200 OK** | FYP CONFIRMED |
| `/api/v1/subscriptions/page` | **200 OK** | Subscriptions CONFIRMED |
| `/api/v1/activity/unread` | **200 OK** | Lightweight auth check available |
| `/api/v1/reader/feed/profile/{id}?types[]=like` | **200 OK** — uses items[] format | Fixed parsing |
| `/api/v1/reader/feed/profile/{id}?types[]=restack` | **200 OK** — uses items[] format | Fixed parsing |

### Additional Fixes from Live Testing
| # | Fix | Files Changed |
|---|---|---|
| 9 | Likes: parse items[] (posts + notes mixed) instead of posts[] | `src/tools/likes.py`, `tests/unit/test_likes.py` |
| 10 | Restacks: same items[] fix | `src/tools/restacks.py`, `tests/unit/test_restacks.py` |
| 11 | Notes: rewrote from /api/v1/notes (404) to reader/feed filtered for comments | `src/tools/notes_feed.py`, `tests/unit/test_notes_feed.py` |

### Test Results
**121 tests passing, 0 failures** — all mock responses updated to match HAR-verified shapes

### Key HAR Findings (logged, not yet implemented)
- `GET /api/v1/posts/by-id/{postId}` — alternative to slug-based post retrieval
- `GET /api/v1/reader/posts?inboxType={paid|saved|seen}` — filtered reading lists
- `GET /api/v1/activity/unread` — lightweight auth validation endpoint
- Feed pagination: base64-encoded opaque cursors with session_id, timestamps, scores
- Cookie expiry confirmed: ~90 days
- User ID: `383926424`

---

## Batch 13 — Deploy (March 8, 2026)

### Deployment Details
- **App:** `substack-mcp` on Fly.io
- **URL:** `https://substack-mcp.fly.dev`
- **MCP endpoint:** `https://substack-mcp.fly.dev/mcp/`
- **Region:** LAX
- **Volume:** ss_data (1GB) → /data
- **Image:** python:3.12-slim, 53MB

### Auth
- Bearer token middleware (Starlette `BaseHTTPMiddleware`)
- Accepts: `Authorization: Bearer <key>` header OR `?key=<key>` query param
- Health endpoint `/health` bypasses auth
- FastMCP's built-in `TokenVerifier` requires full OAuth `AuthSettings` — not used

### Secrets (1Password vault: substack-mcp)
- `SUBSTACK_SESSION_COOKIE` — session cookie (~90 day expiry)
- `GOOGLE_AI_API_KEY` — Gemini Flash-Lite for summarization
- `MCP_API_KEY` — bearer token for server auth

### Post-Deploy Verification
| Check | Result |
|---|---|
| `fly status` | started, 1 passing health check |
| `GET /health` | `{"status":"ok","version":"1.0.0"}` |
| Auth: no key | 401 |
| Auth: wrong key | 401 |
| Auth: valid key (header) | 307 (MCP redirect) |
| Auth: valid key (query) | 307 (MCP redirect) |

### Files Created
- `Dockerfile` — python:3.12-slim multi-stage build
- `fly.toml` — app config, health checks, volume mount
- `src/__main__.py` — uvicorn entrypoint for production

### Test Results
**125 tests passing, 0 failures** (4 new auth tests added)
