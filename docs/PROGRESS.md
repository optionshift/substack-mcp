# Progress Log: substack-mcp

## Status: Scaffolding
**Last Updated:** 2026-03-07

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

### Pending
- [ ] Create pyproject.toml with dependencies
- [ ] Implement Batch 1 (server scaffold + StreamableHTTP transport)
- [ ] Begin TDD cycle
- [ ] Live-test unverified FYP endpoint (`/api/v1/reader/feed` vs `/api/v1/comment/feed`)

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
| 1 — Scaffold | Complete | 11 | pyproject.toml, src/server.py, __init__.py files, test_server.py |
| 2 — Auth | Complete | 10 | Live-test deferred (SUBSTACK_SESSION_COOKIE empty). substack_client.py + tools/auth.py |
| 3 — Subscriptions | Complete | 7 | tools/subscriptions.py |
| 4 — Dedup Cache | Complete | 15 | src/dedup.py, unit + integration tests |
| 5 — Summarization | Not Started | — | Moved before feed tools (per D003 — feed tools default summarize=true) |
| 6 — FYP Feed | Not Started | — | — |
| 7 — Sub Feed | Not Started | — | — |
| 8 — Post Content | Not Started | — | — |
| 9 — Likes/Restacks | Not Started | — | — |
| 10 — Notes Feed | Not Started | — | — |
| 11 — Search | Not Started | — | — |
| 12 — Navigator | Not Started | — | — |
| 13 — Deploy | Not Started | — | — |
