# Substack MCP Sprint 7 — Write tools, voice gate, summarizer removal, async dedup

**Status:** Draft for review
**Author:** Claude Opus 4.7 with Miles
**Date:** 2026-05-02
**Sprint:** Sprint 7 (next after Sprint 6 APPROVED at commit `bb218c7`)

## Background

The Substack MCP server (`ss-nav-3950b79a5cc7.fly.dev`) has 19 tools across 6 prior sprints. It is read-heavy. Write capability is limited to `like`, `save`, `unsave`, `mark_seen`. Two operational problems and three feature gaps justify Sprint 7:

1. **Health-check flapping under load.** Sync sqlite operations on the asyncio event loop block `/health` past Fly's 5s health check timeout, causing the proxy to refuse `/mcp` requests with `"could not find a good candidate within 40 attempts at load balancing"`. Stabilization (2 machines, looser health windows) shipped 2026-05-02 in commit pending. Root cause remains.
2. **Summarizer is unused friction.** Optional `summarize` param across 8 tools, default off, runs Gemini 2.0 Flash-Lite (2 generations stale). Miles wants full articles always to drive replies/restacks/notes, so the summarizer adds maintenance cost without product value.
3. **No write tools beyond likes/saves.** Cannot publish or reply to a Note, restack with quote, comment on articles, manage drafts, schedule posts, upload images, or follow/subscribe — all of which are central to growth on Substack and to Miles's article-to-Notes amplification workflow.

Substack's API is undocumented but the relevant endpoints are HAR-confirmed via four open-source wrappers (`ma2za/python-substack`, `jakub-k-slys/substack-api`, `06ketan/substack-ops`, `NHagar/substack_api`). A subset of high-value endpoints (scheduled notes, follow/unfollow, DM, pub-subscribe) are not yet captured by any open-source wrapper and require a 5-minute DevTools HAR capture session per endpoint.

## Sprint 7 final scope (after HAR review 2026-05-02)

`may2capture.har` (project root, 230 MB, captured 2026-05-02 16:49 PT) confirms multiple Tier 2 endpoints we'd previously planned to defer. Specifically:

- `POST /api/v1/comment/draft` with optional `trigger_at` ISO timestamp creates either a draft note or a scheduled note (same endpoint, dual purpose).
- `DELETE /api/v1/comment/{id}` cancels scheduled notes and deletes draft notes.
- `GET /api/v1/feed/drafts?limit=20` lists all drafts and scheduled notes (filter client-side via `trigger_at`).
- `POST /api/v1/feed/{user_id}/follow` with body `{surface: "profile"}` follows a user.
- `DELETE /api/v1/feed/{user_id}/follow` unfollows.
- `GET /api/v1/feed/following` returns the list of followed user IDs.

DM send and reply-to-note remain unconfirmed. DM is likely websocket-only on Substack's Zync realtime infrastructure. Per Miles, reply is deferred regardless of HAR status. Subscribe/unsubscribe permanently dropped.

**Sprint 7 ships across 5 batches (24 new tools):**
- **Batch 1** — Foundations (summarizer removal, async dedup, navigator growth playbook update).
- **Batch 2** — Voice gate primitive.
- **Batch 3** — 9 Tier 1 writes (publish_note, restack, unrestack, comment_on_post, get_post_comments, get_note_replies, react, delete, upload_image).
- **Batch 4** — 8 article-drafts + post-scheduling tools (list/get/create/update/delete drafts, publish_draft, schedule_post, unschedule_post).
- **Batch 5** — 7 newly HAR-confirmed tools (create_note_draft, schedule_note, list_note_drafts, cancel_scheduled_note, follow, unfollow, list_following).

**Sprint 8 candidates (deferred):** ss_reply_to_note (per Miles), ss_send_dm (no HAR, likely websocket transport).

**Permanently out of scope:** ss_subscribe_to_pub / ss_unsubscribe.

## Goals

- Remove summarizer end-to-end (code, tests, dep, env, docs).
- Eliminate event-loop blocking by moving sqlite work off the event loop.
- Add 24 new write/read tools across three batches: 9 immediate-write tools (publish, restack, comment, react, delete, image, etc.), 8 article-drafts + post-scheduling tools (drafts CRUD + schedule), 7 note-scheduling + following tools (HAR-confirmed via may2capture.har). DM send and reply_to_note deferred to Sprint 8.
- Hard voice-enforcement gate at the MCP API layer for every text-posting tool.
- Bake Substack growth domain knowledge into the START tool (`ss_navigator`).
- Maintain zero regressions across the existing 240-test suite.

## Non-goals

