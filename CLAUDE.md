# CLAUDE.md — substack-mcp (ss-navigator)

## Project Overview
Remote MCP server for Substack content ingestion. Python 3.12+ on Fly.io with StreamableHTTP transport.
Consumed by Perplexity Computer and Claude Cowork scheduled tasks.

## Tech Stack
- Python 3.12+, `mcp[server]` (FastMCP), `httpx`, `google-genai`, `markdownify`
- SQLite3 on Fly Volume for dedup cache
- pytest + pytest-asyncio for testing
- Fly.io deployment (LAX region)

## Architecture Patterns
- **Navigator START tool** — `ss_navigator` must be the first tool clients call
- **Server-side dedup** — SQLite `seen_articles` table, server owns all state
- **Server-side summarization** — Gemini Flash-Lite, optional param, graceful fallback
- **Standard error shape** — `{ error, code, message, retry_after }`
- **Cookie auth** — `substack.sid` only (not connect.sid), expiry: ~90 days (per D012/D014 HAR confirmation)

## Development Rules

### Agent Teams (MANDATORY)
- Use agent teams for all multi-file changes, investigations, and reviews
- Launch review agents. When they report back, DO NOT present findings yet. First, re-read every cited file and verify each finding is real. Remove any finding you can't confirm with actual code. Then present only verified findings.
- Every finding from parallel agents must include (a) exact file path and line number, (b) a direct quote of the problematic code, (c) why it's wrong with concrete evidence not assumptions
- After all agents report, launch a Verification Agent that reads every cited file+line and produces a filtered report keeping only findings where the evidence actually supports the claim

### Caching (MANDATORY)
- All feed tools MUST check SQLite dedup cache before returning articles
- Cache insertions happen server-side, never delegated to clients
- Use `seen_articles` table with indexed lookups by post ID
- Dedup logic: check by ID → if exists, skip → if new, insert and return

