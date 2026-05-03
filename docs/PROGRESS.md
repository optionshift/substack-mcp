# Progress Log: substack-mcp

## Status: Sprint 7 Batch 5 — DONE
**Last Updated:** 2026-05-02

---

## Sprint 7 — Substack Writes + Voice Gate (May 2026)

### Batch 5: Note drafts + scheduling + follow — DONE 2026-05-02
- 7 tools, ~22 new tests
- All HAR-confirmed via may2capture.har
- Test count: 314
- Live at https://ss-nav-3950b79a5cc7.fly.dev/mcp
- Sprint 7 ships 24 new tools total (28 → 43 active tools)
- New: ss_create_note_draft, ss_schedule_note, ss_list_note_drafts, ss_cancel_scheduled_note, ss_follow, ss_unfollow, ss_list_following
- Voice gate on create_note_draft + schedule_note (force=True bypass)

### Batch 4: Article drafts + post scheduling — DONE 2026-05-02
- 8 tools, ~23 new tests
- Test count: 292 (up from 269)
- Live at https://ss-nav-3950b79a5cc7.fly.dev/mcp
- New: ss_list_drafts, ss_get_draft, ss_delete_draft, ss_create_draft, ss_update_draft, ss_publish_draft, ss_schedule_post, ss_unschedule_post
- Helper: src/tools/auth.py exposes `get_my_publication_subdomain()` and `auth_check()` now returns `publications`
- Voice gate on create_draft + update_draft (force=True bypass)
- Subdomain-scoped at `https://{publication}.substack.com/api/v1/drafts...`

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
| 13 — Deploy | Complete | — | Dockerfile, fly.toml, __main__.py. Deployed to ss-nav-3950b79a5cc7.fly.dev. No auth (obscure URL). |
| 14 — Like | Complete | 8 | First write op. POST /post/{id}/reaction + /comment/{id}/reaction. Added post() to SubstackClient. 129 total tests. |
| 15 — Activity Feed | Complete | 16 | HAR-verified endpoint. 3 filters (all, replies-and-mentions, restacks). Enriched senders/posts/comments/pubs. 145 total tests. |
| 16 — Content Architecture | Complete | 9 | Two-tier pattern: feeds return summaries with hint, ss_get_post_content returns full markdown. Removed 2000-char truncation. 154 total tests. |
| 17 — Article Search | Complete | 17 | New ss_search_posts tool via /api/v1/post/search. Time/scope filters, pagination, dedup, input validation. 171 total tests. |
| 18 — Sprint Review | Complete | — | Code review (6 findings, 5 fixed). Summarizer key allowlist, notes hint fix, search validation. |
| 19 — Trending Search | Complete | 11 | ss_search_trending via /api/v1/recent/search. Recency + engagement scoring. 182 total tests. |
| 20 — My Posts | Complete | 9 | ss_get_my_posts via subdomain-scoped /post_management/published. Pagination. 191 total tests. |
| 21 — Mark Seen | Complete | 9 | ss_mark_seen via POST /reader/feed/{id}/seen. Posts + notes. 200 total tests. |
| 22 — Sprint Review | Complete | — | Deploy, docs v1.4, decisions D019-D021. |
| 23 — Saved Posts | Complete | 20 | ss_get_saved_posts via /api/v1/reader/posts?inboxType={saved\|seen\|paid}. Server-side joins, read_progress. 221 total tests. |
| 24 — Save/Unsave | Complete | 14 | ss_save_post + ss_unsave_post. POST + DELETE /api/v1/posts/saved. Added delete() to SubstackClient. 235 total tests. |
| 25 — Sprint Review | Complete | 4 | Code review (5 findings fixed). Deploy v1.5. Docs updated. 240 total tests. |

---

## Sprint 6 — Saved Posts & Playbook Pipeline (March 17, 2026)

### Problem
User saves Substack articles but never processes them into playbooks for prompting, GTM, VC strategy, etc. Need tools to retrieve saved articles and manage the saved queue.

### Batch 23 — Saved Posts Tool
- New `ss_get_saved_posts` using `GET /api/v1/reader/posts?inboxType={saved|seen|paid}`
- Server-side joins: posts[] + publications[] + savedPosts[] + inboxItems[]
- Includes `saved_at` timestamp and `read_progress` from inbox metadata
- `inbox_type` filter: saved (bookmarks), seen (already read), paid (premium)
- Dedup: insert but don't skip (saved posts always returned)
- `since` filter uses `saved_at` for saved type, `post_date` for seen/paid

### Batch 24 — Save/Unsave Tools
- New `ss_save_post`: `POST /api/v1/posts/saved` with `{"post_id": N}`
- New `ss_unsave_post`: `DELETE /api/v1/posts/saved` with `{"post_id": N}`
- Added `delete()` method to `SubstackClient` (mirrors post() with rate limiting)
- Input validation: post_id must be numeric

