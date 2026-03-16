# Decisions Log: substack-mcp

## Format
Each decision includes: Context → Decision → Rationale → Alternatives Considered

---

## D001: Python over TypeScript
**Date:** 2026-03-07
**Context:** Choosing runtime for the MCP server. Shortwave MCP uses TypeScript/Node.js with `@modelcontextprotocol/sdk`. Spec calls for Python.
**Decision:** Python 3.12+ with `mcp[server]` (FastMCP pattern)
**Rationale:**
- Spec explicitly calls for Python
- `httpx` async client is excellent for API scraping
- `google-genai` Python SDK is more mature than JS
- SQLite3 is stdlib in Python — zero dependency for dedup
- Faster prototyping for undocumented API exploration
**Alternatives:** TypeScript (matches Shortwave/QB pattern but spec says Python)

---

## D002: SQLite for Dedup (not Postgres, not in-memory)
**Date:** 2026-03-07
**Context:** Need persistent dedup across deploys. Memory MCP uses vector DB for search but SQLite tables for dedup.
**Decision:** SQLite3 on Fly Volume at `/data/ss_navigator.db`
**Rationale:**
- Zero external dependencies
- Fly Volumes persist across deploys
- Fast enough for ~1000 article lookups/day
- Simple schema with indexes matches memory-mcp pattern
- No need for vector search here (dedup is ID-based, not semantic)
**Alternatives:** Postgres (overkill), in-memory dict (lost on deploy), Redis (external dep)

---

## D003: Server-Side Summarization (not client-side)
**Date:** 2026-03-07
**Context:** Articles need to be summarized before consumption. Could do it client-side (Claude/Perplexity) or server-side (Gemini).
**Decision:** Server-side Gemini Flash-Lite summarization with `summarize=true` default
**Rationale:**
- Keeps client token usage minimal (~200 tokens/article vs ~5000)
- Gemini Flash-Lite is $0.0006/article — negligible cost
- Server owns the full pipeline: fetch → dedup → summarize → return
- Graceful fallback to raw content on failure
**Alternatives:** Client-side (wastes expensive Claude/Perplexity tokens), no summarization (too much raw content)

---

## D004: Navigator START Tool Pattern
**Date:** 2026-03-07
**Context:** All three existing MCP servers (memory, quickbooks, shortwave) use a navigator/START tool.
**Decision:** Include `ss_navigator` tool with domain knowledge, tool discovery, and workflow guides
**Rationale:**
- Proven pattern across all optionshift MCP servers
- Helps AI clients discover available tools without trial-and-error
- Can embed domain knowledge (Substack API quirks, auth rotation, feed semantics)
- Low implementation cost, high value for multi-agent consumption
**Alternatives:** No navigator (breaks established pattern)

---