### Test-Driven Development (MANDATORY)
- Write tests BEFORE implementation code
- Every tool must have unit tests with mocked HTTP responses
- Dedup behavior must be tested (insert, lookup, skip)
- Summarization must be tested (success, failure/fallback)
- Auth must be tested (valid, expired, missing)
- Target: 100+ tests (per D011, benchmarking memory-mcp's 131)
- Run full test suite before every commit — zero regressions allowed

### Spec-Driven Development (MANDATORY)
- All implementation must trace back to PRD.md requirements
- No speculative changes or optimizations not in the spec
- Before committing, verify each change maps to a specific PRD requirement

### Code Review
When running code review agents or parallel investigation agents, always verify findings against actual source code before reporting. Flag confidence level on each finding. Never report a finding without confirming it in the codebase.

### Git Workflow
- Before committing code changes, run `git diff --staged` and verify only intended files are included
- Never amend commits without checking for unrelated staged files first
- Atomic commits — one logical change per commit
- Before EVERY commit: (1) Run full type-check and test suite — zero regressions, (2) Git diff staged changes and verify ONLY files from current batch, (3) Verify each change maps to a specific PRD requirement

### Deployment
- When deploying to Fly.io, always explicitly confirm the deploy was executed and verify it's live
- After deploying: (1) `fly status` to confirm, (2) Hit health endpoint and show response, (3) Run smoke test against production
- Don't mark deploy as done until all 3 pass
- Never assume merging or local verification equals deployment
- After deploy is verified, update `docs/SUBSTACK_MCP_REFERENCE.md` to reflect any new/changed tools, endpoints, schemas, or capabilities. Bump the version, update the changelog, and ensure the Quick Reference Card is current.

### Sprint Protocol (MANDATORY)
Each batch follows this exact sequence. No shortcuts.

#### Phase 1: Plan
- Read the batch's Mini PRD section in `docs/PRD.md`
- Confirm scope, files, parameters, schemas, and gate criteria

#### Phase 2: TDD Cycle (RED → GREEN)
1. **RED** — Write failing tests first. Run tests → confirm they FAIL (red)
2. **CODE** — Implement the minimum code to make tests pass
3. **GREEN** — Run tests → confirm they PASS (green). Iterate until all green

#### Phase 3: Batch Checkpoint
1. Update `docs/PROGRESS.md` — mark batch status, test count, notes
2. Run full test suite — zero regressions
3. Deploy to Fly.io → verify (fly status, health, smoke test)
4. Update `docs/SUBSTACK_MCP_REFERENCE.md` — add/update tools, endpoints, schemas, bump version, update changelog
5. `git diff --staged` — verify only batch files included
6. Atomic git commit with batch reference (e.g., "Batch 1: server scaffold with health endpoint")

#### Phase 4: Sprint Review (after all batches in a sprint complete)
1. Launch code-reviewer agent teams with gates on all changed files
2. Launch verification agent — re-read every cited file+line, keep only confirmed findings
3. Run targeted tests on areas flagged by reviewers
4. Fix any verified issues
5. Progress log update + atomic git commit

#### Phase 5: Final Approval
1. Run FULL test suite — zero failures
2. Run FULL linter/type-check — zero errors
3. Launch final code-review agent with gate: must return PASS
4. Final `docs/PROGRESS.md` update with `APPROVED` stamp and test counts
5. Final atomic git commit with full sprint summary
6. Present summary to user: files changed, tests added, gates passed, batch status

## Key Files
- `docs/SUBSTACK_MCP_REFERENCE.md` — Complete MCP reference (tools, schemas, endpoints, workflows) — **update after every deploy**
- `docs/PRD.md` — Product requirements document
- `docs/PROGRESS.md` — Batch progress tracking
- `docs/DECISIONS.md` — Architecture decision log
- `shortwave-mcp-spec.md` — Original spec (reference only)
- `substack-feeds.txt` — OPML export of 57 subscriptions

### Project Structure
- `src/server.py` — MCP server entry point (all tools registered)
- `src/__main__.py` — uvicorn production entrypoint
- `src/substack_client.py` — Substack API client (httpx, cookie auth, rate limiting)
- `src/dedup.py` — SQLite dedup cache with schema versioning
- `src/summarizer.py` — Gemini Flash-Lite summarization (async)
- `src/tools/` — Tool implementations (12 tools)
- `tests/unit/` — Unit tests (pytest + pytest-asyncio)
- `tests/integration/` — Integration tests

## API Endpoints (Substack — Undocumented, HAR-Verified March 2026)
- `GET /api/v1/user/profile/self` — Auth check (LIVE-CONFIRMED 200 OK, returns id/name/handle/bio)
- `GET /api/v1/reader/feed?tab=for-you&type=base` — FYP feed (LIVE-CONFIRMED, returns items[] mixing posts+notes)
- `GET /api/v1/reader/feed?tab=subscribed&type=secondary` — Subscription feed (HAR-CONFIRMED, same items[] format)
- `GET /api/v1/subscriptions/page` — List subscriptions (LIVE-CONFIRMED, /subscriptions 301-redirects here)
- `GET /api/v1/notes` — **404 NOT FOUND** — Notes come inline via reader/feed as type=comment
- `GET /api/v1/reader/feed/profile/{user_id}?types[]=like` — Likes (LIVE-CONFIRMED, items[] format)
- `GET /api/v1/reader/feed/profile/{user_id}?types[]=restack` — Restacks (LIVE-CONFIRMED, items[] format)
- `GET /api/v1/posts/{slug}` — Single post (per-publication subdomain, CONFIRMED)
- `GET /api/v1/posts/by-id/{postId}` — Single post by ID (HAR-CONFIRMED, no subdomain needed)
- `GET /api/v1/publication/search?query={q}` — Publication search (CONFIRMED, no auth)
- `GET /api/v1/activity-feed-web?filter={filter}` — Activity/notifications feed (HAR-CONFIRMED, filters: all, replies-and-mentions, restacks)
- `POST /api/v1/post/{id}/reaction` — Like article (HAR-CONFIRMED, body: `{reaction: ❤, surface: reader, tabId: for-you}`)
- `POST /api/v1/comment/{id}/reaction` — Like note (HAR-CONFIRMED, body: `{publication_id: null, reaction: ❤, tabId: for-you}`)
- `POST /api/v1/activity/unread` — Mark notifications as read (HAR-CONFIRMED)
- `GET /api/v1/post/search?query={q}&page={n}&includePlatformResults={bool}&filter={scope}&dateRange={range}` — Article search (HAR-CONFIRMED, returns results[] with post data)
- `GET /api/v1/recent/search?query={q}&fromSuggestedSearch=false` — Trending/recent search (HAR-CONFIRMED, returns items[] with search_score, recency_score)
- `GET https://{subdomain}.substack.com/api/v1/post_management/published?offset={n}&limit={n}&order_by=post_date&order_direction={asc|desc}` — Creator's published posts (HAR-CONFIRMED, subdomain-scoped)
- `POST /api/v1/reader/feed/{p|c}-{id}/seen` — Mark post/note as seen (HAR-CONFIRMED, returns {})
- `GET /api/v1/activity/unread` — Lightweight auth validation (LIVE-CONFIRMED)

### Endpoint Verification Status
ALL ENDPOINTS LIVE-TESTED. Every tool's API path returns 200 OK with expected data.
Cookie: Only substack.sid needed (not connect.sid). Expiry ~90 days. User ID: 383926424.

## Environment Variables
- `SUBSTACK_SESSION_COOKIE` — Substack session cookie value
- `GOOGLE_AI_API_KEY` — Gemini Flash-Lite API key
- `MCP_AUTH_TOKEN` — Shared secret for MCP client auth
- `SQLITE_PATH` — Path to SQLite db (default: `/data/ss_navigator.db`)