### HAR-Verified Endpoints
| Endpoint | Method | Body | Response |
|---|---|---|---|
| `/api/v1/reader/posts?inboxType=saved&limit=20` | GET | — | `{posts[], publications[], savedPosts[], inboxItems[], more}` |
| `/api/v1/reader/posts?inboxType=seen&limit=20` | GET | — | Same shape |
| `/api/v1/reader/posts?inboxType=paid&limit=20` | GET | — | Same shape |
| `/api/v1/posts/saved` | POST | `{"post_id": N}` | `{}` |
| `/api/v1/posts/saved` | DELETE | `{"post_id": N}` | `{}` |

### Batch 25 — Sprint Review
**Code review findings (7 from agents, 5 fixed, 2 skipped):**
1. **FIXED** — `substack_client.py`: `delete()` used `http.request("DELETE")` instead of `http.delete()`. Inconsistent with get/post pattern.
2. **FIXED** — `saved_posts.py`: Unguarded `int()` cast on `content_key` suffix could crash on malformed API data. Added try/except.
3. **FIXED** — Added `test_hint_absent_when_no_url` test for missing URL edge case. Strengthened `test_more_flag_in_response`.
4. **FIXED** — Added `test_summarize_fallback_returns_raw_content` and `test_malformed_content_key_handled` tests.
5. **FIXED** — Added `test_save_empty_string_post_id` and `test_unsave_empty_string_post_id` edge case tests. Fixed inconsistent post_id in unsave endpoint test.
6. **SKIP** — `since` param uses client-side filtering. Consistent with ALL existing feed tools. Not a regression.
7. **SKIP** — Reviewer claimed `get_cache` not patched in inbox_type tests — verified FALSE (it IS patched).

### Post-Deploy Verification
| Check | Result |
|---|---|
| `fly status` | started, 1 passing health check |
| `GET /health` | `{"status":"ok","version":"1.0.0"}` |
| MCP endpoint | Auth required (OAuth enabled) — correct |

### Test Results
**240 tests passing, 0 failures** (+40 from Sprint 5)

---

## Sprint 6 Summary

**APPROVED** — 2026-03-17
**Total tests:** 240 passing, 0 failing
**Batches completed:** 23-25 (Saved Posts, Save/Unsave, Sprint Review)
**Sprint review:** 7 findings from agents → 5 fixed, 2 skipped (1 consistent pattern, 1 false positive)
**Live smoke test:** 21/21 tools passing against live Substack API
**Bonus fixes:** 2 pre-existing bugs fixed (search_publications parsing, post_content redirects)
**Tools added:** ss_get_saved_posts (3 filters), ss_save_post, ss_unsave_post
**Total tools:** 19 (14 read + 4 write + 1 navigator)
**Deployed:** v1.5.0 to ss-nav-3950b79a5cc7.fly.dev

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

---

## Batch 14 — Like/React Tool (March 8, 2026)

### HAR-Verified Endpoints
| Type | Endpoint | Body |
|---|---|---|
| Article | `POST /api/v1/post/{post_id}/reaction` | `{"reaction": "❤", "surface": "reader", "tabId": "for-you"}` |
| Note | `POST /api/v1/comment/{comment_id}/reaction` | `{"publication_id": null, "reaction": "❤", "tabId": "for-you"}` |

Both return `200 OK` with `{}` body on success.

### Files Created/Modified
- `src/tools/like.py` — new tool, `like_content(id, type)` with validation and error handling
- `tests/unit/test_like.py` — 8 tests (post success, note success, auth expired, no cookie, invalid type, server error, network error)
- `src/substack_client.py` — added `post()` method (mirrors `get()` with rate limiting and response buffering)
- `src/server.py` — registered `ss_like` tool
- `src/tools/navigator.py` — added `ss_like` to tool list and API quirks

### Post-Deploy Verification
| Check | Result |
|---|---|
| `fly status` | started, 1 passing health check |
| `GET /health` | `{"status":"ok","version":"1.0.0"}` |
| MCP initialize | 200, session established |
| `ss_navigator` call | 11 tools listed (ss_like included) |

### Test Results
**129 tests passing, 0 failures** (8 new like tests)

---

## Batch 15 — Activity Feed (March 8, 2026)