- Veri publication identity (multi-account). Server stays bound to Miles's `substack.sid`.
- Post analytics beyond what's already returned in post metadata. Real read/open/click stats live behind a CSRF flow no public wrapper has captured. Out of scope.
- Pinning posts/notes. No wrapper covers it. Out of scope.
- New transport. Stays StreamableHTTP on Fly.

## Architectural decisions

### Decision 1: Remove summarizer entirely

Per Miles, full article text is required for replies, restacks, quote-restacks, and notes derived from articles. Summary loses fidelity. The `summarize` param defaults to `False` on every tool, so removing it changes no caller behavior unless a caller explicitly opted in.

**Action:** Delete `src/summarizer.py`, `tests/unit/test_summarizer.py`, drop `google-genai` from requirements, drop `GOOGLE_AI_API_KEY` from Fly secrets, remove the `summarize` param + branch from 8 tools, update SUBSTACK_MCP_REFERENCE.md.

### Decision 2: Wrap dedup in `asyncio.to_thread`

`DedupCache` uses `sqlite3` (sync) with `check_same_thread=False` and an internal `threading.Lock`. Every `insert` / `exists` / lookup runs sync sqlite directly on the event loop. With a single uvicorn worker and a feed that returns 50+ items, the resulting bursts can hold the loop past `/health`'s 5s timeout. Switching the methods to async wrappers around `asyncio.to_thread` keeps the public API identical while moving the blocking work to a thread.

**Action:** Convert `DedupCache.insert`, `DedupCache.exists`, and any other sync methods to `async def` whose body is `return await asyncio.to_thread(self._sync_method, ...)` pattern. Update callers in `src/tools/*` to `await dedup.insert(...)` / `await dedup.exists(...)`.

### Decision 3: Voice gate at the MCP API layer (hard gate, force-overridable)

Voice-enforcement is the first line of defense against em-dashes, banned words, and AI-pattern phrases reaching Substack. Caller-side enforcement (the `veri-gtm:voice-enforcement` skill) is the source of truth for nuanced rules, but the MCP must enforce a minimal hard ban server-side because callers can be agents without that skill loaded.

**Design:**
- New module `src/voice_check.py` with a single function `check(text: str) -> list[Violation]` returning structured violations (each `{rule, severity, span, message}`).
- Hard ban set bundled in code: em dash `—`, en dash `–` between words, semicolons, colons (except `<single-word>: <value>` label pattern), banned-words list (`leverage`, `synergy`, `revolutionary`, `ensure`, `crucial`, `delve`, `foster`, `comprehensive`, etc.), AI-pattern phrases (`not because .* because`, `here's the thing`, `let that sink in`, `the real .* isn't`, `unpopular opinion`, `hot take`).
- Sources: `references/voice-enforcement-rules.md` + article-social-launch SKILL.md banned list.
- Every write tool that posts text accepts `force: bool = False`. Default behavior: voice violations short-circuit the call and return `{error: "voice_violation", code: 422, violations: [...], message: "..."}`. With `force=True`, post anyway.
- Tools that don't post text (`ss_react` with emoji only, `ss_restack` without quote, `ss_unrestack`, `ss_delete`, `ss_follow`, `ss_subscribe_to_pub`) skip the voice check entirely.

**Maintenance:** When `references/voice-enforcement-rules.md` changes (via `veri-gtm:revise-voice-rules`), the rules in `voice_check.py` must be re-synced. Documented as a follow-up checklist item in `docs/PROGRESS.md`.

### Decision 4: HAR-gated Tier 2 tools

Four high-value tools (scheduled notes, follow, subscribe, DM) lack open-source HAR confirmation. Rather than guess and ship broken tools, Sprint 7 includes a HAR-capture round with Miles before Batch 5 implementation:

1. Miles opens `https://substack.com` in Chrome.
2. DevTools → Network → filter `fetch/xhr`.
3. Performs each action (schedule one note, follow someone, subscribe to a pub, send a DM).
4. Right-clicks the relevant request → Copy as cURL (POSIX) → pastes in chat.
5. Spec extracts URL + method + body schema.

If any HAR reveals an architecture incompatible with REST tools (e.g., DM uses websockets), that single tool drops to a follow-up sprint without blocking the other three.

### Decision 5: Growth knowledge in `ss_navigator`

The START tool (`ss_navigator`) returns tool descriptions and workflow guidance. Sprint 7 extends it with a Growth Playbook section so any agent calling the MCP gets the domain knowledge baked in:

- **Algorithmic weights:** restacks > replies-on-others > own-notes > likes (per Substack ML head).
- **Note format:** 64–255 words, 4–6 short paragraphs, hook in first 7–10 words.
- **Restack pattern:** restack-with-comment beats naked restack for your visibility; @-mention the author when quoting.
- **7-day article amplification flow:** publish → quote-restack → stat-only Note → "thing I almost cut" → peer-reply → tutorial → contrarian close.
- **Free→paid honest median:** ~3%, not 5–10%. Lifts come from paywalled chat replies, paid sections, automations.
- **Recommendations:** ~40% of new subs in 2026; high-ROI swap mechanism.
- **Voice rules per format:** X all-lowercase, Substack sentence case, banned word list pointer.

This keeps the LLM caller informed without a separate skill load.

## New tool specifications

All tools listed with method + endpoint. Each is registered as `@mcp.tool()` in `src/server.py` with implementation in `src/tools/<name>.py` and unit tests in `tests/unit/test_<name>.py`.

### Batch 1 — Foundations (no new tools, surface shrinks)

- Remove summarize param from: `ss_get_fyp_feed`, `ss_get_subscription_feed`, `ss_get_likes`, `ss_get_restacks`, `ss_get_post_content`, `ss_get_saved_posts` (and any other holders).
- Tests: -13 (drop test_summarizer.py).
- Dedup methods become async; ~14 callers updated.

### Batch 2 — Voice gate primitive

- New: `src/voice_check.py` with `check(text)` and `Violation` dataclass.
- Tests: ~12 (one per rule class + force-bypass + label-colon exception).

### Batch 3 — Tier 1 write tools (10)