## D005: pytest over Vitest (TDD Framework)
**Date:** 2026-03-07
**Context:** Shortwave MCP uses Vitest (TypeScript). This project is Python.
**Decision:** `pytest` + `pytest-asyncio` with mocked httpx responses
**Rationale:**
- Standard Python testing framework
- `pytest-asyncio` handles async tool functions natively
- `httpx` mock transport is well-documented
- Target: 100+ tests (updated by D011 — benchmarking memory-mcp's 131)
**Alternatives:** unittest (verbose), Vitest (wrong language)

---

## D006: Cookie Auth (not OAuth, not API key)
**Date:** 2026-03-07
**Context:** Substack has no public API. Authentication is via browser session cookies.
**Decision:** Session cookie auth (`substack.sid` / `connect.sid`) stored as env var
**Rationale:**
- Only known auth method for Substack's undocumented API
- ~~30 day~~ expiry is actually MONTHS per D012 verification — manageable with `ss_auth_check` validation
- Clear error messages when expired with rotation instructions
**Alternatives:** OAuth (doesn't exist), API key (doesn't exist), scraping (fragile)
**Risk:** Cookie format or endpoints could change without notice. Mitigation: robust error handling + API endpoint verification tests.

---

## D007: Fixed Tag Vocabulary (not open-ended)
**Date:** 2026-03-07
**Context:** Summarization includes tagging articles. Tags could be open-ended or fixed.
**Decision:** Fixed 10-tag vocabulary: `creator-economy`, `AI-agents`, `monetization`, `platform-strategy`, `content-strategy`, `fundraising`, `product`, `engineering`, `culture`, `other`
**Rationale:**
- Consistent categorization for downstream filtering
- Prevents tag explosion / synonyms
- Aligned with Option Shift's content pillars
- Easy to expand in V2 if needed
**Alternatives:** Open-ended LLM tags (inconsistent), no tags (loses categorization value)

---

## D008: Caching Strategy — Server Owns Dedup
**Date:** 2026-03-07
**Context:** Who is responsible for not re-processing articles — client or server?
**Decision:** Server-side dedup. Clients can call the same tool repeatedly and get only new articles.
**Rationale:**
- Borrowed from memory-mcp pattern (server owns state)
- Multiple clients (Perplexity + Claude) would need independent dedup otherwise
- Single source of truth for "what's been seen"
- SQLite on Fly Volume is the persistence layer
**Alternatives:** Client-side dedup (duplicated logic, state management burden on each client)

---

## D009: StreamableHTTP Transport (not SSE)
**Date:** 2026-03-07
**Context:** Original spec calls for SSE transport. Memory MCP server uses StreamableHTTP in production (newer MCP transport). SSE is being superseded.
**Decision:** Use StreamableHTTP transport for production, stdio for local dev
**Rationale:**
- Memory MCP (latest optionshift server) uses StreamableHTTP — this is the current standard
- StreamableHTTP is the successor to SSE in the MCP protocol as of late 2025
- Better reliability, built-in session management
- Perplexity Computer and Claude Cowork support StreamableHTTP
- Matches memory-mcp pattern: `NODE_ENV=production` → HTTP, else stdio
**Alternatives:** SSE (original spec, but being deprecated), stdio only (no remote access)
**Update Applied:** PRD and CLAUDE.md updated from SSE to StreamableHTTP (verified in review pass)

---

## D010: Schema Versioning with Migrations
**Date:** 2026-03-07
**Context:** Memory MCP uses versioned schema migrations (v1→v2→v3) with non-transactional ALTER TABLE support.
**Decision:** Adopt same migration pattern for SQLite schema
**Rationale:**
- Proven pattern from memory-mcp production deployment
- Supports schema evolution without breaking existing data
- Non-transactional approach handles SQLite's ALTER TABLE limitations
- `INSERT OR REPLACE INTO schema_version` for idempotency
**Alternatives:** Single-shot schema (no evolution), ORM migrations (too heavy)

---

## D011: Test Target 100+ (benchmarking memory-mcp's 131)
**Date:** 2026-03-07
**Context:** Memory MCP has 131 tests, Shortwave has 91. QuickBooks has zero tests.
**Decision:** Target 100+ tests, structured as unit/integration/regression
**Rationale:**
- Memory MCP's 131-test suite is the gold standard for optionshift MCP servers
- Includes dedicated bugfix regression tests — adopt this pattern
- Test structure: unit (tools), integration (DB), regression (bugfixes)
- Use pytest fixtures for in-memory SQLite and mocked HTTP
**Alternatives:** Lower target (risks regression), no regression suite (loses bug tracking)

---

## D012: Endpoint Corrections from API Research (Verified)
**Date:** 2026-03-07
**Context:** Launched research agent to verify all Substack API endpoints from spec against real evidence (GitHub repos, blog posts, reverse-engineering articles). Found 2 incorrect paths, 1 unverified path.
**Decision:** Correct endpoints based on verified evidence, flag unverified ones for live testing
**Corrections:**
| Spec Path | Corrected Path | Source |
|---|---|---|
| `/api/v1/user/me` | `/api/v1/user/profile/self` | `ma2za/python-substack` source code |
| `/api/v1/reader/notes/feed` | `/api/v1/notes?cursor={cursor}` | Reverse-engineering article + substack-api readthedocs |
| `/api/v1/reader/feed` (FYP) | **UNVERIFIED** — may be `/api/v1/comment/feed` with `tabId: "for-you"` | Needs live browser network tab verification |
**Confirmed as-is:** `/api/v1/publication/search`, `/api/v1/subscriptions`, likes/restacks profile endpoints
**Also unverified (not in original count):** `/api/v1/reader/feed?filter=subscription` — needs live test alongside FYP endpoint
**Cookie expiry correction:** Months (not ~30 days as spec stated) — multiple sources confirm cookies survive months without logout
**Rationale:** Building on unverified endpoints guarantees breakage. Correct now, live-test the unverified FYP endpoint during Batch 2 auth testing.
**Risk:** Substack can change any undocumented endpoint at any time. Mitigation: endpoint smoke tests in CI, version-pin known-working paths.

---

## D013: RSS Fallback Strategy
**Date:** 2026-03-07
**Context:** API research confirmed every Substack publication has RSS at `{subdomain}.substack.com/feed`. RSS is rate-limit-free and auth-free.
**Decision:** Implement RSS fallback for subscription feed if authenticated API endpoints fail
**Rationale:**
- The user's 57 subscriptions all have RSS feeds (confirmed in OPML export)
- RSS provides full content for free posts, no auth needed
- Can serve as fallback if session cookie expires before rotation
- RSS cannot access Notes, likes, restacks, or FYP — so it's a fallback, not a replacement
**Alternatives:** API-only (breaks on auth failure), scraping (fragile)

---

## D014: HAR Analysis — Endpoint Corrections (March 2026)
**Date:** 2026-03-08
**Context:** User captured two HAR files from live substack.com browsing sessions. Analysis revealed 6 critical discrepancies between our implementation and real API behavior.
**Decision:** Correct all verified endpoints and response parsing based on HAR evidence.
**Corrections:**
| Issue | Before | After (HAR-verified) |
|---|---|---|
| FYP feed params | `GET /api/v1/reader/feed` (no params) | `GET /api/v1/reader/feed?tab=for-you&type=base` |
| FYP response shape | `{ "posts": [...] }` | `{ "items": [{ "entity_key", "type", "post", "comment", "context" }] }` |
| Subscription feed params | `?filter=subscription` | `?tab=subscribed&type=secondary` |
| Subscription feed response | Same `posts` shape | Same `items` shape as FYP |
| Subscriptions endpoint | `/api/v1/subscriptions` (301 redirect) | `/api/v1/subscriptions/page` (direct) |
| Subscriptions response | Flat array `[{ "publication": {...} }]` | `{ "subscriptions": [...], "publications": [...] }` (join by publication_id) |
| Cookie auth | Both `substack.sid` and `connect.sid` | Only `substack.sid` needed |
| httpx redirects | Not following 301s | `follow_redirects=True` added |
**Still unverified (kept as-is):**
- Auth endpoint `/api/v1/user/profile/self` — not seen in HAR (browser uses `/api/v1/user/{id}-{handle}/public_profile/self`), but sourced from python-substack library. May work; needs live test.
- Notes endpoint `/api/v1/notes` — not hit in HAR (notes appear inline in reader/feed as `type: "comment"`). May work as standalone; needs live test.
**New discoveries from HAR (not implemented, for future reference):**
- `GET /api/v1/posts/by-id/{postId}` — fetch post by numeric ID (no subdomain needed)
- `GET /api/v1/reader/posts?inboxType={paid|saved|seen}` — filtered reading lists
- `GET /api/v1/inbox/top` — reading queue with offset pagination
- `GET /api/v1/search/explore/web` — discover/explore feed
- `GET /api/v1/activity/unread` — lightweight auth validation
- Feed pagination uses base64-encoded opaque cursors
- Cookie expiry confirmed: ~90 days (set March 7, expires June 5)
- User ID: `383926424`, handle: `mileslozano`
**Rationale:** HAR captures are ground truth — they show exactly what the real Substack frontend sends. These corrections prevent guaranteed 404s and empty-response bugs in production.

---

## D015: Two-Tier Content Architecture
**Date:** 2026-03-15
**Context:** Feed tools returned either Gemini summaries (no full text) or 2000-char truncated raw content. LLMs doing deep research had no way to get complete article text.
**Decision:** Two-tier discovery pattern — Tier 1: feed/search tools return summaries with `hint` field pointing to `ss_get_post_content`. Tier 2: `ss_get_post_content` returns complete untruncated markdown.
**Rationale:**
- Saves tokens on discovery (summaries are small)
- Full content available on demand for deep research
- `hint` field tells LLMs exactly which tool to call and how
- `ss_get_post_content` default changed to `summarize=False` (it's the "read full article" tool)
- `content` field always present (summary augments, never replaces)
**Alternatives:** Always return full content (wastes tokens), only return summaries (blocks deep research)

---

## D016: Article Search via /api/v1/post/search
**Date:** 2026-03-15
**Context:** HAR capture from search page with Posts tab revealed `GET /api/v1/post/search` endpoint with filter and pagination support. Previous search tool only found publications.
**Decision:** New `ss_search_posts` tool using `/api/v1/post/search` with `filter` (all/subscribed), `dateRange` (day/week/month), and `page` (0-indexed pagination).
**Rationale:**
- HAR-verified with full response schema (results[] with id, title, truncated_body_text, wordcount, reactions, canonical_url)
- Filters enable scoped search (subscriptions only vs all Substack)
- Time filters enable recency-based discovery
- Pagination for browsing deep result sets
- Returns article previews — LLMs use `ss_get_post_content` for full text (D015 pattern)
**Alternatives:** Platform/search endpoint (only returns publications/users), top/search (mixed results, less structured)

---

## D017: Authenticated Search Only
**Date:** 2026-03-15
**Context:** `/api/v1/post/search` requires `substack.sid` cookie. The older `/api/v1/publication/search` works without auth.
**Decision:** Use authenticated client for article search. No public fallback.
**Rationale:**
- Article search requires auth by design (subscription-scoped results need user context)
- All other feed tools already require auth — consistent pattern
- Public publication search still available via `ss_search_publications`
**Alternatives:** Auth with public fallback (more code, publication search ≠ article search)

---

## D018: Summarizer Key Allowlisting
**Date:** 2026-03-15
**Context:** Code review found `article.update(summary_result)` could clobber article fields if Gemini returned unexpected JSON keys. The summarizer returned the raw parsed dict without filtering.
**Decision:** Allowlist summary keys in `summarizer.py` — only return `{summary, tags, relevance, key_quote, angle}`.
**Rationale:**
- Prevents Gemini hallucinated keys from overwriting `content`, `hint`, `id`, `url`, etc.
- Single fix point protects all callers (5 feed tools + post_content)
- Follows principle of least surprise — callers expect only the documented schema
**Alternatives:** Per-caller key filtering (duplicated logic across 6 files)