### HAR-Verified Endpoint
| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/activity-feed-web?filter={filter}` | GET | substack.sid | Main activity/notifications feed |
| `/api/v1/activity/unread` | POST | substack.sid | Mark notifications as read (documented, not implemented) |

### Filters
| Filter | Activity Types |
|---|---|
| `all` | note_like, post_like, restack, restack_quote, note_reply, viral_gift_granted |
| `replies-and-mentions` | note_reply |
| `restacks` | restack, restack_quote |

### Response Shape
- `activityItems[]` — notifications with type, sender_count, recent_sender_ids, target IDs
- `users[]` — full user objects for sender lookup (name, handle, photo, is_following, can_dm)
- `posts[]` — post objects for target_post_id lookup
- `comments[]` — comment objects for target_comment_id / comment_id lookup
- `pubs[]` — publication objects for publication_id lookup
- `more: bool` — pagination flag

### Enrichment
Tool joins activity items with users/posts/comments/pubs arrays server-side, returning enriched objects with full sender details, target post titles/URLs, comment bodies, and publication names.

### Files Created/Modified
- `src/tools/activity_feed.py` — new tool, `get_activity_feed(filter, limit)` with validation, enrichment, error handling
- `tests/unit/test_activity_feed.py` — 16 tests (all filter, restacks filter, replies filter, enrichment x4, limit, validation, auth x2, errors x2, endpoint x2, isNew flag)
- `src/server.py` — registered `ss_get_activity_feed` tool
- `src/tools/navigator.py` — added tool to list, added 4 API quirks

### Post-Deploy Verification
| Check | Result |
|---|---|
| `fly status` | started, 1 passing health check |
| `GET /health` | `{"status":"ok","version":"1.0.0"}` |
| MCP initialize | 200, session established |
| `ss_navigator` call | 12 tools listed (ss_get_activity_feed included) |

### Test Results
**145 tests passing, 0 failures** (16 new activity feed tests)

---

## Sprint 4 — Deep Research Enablement (March 15, 2026)

### Problem
MCP server blocked Perplexity/Claude from deep research: full article content never returned (2000-char truncation), no article search, no signal for LLMs to get full text.

### Batch 16 — Content Architecture Fix
- Removed `RAW_CONTENT_CHARS = 2000` from all 5 content tools
- `ss_get_post_content`: default `summarize=False`, always returns full `content` field
- Feed tools: added `hint` field pointing to `ss_get_post_content`
- Two-tier pattern: Tier 1 (feeds/search → summaries) → Tier 2 (post_content → full text)

### Batch 17 — Article Search Tool
- New `ss_search_posts` using HAR-verified `GET /api/v1/post/search`
- Filters: `filter` (all/subscribed), `date_range` (day/week/month), `page` (pagination)
- Returns article previews with metadata, wordcount, reactions, restacks
- Dedup: insert but don't skip (search results always returned)
- Input validation on filter and date_range values

### Batch 18 — Sprint Review
**Code review findings (6 total, 5 fixed):**
1. **FIXED** — Summarizer could clobber caller fields via `article.update()`. Added key allowlist in `summarizer.py`.
2. **FIXED** — Notes in likes/restacks got misleading `hint` (URL is empty). Now only set hint when URL is present.
3. **FIXED** — `search_posts.py` had no input validation on `filter`/`date_range`. Added `VALID_FILTERS` and `VALID_DATE_RANGES` validation.
4. **FIXED** — `search_posts.py` missing dedup cache. Added `DedupCache` with insert-but-don't-skip pattern.
5. **FIXED** — `search_posts.py` missing `is_new` field. Added from dedup result.
6. **NOTED** — `post_content.py` uses raw `httpx.AsyncClient()` without auth or rate limiting. Pre-existing, not Sprint 4 regression. Deferred to future batch.

### Test Results
**171 tests passing, 0 failures** (+26 from baseline of 145)

---

## Sprint 5 — Trending Search, My Posts, Mark Seen (March 15, 2026)

### Batch 19 — Trending Search Tool
- New `ss_search_trending` using `GET /api/v1/recent/search`
- Returns articles ranked by recency + engagement scores (`search_score`, `recency_score`)
- Dedup: insert but don't skip

### Batch 20 — My Published Posts Tool
- New `ss_get_my_posts` using `GET {subdomain}.substack.com/api/v1/post_management/published`
- Subdomain-scoped endpoint (uses `SUBSTACK_PUBLICATION_SUBDOMAIN` env var, defaults to `joinveri`)
- Pagination via offset/limit, sortable by post_date asc/desc

### Batch 21 — Mark Seen Tool
- New `ss_mark_seen` using `POST /api/v1/reader/feed/{p|c}-{id}/seen`
- Mirrors `ss_like` pattern exactly
- Supports both posts (`p-{id}`) and notes (`c-{id}`)

### Test Results
**200 tests passing, 0 failures** (+29 from Sprint 4)

---

## Sprint 7 — Write tools, voice gate, async dedup

### Batch 1: Foundations — DONE 2026-05-02
- Removed summarizer (8 tools simplified, -18 tests)
- Async dedup via asyncio.to_thread (+1 concurrency test, max health probe 0.004ms vs 100ms threshold)
- ss_navigator growth playbook added (+1 test)
- Deployed to Fly, verified live, GOOGLE_AI_API_KEY secret removed
- Test count: ~224

### Batch 2: Voice gate — DONE 2026-05-02
- src/voice_check.py + 14 tests
- Hard-ban regex (em dash, en dash, semicolon, colon-with-label-exception, banned words, AI patterns)
- Force override via force=True

### Batch 3: Tier 1 writes — DONE 2026-05-02
- 9 tools, 31 new tests
- Test count: 269
- Voice gate enforced on all text-posting tools
- Live at https://ss-nav-3950b79a5cc7.fly.dev/mcp