| Tool | Method | Endpoint | Notes |
|------|--------|----------|-------|
| `ss_publish_note(text, attachments=[], force=False)` | POST | `/api/v1/comment/feed` | ProseMirror bodyJson. attachments are link objects (id from upload-attachment step). |
| ~~`ss_reply_to_note`~~ | — | — | DEFERRED to Sprint 8 per Miles 2026-05-02. |
| `ss_restack(target_id, kind, quote_text=None, force=False)` | POST | `/api/v1/restack/feed` | If `quote_text` provided, post a quote-Note first then restack. `kind`: `"post"` or `"note"`. |
| `ss_unrestack(target_id, kind)` | DELETE | `/api/v1/restack/feed` | No voice check. |
| `ss_comment_on_post(post_id, text, parent_id=None, force=False)` | POST | `{pub}/api/v1/post/{post_id}/comment` | Resolve publication subdomain via existing `/posts/by-id/{id}` lookup. |
| `ss_get_post_comments(post_id, sort="best_first")` | GET | `{pub}/api/v1/post/{post_id}/comments?all_comments=true&sort=best_first` | No voice check. |
| `ss_get_note_replies(note_id, cursor=None)` | GET | `/api/v1/reader/comment/{note_id}/replies` | No voice check. |
| `ss_react(target_id, kind, emoji="❤")` | POST | `/api/v1/post/{id}/reaction` or `/api/v1/comment/{id}/reaction` | Generalizes existing `ss_like`. `ss_like` is retained as a thin alias for backward compat (so existing callers don't break) and delegates to `ss_react` with `emoji="❤"`. |
| `ss_delete(target_id, kind)` | DELETE | host-disambiguated | `kind`: `"note"` → `substack.com`; `"post_comment"` → `{pub}.substack.com`. |
| `ss_upload_image(image_path_or_b64)` | POST | `{pub}/api/v1/image` | Returns CDN URL. Used as input to `attachments` for `ss_publish_note`. |

### Batch 4 — Drafts CRUD + post scheduling (5)

| Tool | Method | Endpoint | Notes |
|------|--------|----------|-------|
| `ss_list_drafts(limit=20, offset=0)` | GET | `{pub}/api/v1/drafts?limit=N&offset=N` | |
| `ss_get_draft(draft_id)` | GET | `{pub}/api/v1/drafts/{id}` | |
| `ss_create_draft(title, body_markdown, subtitle=None, force=False)` | POST | `{pub}/api/v1/drafts` | Voice-checks `body_markdown`. Converts markdown to ProseMirror bodyJson. |
| `ss_update_draft(draft_id, fields)` | PUT | `{pub}/api/v1/drafts/{id}` | `fields` = subset of {title, subtitle, slug, search_engine_title, search_engine_description}. Voice-check fields if `body_markdown` included. |
| `ss_delete_draft(draft_id)` | DELETE | `{pub}/api/v1/drafts/{id}` | |
| `ss_publish_draft(draft_id, send=True, share_automatically=False)` | POST | `{pub}/api/v1/drafts/{id}/publish` | |
| `ss_schedule_post(draft_id, post_date_iso)` | POST | `{pub}/api/v1/drafts/{id}/schedule` | |
| `ss_unschedule_post(draft_id)` | POST | `{pub}/api/v1/drafts/{id}/schedule` | body `{post_date: null}`. |

(Batch 4 lists 8 tools; the spec table groups schedule/unschedule under one batch entry.)

### Batch 5 — Note scheduling + Following (7 tools, all HAR-confirmed via may2capture.har)

| Tool | Method | Endpoint | Notes |
|------|--------|----------|-------|
| `ss_create_note_draft(text, force=False)` | POST | `/api/v1/comment/draft` | bodyJson + `replyMinimumRole: "everyone"`. No `trigger_at`. Returns draft id + body. Voice-checked. |
| `ss_schedule_note(text, trigger_at_iso, force=False)` | POST | `/api/v1/comment/draft` | Same body + `trigger_at: "<iso>"`. Voice-checked. Returns draft id. |
| `ss_list_note_drafts(limit=20)` | GET | `/api/v1/feed/drafts?limit=N` | Returns `{drafts: [...], hasMore, nextCursor}`. Includes both unscheduled drafts and scheduled notes. Filter client-side via `trigger_at != null`. |
| `ss_cancel_scheduled_note(comment_id)` | DELETE | `/api/v1/comment/{id}` | Cancels schedule or deletes draft. Empty body. Returns `{}`. |
| `ss_follow(user_id)` | POST | `/api/v1/feed/{user_id}/follow` | Body `{surface: "profile"}`. Returns `{}`. |
| `ss_unfollow(user_id)` | DELETE | `/api/v1/feed/{user_id}/follow` | Body `{surface: "profile"}`. Returns `{}`. |
| `ss_list_following()` | GET | `/api/v1/feed/following` | Returns bare JSON array of user_ids. |

**Deferred to Sprint 8:** `ss_send_dm` (no HAR; Zync realtime token-only confirms inbound push, send transport unknown).

**Permanently out of scope:** `ss_subscribe_to_pub` / `ss_unsubscribe`.

## Test strategy

- Continue TDD per CLAUDE.md sprint protocol. Every tool has a unit test file with mocked httpx responses, dedup interactions, and voice-check coverage where applicable.
- Voice-check covered by its own ~12-test file plus one regression test per write tool that verifies the gate fires for an em-dash input.
- Async dedup gets a concurrency test verifying `/health` stays under 1s while a feed call processes 100 items.
- Target: 240 current → ~340 after sprint. Approximate breakdown: -13 (summarizer removal) + 12 (voice gate) + 45 (Batch 3) + 25 (Batch 4) + 25 (Batch 5) + 3 (concurrency) ≈ +97.

## Sprint protocol per CLAUDE.md

Each batch follows: read PRD section → RED tests → CODE → GREEN → checkpoint (test suite + deploy + reference doc + atomic commit). After all batches, sprint review with code-review and verification agent teams, then final approval commit.

## Risks

- **HAR capture round may reveal one of the Tier 2 endpoints uses non-REST transport.** Mitigation: each Tier 2 tool is independent; one infeasible endpoint does not block the others.
- **Voice rule drift between `references/voice-enforcement-rules.md` and `src/voice_check.py`.** Mitigation: PROGRESS.md gets a checklist item to re-sync after every `veri-gtm:revise-voice-rules` run. Long-term mitigation: read the rules file at server startup. Out of scope for Sprint 7.
- **`google-genai` removal could break unrelated import elsewhere.** Mitigation: grep before removal, verify zero references outside `src/summarizer.py`.

## Out of scope (deferred)

- Pinning posts/notes (no public wrapper).
- Real post analytics (open/click rates) behind CSRF flow.
- Multi-identity (Veri publication separate from Miles personal).
- Streaming reads (`/api/v1/reader/feed` could be consumed via SSE; not needed for current workflows).
- Reading rules file at runtime instead of bundling rules in code.

## Acceptance criteria

- [ ] `google-genai` no longer in requirements.
- [ ] No `summarize` param on any tool. No `summarizer.py` file. `GOOGLE_AI_API_KEY` removed from Fly secrets.
- [ ] `/health` p99 latency under 1s while a 100-item feed call is in flight (concurrency test).
- [ ] All 24 new tools registered, deployed, and callable via the live `/mcp` endpoint.
- [ ] Voice gate fires on em-dash test input for every write-with-text tool. `force=True` bypasses.
- [ ] `ss_navigator` returns the Growth Playbook section.
- [ ] `docs/SUBSTACK_MCP_REFERENCE.md` updated with all new tools/endpoints/schemas, version bumped, changelog updated.
- [ ] `docs/PROGRESS.md` shows `APPROVED` stamp for Sprint 7.
- [ ] Test suite passes with ~340 tests, zero regressions.
- [ ] Final code-review agent gate returns PASS.
