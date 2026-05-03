# Sprint 7 — Substack write tools, voice gate, summarizer removal, async dedup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 24 new MCP tools (write + drafts + scheduling + following), add a voice-enforcement gate, remove the summarizer, and move sqlite work off the asyncio event loop. Live deploy at the end of every batch.

**Architecture:** FastMCP/uvicorn on Fly (LAX). Each tool is a coroutine in `src/tools/<name>.py`, registered as `@mcp.tool()` in `src/server.py`. State lives in SQLite at `/data/ss_navigator.db` accessed via `DedupCache`. Auth is `substack.sid` cookie via `SubstackClient`. Write-with-text tools call `voice_check.check(text)` before posting unless `force=True`.

**Tech Stack:** Python 3.12+, `mcp[server]` (FastMCP), `httpx.AsyncClient`, `sqlite3` (sync wrapped via `asyncio.to_thread`), pytest + pytest-asyncio, fly.io.

**Spec:** `docs/superpowers/specs/2026-05-02-substack-write-tools-and-voice-gate-design.md`

**Source HARs:** `may2capture.har` (Tier 2 actions, 2026-05-02 16:49 PT) plus existing project HARs for Tier 1.

---

## File structure

### Files to create
- `src/voice_check.py` — voice-enforcement primitive (regex-based hard ban + force override)
- `src/tools/publish_note.py`
- `src/tools/restack.py` (also handles unrestack)
- `src/tools/comment_on_post.py` (also handles get_post_comments)
- `src/tools/note_replies.py` (read-only)
- `src/tools/react.py` (generalizes like; ss_like becomes alias)
- `src/tools/delete_content.py` (note + post-comment delete)
- `src/tools/upload_image.py`
- `src/tools/drafts.py` (article-drafts CRUD + publish + schedule)
- `src/tools/note_drafts.py` (Batch 5 — note drafts and scheduling)
- `src/tools/follow.py` (follow + unfollow + list_following)
- `tests/unit/test_voice_check.py`
- `tests/unit/test_publish_note.py`
- `tests/unit/test_restack.py`
- `tests/unit/test_comment_on_post.py`
- `tests/unit/test_note_replies.py`
- `tests/unit/test_react.py`
- `tests/unit/test_delete_content.py`
- `tests/unit/test_upload_image.py`
- `tests/unit/test_drafts.py`
- `tests/unit/test_note_drafts.py`
- `tests/unit/test_follow.py`
- `tests/integration/test_dedup_concurrency.py` — verify /health stays under 1s while feed processes 100 items

### Files to modify
- `src/dedup.py` — convert public methods to `async def` wrapping `asyncio.to_thread`
- `src/server.py` — register new tools, drop summarize param from existing
- `src/tools/fyp_feed.py`, `subscription_feed.py`, `likes.py`, `restacks.py`, `post_content.py`, `saved_posts.py`, `notes_feed.py`, `search_posts.py`, `search_trending.py` — drop `summarize` param + branch, await dedup
- `src/tools/like.py` — convert to thin wrapper around new `ss_react`
- `src/tools/navigator.py` — extend with growth playbook + new tools
- `pyproject.toml` — drop `google-genai` dependency
- `docs/SUBSTACK_MCP_REFERENCE.md` — add all new tools/endpoints, bump version, changelog

### Files to delete
- `src/summarizer.py`
- `tests/unit/test_summarizer.py`

### Fly secrets to remove (after Batch 1 deploy verified)
- `GOOGLE_AI_API_KEY`

---

## Conventions all tasks follow

**Standard error shape** (all tools):
```python
{"error": True, "code": "<CODE>", "message": "<msg>", "retry_after": None}
```
Codes: `VALIDATION`, `AUTH_EXPIRED`, `VOICE_VIOLATION`, `UNKNOWN`, `RATE_LIMITED`.

**Standard 401 handling** (every tool that calls Substack):
```python
if response.status_code == 401:
    return {"error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie expired. Rotate via browser DevTools.",
            "retry_after": None}
```

**Standard non-200 handling**:
```python
if response.status_code != 200:
    return {"error": True, "code": "UNKNOWN",
            "message": f"Unexpected status {response.status_code}",
            "retry_after": None}
```

**Test setup pattern** (every test file starts with):
```python
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST", url="https://substack.com/x"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, url),
    )
```

**Voice-checked write tools** (publish_note, comment_on_post, create_note_draft, schedule_note, update_draft when body changes, create_draft):
```python
from src.voice_check import check as voice_check

violations = voice_check(text)
if violations and not force:
    return {"error": True, "code": "VOICE_VIOLATION",
            "violations": [v.to_dict() for v in violations],
            "message": "Voice check failed. Use force=True to bypass.",
            "retry_after": None}
```

**Run tests** for a single file:
```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/<file>.py -v
```

**Run full suite + type-check**:
```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```

**Deploy + verify** (end of every batch):
```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && fly deploy --remote-only -a ss-nav-3950b79a5cc7
fly status -a ss-nav-3950b79a5cc7
curl -sS -i https://ss-nav-3950b79a5cc7.fly.dev/health
```

---

# Batch 1 — Foundations

Goal: Strip summarizer, async-ify dedup, update navigator with growth playbook. Net surface shrinks; event-loop blocking eliminated.

## Task 1: Remove summarizer

**Files:**
- Delete: `src/summarizer.py`
- Delete: `tests/unit/test_summarizer.py`
- Modify: `pyproject.toml` (remove `google-genai`)
- Modify: `src/tools/fyp_feed.py`, `subscription_feed.py`, `likes.py`, `restacks.py`, `post_content.py`, `saved_posts.py`, `notes_feed.py`, `search_posts.py`, `search_trending.py` — remove `summarize` param + summarization branch
- Modify: `src/server.py` — drop `summarize` keyword from any tool registration
- Modify: `docs/SUBSTACK_MCP_REFERENCE.md` — remove summarize param from tool docs

- [ ] **Step 1: Find every call to summarizer**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
grep -rn "summarizer\|from src.summarizer\|summarize=\|summarize:\|get_summary\|generate_content" src/ tests/ docs/SUBSTACK_MCP_REFERENCE.md
```
Expected: list of files referencing summarizer. Use this list as the surgical edit list.

- [ ] **Step 2: Delete summarizer files**

```bash
rm src/summarizer.py tests/unit/test_summarizer.py
```

- [ ] **Step 3: Remove summarize param from each consumer tool**

For each file in the grep result above (under `src/tools/`), remove:
- `from src.summarizer import summarize` import
- `summarize: bool = False` parameter
- The `if summarize:` branch (replace with the non-summarize path or just inline-remove)

Example transform for `src/tools/fyp_feed.py`:
```python
# BEFORE
async def get_fyp_feed(limit: int = 20, since: str | None = None, summarize: bool = False) -> dict:
    ...
    if summarize:
        article = await summarize_article(article)
    return {"articles": articles}

# AFTER
async def get_fyp_feed(limit: int = 20, since: str | None = None) -> dict:
    ...
    return {"articles": articles}
```

- [ ] **Step 4: Drop google-genai from pyproject.toml**

In `pyproject.toml`, remove the line:
```
"google-genai>=1.0.0",
```

- [ ] **Step 5: Verify no stale references**

```bash
grep -rn "summarizer\|summarize\|google.genai\|google_genai\|google-genai\|GOOGLE_AI_API_KEY" src/ tests/ pyproject.toml
```
Expected: zero matches in `src/` and `tests/`. `GOOGLE_AI_API_KEY` may still appear in deployment scripts/docs noted for separate cleanup.

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: all tests pass. Test count drops by ~13 (summarizer tests removed) plus any tests that exercised the `summarize=True` branch — those need their mocks updated (drop the `mock_summarize` patch and the assertion on summary fields).

If any test references `summarize=True` or `summary` in a returned dict, update the test to use the new no-summarize signature and assert on raw article fields only.

- [ ] **Step 7: Update SUBSTACK_MCP_REFERENCE.md**

In `docs/SUBSTACK_MCP_REFERENCE.md`:
- Remove `summarize` from every tool's parameter list
- Remove the "Summarization" section if present
- Add to Changelog: `- v1.1.0 (2026-05-02): Removed summarizer (Sprint 7 Batch 1).`
- Bump version field from 1.0.0 to 1.1.0

- [ ] **Step 8: Commit**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add -A
git diff --staged --stat
git commit -m "$(cat <<'EOF'
Sprint 7 Batch 1.1: Remove summarizer

- Delete src/summarizer.py and tests/unit/test_summarizer.py
- Remove google-genai dependency
- Strip `summarize` param + branch from 9 read tools
- Bump SUBSTACK_MCP_REFERENCE.md to v1.1.0

Per spec, full articles are always wanted. Summarizer is unused friction.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Task 2: Async-ify dedup

**Files:**
- Modify: `src/dedup.py` — wrap public methods in `asyncio.to_thread`
- Modify: every consumer in `src/tools/` that calls `dedup.insert(...)` / `dedup.exists(...)` / `dedup.list_by_feed(...)` — add `await`
- Test: `tests/unit/test_dedup.py` — async-ify existing tests
- Create: `tests/integration/test_dedup_concurrency.py` — verify non-blocking under load

- [ ] **Step 1: Convert DedupCache public methods to async**

In `src/dedup.py`, add `import asyncio` at top, then convert:

```python
# BEFORE
def insert(self, article_id: str, url: str, title: str, source: str, source_feed: str) -> bool:
    with self._lock:
        cursor = self.conn.execute(
            "SELECT 1 FROM seen_articles WHERE id = ?", (article_id,)
        )
        if cursor.fetchone() is not None:
            return False
        self.conn.execute(
            """INSERT INTO seen_articles (id, url, title, source, first_seen_at, source_feed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (article_id, url, title, source, datetime.now(timezone.utc).isoformat(), source_feed),
        )
        self.conn.commit()
        return True

# AFTER (rename old method to _insert_sync, then add async wrapper)
def _insert_sync(self, article_id: str, url: str, title: str, source: str, source_feed: str) -> bool:
    with self._lock:
        cursor = self.conn.execute(
            "SELECT 1 FROM seen_articles WHERE id = ?", (article_id,)
        )
        if cursor.fetchone() is not None:
            return False
        self.conn.execute(
            """INSERT INTO seen_articles (id, url, title, source, first_seen_at, source_feed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (article_id, url, title, source, datetime.now(timezone.utc).isoformat(), source_feed),
        )
        self.conn.commit()
        return True

async def insert(self, article_id: str, url: str, title: str, source: str, source_feed: str) -> bool:
    return await asyncio.to_thread(self._insert_sync, article_id, url, title, source, source_feed)
```

Apply the same `_<name>_sync` → `async def <name>` pattern to:
- `exists`
- `list_by_feed`

Leave `_run_migrations` and `_migrate_v1` synchronous (called only from `__init__`, which runs once at startup).

- [ ] **Step 2: Update existing dedup tests to use await**

In `tests/unit/test_dedup.py`, find every call like `cache.insert(...)` and convert to `await cache.insert(...)`. Mark every test function `async def` and add `@pytest.mark.asyncio` decorator if missing.

Example:
```python
# BEFORE
def test_insert_new_article(tmp_path):
    cache = DedupCache(db_path=str(tmp_path / "test.db"))
    result = cache.insert("123", "https://x.com/a", "Title", "src", "feed")
    assert result is True

# AFTER
@pytest.mark.asyncio
async def test_insert_new_article(tmp_path):
    cache = DedupCache(db_path=str(tmp_path / "test.db"))
    result = await cache.insert("123", "https://x.com/a", "Title", "src", "feed")
    assert result is True
```

- [ ] **Step 3: Run dedup tests, verify they pass**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_dedup.py -v
```
Expected: all 12 dedup tests pass.

- [ ] **Step 4: Update every consumer to await dedup calls**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
grep -rn "dedup\.\(insert\|exists\|list_by_feed\)\|cache\.\(insert\|exists\|list_by_feed\)" src/tools/
```
For every match, prepend `await ` to the call. The enclosing function is already `async def` (verify this — every tool is async).

- [ ] **Step 5: Write the concurrency integration test**

Create `tests/integration/test_dedup_concurrency.py`:

```python
import asyncio
import time

import pytest

from src.dedup import DedupCache


@pytest.mark.asyncio
async def test_health_endpoint_unblocked_during_bulk_insert(tmp_path):
    """A 100-item dedup batch must not block other coroutines for more than 1s."""
    cache = DedupCache(db_path=str(tmp_path / "test.db"))

    async def fake_health():
        # Simulates the /health endpoint: must respond quickly even under load.
        return {"status": "ok"}

    async def bulk_insert():
        for i in range(100):
            await cache.insert(
                f"id-{i}", f"https://x.com/{i}", f"Title {i}", "src", "feed"
            )

    start = time.monotonic()
    bulk_task = asyncio.create_task(bulk_insert())
    health_results = []
    # Hit "health" 5 times during the bulk insert window
    for _ in range(5):
        await asyncio.sleep(0.05)
        health_start = time.monotonic()
        result = await fake_health()
        health_results.append(time.monotonic() - health_start)
        assert result == {"status": "ok"}
    await bulk_task
    total = time.monotonic() - start

    # Each health probe should complete in well under 100ms even while bulk_insert runs
    assert max(health_results) < 0.1, f"health probe took {max(health_results)}s under load"
    # Total wall-clock should be reasonable
    assert total < 5.0, f"bulk insert took {total}s"
```

- [ ] **Step 6: Run the concurrency test**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/integration/test_dedup_concurrency.py -v
```
Expected: PASS. If health probes are >100ms, the wrapping isn't actually offloading — verify `asyncio.to_thread` is in use.

- [ ] **Step 7: Run full suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: all tests pass. Test count: ~227 (240 - 13 summarizer + 0 net change here, since concurrency test is +1 and dedup tests are async-renamed).

- [ ] **Step 8: Commit**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add -A
git commit -m "$(cat <<'EOF'
Sprint 7 Batch 1.2: Async dedup via asyncio.to_thread

- Convert DedupCache.insert/exists/list_by_feed to async wrappers
  around sync sqlite operations using asyncio.to_thread
- Update all tool callers to await
- Add concurrency integration test verifying health-style probes
  remain under 100ms during bulk insert

Eliminates event-loop blocking that caused Fly health-check flapping.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Task 3: Update navigator with growth playbook + new-tool placeholders

**Files:**
- Modify: `src/tools/navigator.py`

The full Batch 3/4/5 tool list won't exist until those batches land, but the playbook section can be added now and tools added incrementally per batch. Here we add the playbook only.

- [ ] **Step 1: Find the navigator's return structure**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && cat src/tools/navigator.py | head -200
```

The file exposes `TOOLS = [...]`, `WORKFLOWS = [...]`, and `get_navigator()` returning a dict.

- [ ] **Step 2: Add growth playbook section**

In `src/tools/navigator.py`, add a new constant `GROWTH_PLAYBOOK` immediately after `WORKFLOWS`:

```python
GROWTH_PLAYBOOK = {
    "algorithm_weights": {
        "highest": ["restacks", "replies-on-others"],
        "medium": ["shares", "saves"],
        "low": ["likes"],
        "note": "Substack ML head Mike Cohen has confirmed restacks are the dominant signal. Engagement on others' work outweighs your own posting volume.",
    },
    "note_format": {
        "length_words": "64-255",
        "structure": "4-6 short paragraphs with whitespace",
        "hook_first_words": "7-10",
        "hook_pattern": "specific claim, unexpected stat, or identity statement",
        "best_windows_et": ["Tue-Thu 8-10 AM", "Tue-Thu 2-4 PM"],
        "first_4_hours": "decide reach; if no early traction, the note is dead",
    },
    "restack_pattern": {
        "rule": "restack-with-comment beats naked restack for your visibility",
        "naked_restack": "promotes original author only",
        "quote_restack": "highlight one sentence; works for any article including your own",
        "tip": "@-mention the author when restacking with comment so they get notified",
    },
    "article_amplification_7d": [
        "Day 0: announce note linking the post",
        "Day 1: quote-restack the strongest single sentence",
        "Day 2: standalone note with one chart/stat from the piece (no link)",
        "Day 3: 'thing I almost cut' as standalone note",
        "Day 4: reply to a related note from a peer, citing your article",
        "Day 5: 'tiny tutorial' note teaching one concrete thing",
        "Day 6: behind-the-scenes / how-I-wrote-it note",
        "Day 7: contrarian framing note that links back",
    ],
    "free_to_paid": {
        "honest_median": "~3% (not the 5-10% Substack markets)",
        "lifts": ["paywalled chat replies", "paid-only sections", "email automations (rolling out 2026)"],
    },
    "recommendations": {
        "share_of_new_subs_2026": "~40%",
        "tactic": "swap recommendations with peers at similar size/niche; high-ROI compounding",
    },
    "voice_rules_per_format": {
        "x_twitter": "ALL lowercase except proper nouns; 1-2 sentences; no em-dashes/emoji/hashtags",
        "substack_notes": "sentence case; 2-3 sentences; best stuff under 10 words",
        "banned_words": ["leverage", "synergy", "ensure", "revolutionary", "crucial", "delve", "foster", "comprehensive", "however", "essentially", "literally"],
        "hard_ban_chars": ["em dash —", "semicolon ;", "colon : (except 'Word: value' label)"],
        "ai_pattern_phrases": ["not because X. because Y.", "here's the thing", "let that sink in", "the real X isn't Y", "unpopular opinion", "hot take"],
    },
}
```

- [ ] **Step 3: Wire it into the navigator return**

In `get_navigator()`, add `"growth_playbook": GROWTH_PLAYBOOK` to the returned dict.

- [ ] **Step 4: Add or update test for growth_playbook field**

In `tests/unit/test_navigator.py`, add:

```python
@pytest.mark.asyncio
async def test_navigator_includes_growth_playbook():
    from src.tools.navigator import get_navigator

    result = await get_navigator() if asyncio.iscoroutinefunction(get_navigator) else get_navigator()
    assert "growth_playbook" in result
    assert "algorithm_weights" in result["growth_playbook"]
    assert "article_amplification_7d" in result["growth_playbook"]
    assert "voice_rules_per_format" in result["growth_playbook"]
```

(If `get_navigator` is sync, drop the `await` and `@pytest.mark.asyncio`.)

- [ ] **Step 5: Run navigator tests**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_navigator.py -v
```
Expected: all tests pass including the new one.

- [ ] **Step 6: Commit**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add src/tools/navigator.py tests/unit/test_navigator.py
git commit -m "$(cat <<'EOF'
Sprint 7 Batch 1.3: Bake Substack growth playbook into ss_navigator

GROWTH_PLAYBOOK section in nav response covers:
- Algorithm weights (restacks > replies > likes)
- Note format rules (64-255 words, 4-6 paragraphs, hook in first 7-10)
- Restack-with-comment beats naked restack
- 7-day article-to-notes amplification flow
- Free->paid honest median (~3%)
- Recommendations as ~40% of new subs in 2026
- Voice rules + banned words/chars per format

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Task 4: Batch 1 checkpoint — deploy + verify + Fly secret cleanup

- [ ] **Step 1: Run full suite + sanity-check the test count**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: PASS, ~228 tests (240 - 13 summarizer + 1 concurrency + 1 navigator).

- [ ] **Step 2: Deploy to Fly**

```bash
fly deploy --remote-only -a ss-nav-3950b79a5cc7
```
Expected: build succeeds, machine reaches good state.

- [ ] **Step 3: Verify deployment**

```bash
fly status -a ss-nav-3950b79a5cc7
curl -sS -i https://ss-nav-3950b79a5cc7.fly.dev/health
```
Expected: 2 machines, both `started` with 1/1 health passing. `/health` returns 200 with `{"status":"ok","version":"1.0.0"}`.

- [ ] **Step 4: Remove obsolete Fly secret**

```bash
fly secrets unset GOOGLE_AI_API_KEY -a ss-nav-3950b79a5cc7
```
Note: this triggers a redeploy. Verify status again afterward.

- [ ] **Step 5: Update PROGRESS.md**

In `docs/PROGRESS.md`, append:
```
## Sprint 7 — Write tools, voice gate, async dedup

### Batch 1: Foundations — DONE 2026-05-02
- Removed summarizer (8 tools simplified, -13 tests)
- Async dedup via asyncio.to_thread (+1 concurrency test)
- ss_navigator growth playbook added (+1 test)
- Deployed to Fly, verified live, GOOGLE_AI_API_KEY secret removed
- Test count: ~228
```

- [ ] **Step 6: Commit progress + push**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add docs/PROGRESS.md
git commit -m "Sprint 7 Batch 1: progress checkpoint, deployed live

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Batch 2 — Voice gate primitive

## Task 5: src/voice_check.py with hard-ban regex + Violation dataclass

**Files:**
- Create: `src/voice_check.py`
- Create: `tests/unit/test_voice_check.py`

- [ ] **Step 1: Write failing tests first**

Create `tests/unit/test_voice_check.py`:

```python
import pytest

from src.voice_check import check, Violation


class TestVoiceCheck:
    def test_clean_text_passes(self):
        assert check("two years ago i wouldn't know an API from a CLI") == []

    def test_em_dash_blocks(self):
        violations = check("the answer — wait — is no")
        assert any(v.rule == "em_dash" for v in violations)

    def test_en_dash_between_words_blocks(self):
        violations = check("the answer – wait – is no")
        assert any(v.rule == "en_dash_used_as_em" for v in violations)

    def test_semicolon_blocks(self):
        violations = check("we shipped it; nobody noticed")
        assert any(v.rule == "semicolon" for v in violations)

    def test_label_colon_passes(self):
        # 'Word: value' label pattern is the explicit exception per voice rules
        assert check("Compensation to creators: zero.") == []

    def test_inline_colon_blocks(self):
        violations = check("here is the thing about creators: they are not employees")
        assert any(v.rule == "colon" for v in violations)

    def test_banned_word_leverage(self):
        violations = check("we can leverage this for distribution")
        assert any(v.rule == "banned_word" and "leverage" in v.message for v in violations)

    def test_banned_word_revolutionary(self):
        violations = check("this is a revolutionary product")
        assert any(v.rule == "banned_word" and "revolutionary" in v.message for v in violations)

    def test_ai_pattern_not_because(self):
        violations = check("we shipped not because we had to. because we wanted to.")
        assert any(v.rule == "ai_pattern" and "not because" in v.message.lower() for v in violations)

    def test_ai_pattern_heres_the_thing(self):
        violations = check("here's the thing about distribution")
        assert any(v.rule == "ai_pattern" for v in violations)

    def test_ai_pattern_let_that_sink_in(self):
        violations = check("ten thousand creators. let that sink in.")
        assert any(v.rule == "ai_pattern" for v in violations)

    def test_violation_to_dict(self):
        violations = check("we leverage synergy")
        assert len(violations) >= 1
        d = violations[0].to_dict()
        assert "rule" in d and "message" in d and "severity" in d
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_voice_check.py -v
```
Expected: FAIL with `ImportError: No module named 'src.voice_check'`.

- [ ] **Step 3: Implement src/voice_check.py**

Create `src/voice_check.py`:

```python
import re
from dataclasses import dataclass, asdict


BANNED_WORDS = [
    "leverage", "synergy", "ensure", "revolutionary", "crucial",
    "delve", "foster", "comprehensive", "however", "essentially",
    "literally", "basically", "really", "very", "underscore",
    "showcase", "tapestry", "landscape", "multifaceted", "myriad",
    "plethora", "pivotal", "intricate", "realm", "simply",
]

# AI-tell patterns from the article-social-launch skill rubric, plus
# common LLM giveaways. Case-insensitive, matched as substring/phrase.
AI_PATTERNS = [
    r"not because [^.]*?\. ?because",
    r"here'?s the thing",
    r"here'?s what nobody tells you",
    r"the real [^.]*? isn'?t",
    r"that'?s not [^.]*?\. ?that'?s",
    r"let that sink in",
    r"read that again",
    r"full stop\.",
    r"unpopular opinion[:\b]",
    r"hot take[:\b]",
    r"nobody is talking about",
]


@dataclass
class Violation:
    rule: str
    message: str
    severity: str  # "hard" | "soft"
    span: tuple[int, int] | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["span"] is not None:
            d["span"] = list(d["span"])
        return d


_LABEL_COLON_RE = re.compile(r"^\s*\w[\w\s]*?:\s+\S", re.MULTILINE)


def _has_label_colon_only(text: str) -> bool:
    """True if every colon in `text` is the start of a label-pattern line like 'Word: value'."""
    if ":" not in text:
        return True
    # Strip lines that match the label pattern, see if any colon remains.
    stripped = _LABEL_COLON_RE.sub(lambda _: "", text)
    return ":" not in stripped


def check(text: str) -> list[Violation]:
    """Return the list of voice violations in `text`. Empty list = clean."""
    if not text:
        return []

    violations: list[Violation] = []

    # Em dash
    for m in re.finditer(r"—", text):
        violations.append(Violation(
            rule="em_dash",
            message="Em dash banned. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # En dash used between words (not in date ranges like "2024–2025" — those are fine)
    for m in re.finditer(r"(?<=\w)\s*–\s*(?=\w)", text):
        # Skip pure number ranges like "10–20"
        local = text[max(0, m.start() - 4): m.end() + 4]
        if re.search(r"\d\s*–\s*\d", local):
            continue
        violations.append(Violation(
            rule="en_dash_used_as_em",
            message="En dash used as em dash banned. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # Semicolon
    for m in re.finditer(r";", text):
        violations.append(Violation(
            rule="semicolon",
            message="Semicolon banned. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # Colon — except in label pattern (Word: value at line start)
    if not _has_label_colon_only(text):
        # Find each colon NOT in a label pattern
        for m in re.finditer(r":", text):
            # Heuristic: if this colon is at a line start as part of a label, skip
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_to_colon = text[line_start: m.start()]
            after = text[m.end(): m.end() + 2]
            if re.fullmatch(r"\s*\w[\w\s]*", line_to_colon) and after.startswith(" ") and after[1:].strip():
                continue
            violations.append(Violation(
                rule="colon",
                message="Colon banned outside 'Word: value' label pattern. Use a period.",
                severity="hard",
                span=(m.start(), m.end()),
            ))

    # Banned words (whole-word, case insensitive)
    lower = text.lower()
    for word in BANNED_WORDS:
        for m in re.finditer(rf"\b{re.escape(word)}\b", lower):
            violations.append(Violation(
                rule="banned_word",
                message=f"Banned word '{word}'.",
                severity="hard",
                span=(m.start(), m.end()),
            ))

    # AI patterns
    for pat in AI_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            violations.append(Violation(
                rule="ai_pattern",
                message=f"AI-tell phrase matched: '{m.group(0)}'",
                severity="hard",
                span=(m.start(), m.end()),
            ))

    return violations
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_voice_check.py -v
```
Expected: all 12 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add src/voice_check.py tests/unit/test_voice_check.py
git commit -m "$(cat <<'EOF'
Sprint 7 Batch 2: Voice gate primitive (src/voice_check.py)

Hard-ban regex set:
- em dash, en dash used as em
- semicolons, colons (except 'Word: value' label pattern)
- banned-words list (leverage, synergy, revolutionary, ...)
- AI-pattern phrases (not because X. because Y., here's the thing,
  let that sink in, the real X isn't Y, unpopular opinion, hot take)

Violation dataclass with rule/message/severity/span. 12 unit tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Batch 3 — Tier 1 write tools (9 tools)

Each task creates one tool. Same TDD shape: write tests, verify they fail, implement, verify tests pass, register in server, commit. Tasks 6 through 14.

## Task 6: ss_publish_note

**Files:**
- Create: `src/tools/publish_note.py`
- Create: `tests/unit/test_publish_note.py`
- Modify: `src/server.py` — register tool

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_publish_note.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {"id": 12345, "body": "hi"},
        request=httpx.Request("POST", "https://substack.com/api/v1/comment/feed"),
    )


class TestPublishNote:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await publish_note(text="two years ago i wouldn't know an API from a CLI")

        assert result["success"] is True
        assert result["id"] == 12345

    @pytest.mark.asyncio
    async def test_publish_calls_correct_endpoint(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            await publish_note(text="hello")

        mock_client.post.assert_called_once()
        call = mock_client.post.call_args
        assert call.args[0] == "/api/v1/comment/feed"
        body = call.kwargs["json"]
        assert body["bodyJson"]["type"] == "doc"
        assert body["bodyJson"]["content"][0]["content"][0]["text"] == "hello"
        assert body["replyMinimumRole"] == "everyone"

    @pytest.mark.asyncio
    async def test_publish_voice_violation_blocks(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            result = await publish_note(text="we leverage synergy — it's revolutionary")

        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
        assert "violations" in result
        # Endpoint NOT called
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_force_bypasses_voice(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await publish_note(text="we leverage synergy", force=True)

        assert result["success"] is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_missing_cookie(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client", return_value=None):
            result = await publish_note(text="clean text")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"

    @pytest.mark.asyncio
    async def test_publish_401(self):
        from src.tools.publish_note import publish_note

        with patch("src.tools.publish_note.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await publish_note(text="clean text")

        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_publish_note.py -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement src/tools/publish_note.py**

```python
from src.substack_client import create_client
from src.voice_check import check as voice_check


def get_client():
    return create_client()


def _to_prosemirror(text: str) -> dict:
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1", "title": None},
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def publish_note(text: str, attachments: list[str] | None = None, force: bool = False) -> dict:
    if not text or not text.strip():
        return {
            "error": True, "code": "VALIDATION",
            "message": "text is required", "retry_after": None,
        }

    if not force:
        violations = voice_check(text)
        if violations:
            return {
                "error": True, "code": "VOICE_VIOLATION",
                "violations": [v.to_dict() for v in violations],
                "message": "Voice check failed. Use force=True to bypass.",
                "retry_after": None,
            }

    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured. Set SUBSTACK_SESSION_COOKIE.",
            "retry_after": None,
        }

    body = {
        "bodyJson": _to_prosemirror(text),
        "replyMinimumRole": "everyone",
    }
    if attachments:
        body["attachmentIds"] = attachments

    try:
        response = await client.post("/api/v1/comment/feed", json=body)
    except Exception as e:
        return {
            "error": True, "code": "UNKNOWN",
            "message": str(e), "retry_after": None,
        }

    if response.status_code == 401:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie expired. Rotate via browser DevTools.",
            "retry_after": None,
        }

    if response.status_code != 200:
        return {
            "error": True, "code": "UNKNOWN",
            "message": f"Unexpected status {response.status_code}",
            "retry_after": None,
        }

    data = response.json()
    return {
        "success": True,
        "id": data.get("id"),
        "body": data.get("body"),
    }
```

- [ ] **Step 4: Register tool in src/server.py**

In `src/server.py`, add the import:
```python
from src.tools.publish_note import publish_note
```

And the tool registration (place near other write tools like `ss_save_post`):
```python
@mcp.tool()
async def ss_publish_note(text: str, attachments: list[str] | None = None, force: bool = False) -> dict:
    """Publish a Note immediately. Voice-checked. Use force=True to bypass voice check.
    Params: text (required), attachments (optional list of attachment IDs from ss_upload_image), force (default False)."""
    return await publish_note(text=text, attachments=attachments, force=force)
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_publish_note.py -v
```
Expected: all 6 tests pass.

- [ ] **Step 6: Run full suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add src/tools/publish_note.py tests/unit/test_publish_note.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_publish_note with voice gate

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 7: ss_restack and ss_unrestack

**Files:**
- Create: `src/tools/restack.py`
- Create: `tests/unit/test_restack.py`
- Modify: `src/server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_restack.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://substack.com/api/v1/restack/feed"),
    )


class TestRestack:
    @pytest.mark.asyncio
    async def test_restack_post_success(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(target_id="191270969", kind="post")

        assert result["success"] is True
        mock_client.post.assert_called_once()
        call = mock_client.post.call_args
        assert call.args[0] == "/api/v1/restack/feed"
        assert call.kwargs["json"]["postId"] == 191270969
        assert call.kwargs["json"]["commentId"] is None

    @pytest.mark.asyncio
    async def test_restack_note_success(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(target_id="252827081", kind="note")

        body = mock_client.post.call_args.kwargs["json"]
        assert body["commentId"] == 252827081
        assert body["postId"] is None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_restack_invalid_kind(self):
        from src.tools.restack import restack_content

        result = await restack_content(target_id="123", kind="bogus")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_restack_with_quote_voice_blocks(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            result = await restack_content(
                target_id="123", kind="post",
                quote_text="we leverage this revolutionary tool",
            )
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_restack_with_quote_force_bypasses(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            # First call: comment/feed (the quote note); second: restack/feed
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(
                target_id="123", kind="post",
                quote_text="we leverage this", force=True,
            )
        assert result["success"] is True
        # Two POSTs: comment/feed for quote, restack/feed for restack
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_restack_with_clean_quote(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await restack_content(
                target_id="191270969", kind="post",
                quote_text="this changed how i think about distribution",
            )

        assert result["success"] is True
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_unrestack_post(self):
        from src.tools.restack import unrestack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(method="DELETE")
            mock_gc.return_value = mock_client

            result = await unrestack_content(target_id="191270969", kind="post")

        assert result["success"] is True
        mock_client.delete.assert_called_once()
        body = mock_client.delete.call_args.kwargs["json"]
        assert body["postId"] == 191270969

    @pytest.mark.asyncio
    async def test_restack_401(self):
        from src.tools.restack import restack_content

        with patch("src.tools.restack.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(status=401)
            mock_gc.return_value = mock_client

            result = await restack_content(target_id="123", kind="post")
        assert result["error"] is True
        assert result["code"] == "AUTH_EXPIRED"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_restack.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement src/tools/restack.py**

```python
from src.substack_client import create_client
from src.voice_check import check as voice_check


def get_client():
    return create_client()


def _to_prosemirror(text: str) -> dict:
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1", "title": None},
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


def _validate_kind(kind: str) -> dict | None:
    if kind not in ("post", "note"):
        return {
            "error": True, "code": "VALIDATION",
            "message": "kind must be 'post' or 'note'",
            "retry_after": None,
        }
    return None


def _validate_id(target_id: str) -> tuple[int | None, dict | None]:
    try:
        return int(target_id), None
    except (ValueError, TypeError):
        return None, {
            "error": True, "code": "VALIDATION",
            "message": "target_id must be a numeric string",
            "retry_after": None,
        }


def _restack_body(target_id_int: int, kind: str) -> dict:
    return {
        "postId": target_id_int if kind == "post" else None,
        "commentId": target_id_int if kind == "note" else None,
        "tabId": "for-you",
        "surface": "feed",
    }


async def restack_content(
    target_id: str,
    kind: str,
    quote_text: str | None = None,
    force: bool = False,
) -> dict:
    err = _validate_kind(kind)
    if err:
        return err
    target_int, err = _validate_id(target_id)
    if err:
        return err

    if quote_text:
        violations = voice_check(quote_text)
        if violations and not force:
            return {
                "error": True, "code": "VOICE_VIOLATION",
                "violations": [v.to_dict() for v in violations],
                "message": "Voice check failed. Use force=True to bypass.",
                "retry_after": None,
            }

    client = get_client()
    if client is None:
        return {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.",
            "retry_after": None,
        }

    # If quote_text, post the quote-note first
    if quote_text:
        try:
            quote_body = {
                "bodyJson": _to_prosemirror(quote_text),
                "replyMinimumRole": "everyone",
            }
            quote_resp = await client.post("/api/v1/comment/feed", json=quote_body)
            if quote_resp.status_code == 401:
                return {
                    "error": True, "code": "AUTH_EXPIRED",
                    "message": "Session cookie expired.", "retry_after": None,
                }
            if quote_resp.status_code != 200:
                return {
                    "error": True, "code": "UNKNOWN",
                    "message": f"Quote note POST failed: {quote_resp.status_code}",
                    "retry_after": None,
                }
        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    try:
        response = await client.post("/api/v1/restack/feed", json=_restack_body(target_int, kind))
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if response.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if response.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {response.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "quoted": bool(quote_text)}


async def unrestack_content(target_id: str, kind: str) -> dict:
    err = _validate_kind(kind)
    if err:
        return err
    target_int, err = _validate_id(target_id)
    if err:
        return err

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    try:
        response = await client.delete("/api/v1/restack/feed", json=_restack_body(target_int, kind))
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if response.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if response.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {response.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "action": "unrestacked"}
```

- [ ] **Step 4: Register in src/server.py**

```python
from src.tools.restack import restack_content, unrestack_content

@mcp.tool()
async def ss_restack(target_id: str, kind: str, quote_text: str | None = None, force: bool = False) -> dict:
    """Restack a post or note, optionally with a quote-comment Note. Voice-checked when quote_text provided.
    Params: target_id, kind ('post' or 'note'), quote_text (optional), force (bypass voice check)."""
    return await restack_content(target_id=target_id, kind=kind, quote_text=quote_text, force=force)


@mcp.tool()
async def ss_unrestack(target_id: str, kind: str) -> dict:
    """Remove a restack. Params: target_id, kind ('post' or 'note')."""
    return await unrestack_content(target_id=target_id, kind=kind)
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_restack.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/tools/restack.py tests/unit/test_restack.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_restack + ss_unrestack with optional quote-note voice check

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 8: ss_comment_on_post + ss_get_post_comments

**Files:**
- Create: `src/tools/comment_on_post.py`
- Create: `tests/unit/test_comment_on_post.py`
- Modify: `src/server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_comment_on_post.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://example.substack.com/api/v1/post/123/comment"),
    )


class TestCommentOnPost:
    @pytest.mark.asyncio
    async def test_comment_success(self):
        from src.tools.comment_on_post import comment_on_post

        with patch("src.tools.comment_on_post.get_client") as mock_gc, \
             patch("src.tools.comment_on_post.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 99, "body": "great post"})
            mock_gc.return_value = mock_client

            result = await comment_on_post(post_id="191270969", text="great post")

        assert result["success"] is True
        assert result["id"] == 99
        # Endpoint must include the resolved subdomain
        called_url = mock_client.post.call_args.args[0]
        assert "lenny.substack.com" in called_url

    @pytest.mark.asyncio
    async def test_comment_voice_blocks(self):
        from src.tools.comment_on_post import comment_on_post

        with patch("src.tools.comment_on_post.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            result = await comment_on_post(post_id="123", text="we leverage synergy")

        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_comment_with_parent_id(self):
        from src.tools.comment_on_post import comment_on_post

        with patch("src.tools.comment_on_post.get_client") as mock_gc, \
             patch("src.tools.comment_on_post.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 100})
            mock_gc.return_value = mock_client

            await comment_on_post(post_id="123", text="thanks for clarifying", parent_id="55")

        body = mock_client.post.call_args.kwargs["json"]
        assert body["parent_id"] == 55

    @pytest.mark.asyncio
    async def test_get_post_comments(self):
        from src.tools.comment_on_post import get_post_comments

        with patch("src.tools.comment_on_post.get_client") as mock_gc, \
             patch("src.tools.comment_on_post.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(
                data={"comments": [{"id": 1, "body": "x"}]},
                method="GET",
            )
            mock_gc.return_value = mock_client

            result = await get_post_comments(post_id="123")

        assert "comments" in result
        assert len(result["comments"]) == 1
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_comment_on_post.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement src/tools/comment_on_post.py**

```python
import httpx

from src.substack_client import create_client
from src.voice_check import check as voice_check


def get_client():
    return create_client()


async def resolve_publication_subdomain(post_id_int: int) -> str | None:
    """Look up a post's publication subdomain via /api/v1/posts/by-id/{id}.
    Returns the subdomain (e.g., 'lenny') or None on failure."""
    client = get_client()
    if client is None:
        return None
    try:
        resp = await client.get(f"/api/v1/posts/by-id/{post_id_int}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("publication", {}).get("subdomain")
    except Exception:
        return None


async def comment_on_post(
    post_id: str,
    text: str,
    parent_id: str | None = None,
    force: bool = False,
) -> dict:
    if not text or not text.strip():
        return {"error": True, "code": "VALIDATION",
                "message": "text required", "retry_after": None}

    if not force:
        violations = voice_check(text)
        if violations:
            return {
                "error": True, "code": "VOICE_VIOLATION",
                "violations": [v.to_dict() for v in violations],
                "message": "Voice check failed. Use force=True to bypass.",
                "retry_after": None,
            }

    try:
        post_id_int = int(post_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "post_id must be numeric", "retry_after": None}

    parent_int = None
    if parent_id is not None:
        try:
            parent_int = int(parent_id)
        except (ValueError, TypeError):
            return {"error": True, "code": "VALIDATION",
                    "message": "parent_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    subdomain = await resolve_publication_subdomain(post_id_int)
    if subdomain is None:
        return {"error": True, "code": "VALIDATION",
                "message": f"could not resolve publication for post {post_id}",
                "retry_after": None}

    body = {"body": text}
    if parent_int is not None:
        body["parent_id"] = parent_int

    url = f"https://{subdomain}.substack.com/api/v1/post/{post_id_int}/comment"
    try:
        async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
            resp = await http.post(url, json=body)
            await resp.aread()
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    data = resp.json()
    return {"success": True, "id": data.get("id"), "body": data.get("body")}


async def get_post_comments(post_id: str, sort: str = "best_first") -> dict:
    try:
        post_id_int = int(post_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "post_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    subdomain = await resolve_publication_subdomain(post_id_int)
    if subdomain is None:
        return {"error": True, "code": "VALIDATION",
                "message": f"could not resolve publication for post {post_id}",
                "retry_after": None}

    url = f"https://{subdomain}.substack.com/api/v1/post/{post_id_int}/comments"
    params = {"all_comments": "true", "sort": sort}
    try:
        async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
            resp = await http.get(url, params=params)
            await resp.aread()
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return resp.json()
```

- [ ] **Step 4: Register in src/server.py**

```python
from src.tools.comment_on_post import comment_on_post, get_post_comments

@mcp.tool()
async def ss_comment_on_post(post_id: str, text: str, parent_id: str | None = None, force: bool = False) -> dict:
    """Post a comment on a Substack article. Voice-checked. Optionally reply to a parent comment.
    Params: post_id, text, parent_id (optional), force (bypass voice check)."""
    return await comment_on_post(post_id=post_id, text=text, parent_id=parent_id, force=force)


@mcp.tool()
async def ss_get_post_comments(post_id: str, sort: str = "best_first") -> dict:
    """Get the comment tree on a Substack article. Params: post_id, sort ('best_first' default)."""
    return await get_post_comments(post_id=post_id, sort=sort)
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_comment_on_post.py -v
```
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/tools/comment_on_post.py tests/unit/test_comment_on_post.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_comment_on_post + ss_get_post_comments

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 9: ss_get_note_replies (read-only)

**Files:**
- Create: `src/tools/note_replies.py`
- Create: `tests/unit/test_note_replies.py`
- Modify: `src/server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_note_replies.py
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {"commentBranches": []},
        request=httpx.Request("GET", "https://substack.com/api/v1/reader/comment/123/replies"),
    )


class TestGetNoteReplies:
    @pytest.mark.asyncio
    async def test_get_replies_success(self):
        from src.tools.note_replies import get_note_replies

        with patch("src.tools.note_replies.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(
                data={"commentBranches": [{"id": 1, "descendantComments": []}]}
            )
            mock_gc.return_value = mock_client

            result = await get_note_replies(note_id="252827081")

        assert "commentBranches" in result
        mock_client.get.assert_called_once_with(
            "/api/v1/reader/comment/252827081/replies",
            params={},
        )

    @pytest.mark.asyncio
    async def test_get_replies_with_cursor(self):
        from src.tools.note_replies import get_note_replies

        with patch("src.tools.note_replies.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response()
            mock_gc.return_value = mock_client

            await get_note_replies(note_id="252827081", cursor="abc123")

        assert mock_client.get.call_args.kwargs["params"] == {"cursor": "abc123"}

    @pytest.mark.asyncio
    async def test_get_replies_invalid_id(self):
        from src.tools.note_replies import get_note_replies

        result = await get_note_replies(note_id="not-numeric")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
```

- [ ] **Step 2: Run, verify FAIL.**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_note_replies.py -v
```

- [ ] **Step 3: Implement src/tools/note_replies.py**

```python
from src.substack_client import create_client


def get_client():
    return create_client()


async def get_note_replies(note_id: str, cursor: str | None = None) -> dict:
    try:
        note_int = int(note_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "note_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    params = {}
    if cursor:
        params["cursor"] = cursor

    try:
        resp = await client.get(f"/api/v1/reader/comment/{note_int}/replies", params=params)
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return resp.json()
```

- [ ] **Step 4: Register in server.py**

```python
from src.tools.note_replies import get_note_replies

@mcp.tool()
async def ss_get_note_replies(note_id: str, cursor: str | None = None) -> dict:
    """Get replies on a Note thread. Params: note_id, cursor (for pagination)."""
    return await get_note_replies(note_id=note_id, cursor=cursor)
```

- [ ] **Step 5: Run tests, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/note_replies.py tests/unit/test_note_replies.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_get_note_replies

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 10: ss_react (generalize ss_like)

**Files:**
- Create: `src/tools/react.py`
- Create: `tests/unit/test_react.py`
- Modify: `src/tools/like.py` — convert to thin wrapper around ss_react with emoji="❤"
- Modify: `src/server.py`

- [ ] **Step 1: Write tests for ss_react**

```python
# tests/unit/test_react.py
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request("POST", "https://substack.com/api/v1/post/123/reaction"),
    )


class TestReact:
    @pytest.mark.asyncio
    async def test_react_post_default_heart(self):
        from src.tools.react import react

        with patch("src.tools.react.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await react(target_id="123", kind="post")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["reaction"] == "❤"
        assert mock_client.post.call_args.args[0] == "/api/v1/post/123/reaction"

    @pytest.mark.asyncio
    async def test_react_note_thumbs_up(self):
        from src.tools.react import react

        with patch("src.tools.react.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await react(target_id="999", kind="note", emoji="👍")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["reaction"] == "👍"
        assert mock_client.post.call_args.args[0] == "/api/v1/comment/999/reaction"

    @pytest.mark.asyncio
    async def test_react_invalid_kind(self):
        from src.tools.react import react

        result = await react(target_id="1", kind="bogus")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_like_alias_still_works(self):
        from src.tools.like import like_content

        with patch("src.tools.react.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await like_content(id="123", type="post")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["reaction"] == "❤"
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement src/tools/react.py**

```python
from src.substack_client import create_client


def get_client():
    return create_client()


async def react(target_id: str, kind: str, emoji: str = "❤") -> dict:
    if kind not in ("post", "note"):
        return {"error": True, "code": "VALIDATION",
                "message": "kind must be 'post' or 'note'", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    if kind == "post":
        endpoint = f"/api/v1/post/{target_id}/reaction"
        body = {"reaction": emoji, "surface": "reader", "tabId": "for-you"}
    else:
        endpoint = f"/api/v1/comment/{target_id}/reaction"
        body = {"publication_id": None, "reaction": emoji, "tabId": "for-you"}

    try:
        resp = await client.post(endpoint, json=body)
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "emoji": emoji}
```

- [ ] **Step 4: Update src/tools/like.py to delegate**

Replace the body of `src/tools/like.py` with:

```python
from src.tools.react import react


async def like_content(id: str, type: str) -> dict:
    """Backward-compat alias for ss_react with emoji=❤."""
    return await react(target_id=id, kind=type, emoji="❤")
```

Existing tests in `tests/unit/test_like.py` should keep passing because `like_content` is preserved.

- [ ] **Step 5: Register ss_react in server.py**

```python
from src.tools.react import react

@mcp.tool()
async def ss_react(target_id: str, kind: str, emoji: str = "❤") -> dict:
    """React to a post or note with any emoji. Generalizes ss_like.
    Params: target_id, kind ('post' or 'note'), emoji (default ❤)."""
    return await react(target_id=target_id, kind=kind, emoji=emoji)
```

Keep `ss_like` registered (it now delegates internally).

- [ ] **Step 6: Run all relevant tests**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_react.py tests/unit/test_like.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/tools/react.py src/tools/like.py tests/unit/test_react.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_react generalizes reactions; ss_like is alias

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 11: ss_delete (host-disambiguated)

**Files:**
- Create: `src/tools/delete_content.py`
- Create: `tests/unit/test_delete_content.py`
- Modify: `src/server.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/test_delete_content.py
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request("DELETE", "https://substack.com/api/v1/comment/123"),
    )


class TestDeleteContent:
    @pytest.mark.asyncio
    async def test_delete_note_uses_substack_root(self):
        from src.tools.delete_content import delete_content

        with patch("src.tools.delete_content.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await delete_content(target_id="252827081", kind="note")

        assert result["success"] is True
        # delete called against substack.com root via SubstackClient.delete (which uses base_url)
        mock_client.delete.assert_called_once_with("/api/v1/comment/252827081")

    @pytest.mark.asyncio
    async def test_delete_post_comment_uses_publication(self):
        from src.tools.delete_content import delete_content

        with patch("src.tools.delete_content.get_client") as mock_gc, \
             patch("src.tools.delete_content.resolve_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.delete_content.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_resp = _make_response()
                mock_http.delete.return_value = mock_resp
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await delete_content(target_id="50", kind="post_comment", post_id="123")

        assert result["success"] is True
        called_url = mock_http.delete.call_args.args[0]
        assert "lenny.substack.com" in called_url
        assert "/comment/50" in called_url

    @pytest.mark.asyncio
    async def test_delete_post_comment_requires_post_id(self):
        from src.tools.delete_content import delete_content

        result = await delete_content(target_id="50", kind="post_comment")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_delete_invalid_kind(self):
        from src.tools.delete_content import delete_content

        result = await delete_content(target_id="50", kind="bogus")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement src/tools/delete_content.py**

```python
import httpx

from src.substack_client import create_client
from src.tools.comment_on_post import resolve_publication_subdomain


def get_client():
    return create_client()


async def delete_content(target_id: str, kind: str, post_id: str | None = None) -> dict:
    if kind not in ("note", "post_comment"):
        return {"error": True, "code": "VALIDATION",
                "message": "kind must be 'note' or 'post_comment'", "retry_after": None}
    try:
        target_int = int(target_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "target_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    if kind == "note":
        try:
            resp = await client.delete(f"/api/v1/comment/{target_int}")
        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    else:
        if post_id is None:
            return {"error": True, "code": "VALIDATION",
                    "message": "post_id required when kind='post_comment'", "retry_after": None}
        try:
            post_id_int = int(post_id)
        except (ValueError, TypeError):
            return {"error": True, "code": "VALIDATION",
                    "message": "post_id must be numeric", "retry_after": None}

        subdomain = await resolve_publication_subdomain(post_id_int)
        if subdomain is None:
            return {"error": True, "code": "VALIDATION",
                    "message": f"could not resolve publication for post {post_id}",
                    "retry_after": None}
        url = f"https://{subdomain}.substack.com/api/v1/comment/{target_int}"
        try:
            async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
                resp = await http.delete(url)
                await resp.aread()
        except Exception as e:
            return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return {"success": True, "target_id": target_id, "kind": kind, "action": "deleted"}
```

- [ ] **Step 4: Register in server.py**

```python
from src.tools.delete_content import delete_content

@mcp.tool()
async def ss_delete(target_id: str, kind: str, post_id: str | None = None) -> dict:
    """Delete a note or a post comment. For 'post_comment', also pass post_id.
    Params: target_id, kind ('note' or 'post_comment'), post_id (required for post_comment)."""
    return await delete_content(target_id=target_id, kind=kind, post_id=post_id)
```

- [ ] **Step 5: Run tests, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/delete_content.py tests/unit/test_delete_content.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_delete with host disambiguation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 12: ss_upload_image

**Files:**
- Create: `src/tools/upload_image.py`
- Create: `tests/unit/test_upload_image.py`
- Modify: `src/server.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/test_upload_image.py
import base64
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200):
    return httpx.Response(
        status,
        json=data if data is not None else {"url": "https://substackcdn.com/abc.jpg"},
        request=httpx.Request("POST", "https://substack.com/api/v1/image"),
    )


class TestUploadImage:
    @pytest.mark.asyncio
    async def test_upload_with_base64(self):
        from src.tools.upload_image import upload_image

        b64 = base64.b64encode(b"fake image bytes").decode()
        data_uri = f"data:image/jpeg;base64,{b64}"

        with patch("src.tools.upload_image.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await upload_image(image_data=data_uri)

        assert result["success"] is True
        assert result["url"] == "https://substackcdn.com/abc.jpg"

    @pytest.mark.asyncio
    async def test_upload_invalid_format(self):
        from src.tools.upload_image import upload_image

        result = await upload_image(image_data="not-a-data-uri")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement src/tools/upload_image.py**

```python
from src.substack_client import create_client


def get_client():
    return create_client()


async def upload_image(image_data: str) -> dict:
    """Upload an image. image_data must be a data URI like 'data:image/jpeg;base64,...'."""
    if not image_data.startswith("data:image/"):
        return {"error": True, "code": "VALIDATION",
                "message": "image_data must be a data URI like 'data:image/jpeg;base64,...'",
                "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    try:
        resp = await client.post("/api/v1/image", json={"image": image_data})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    data = resp.json()
    return {"success": True, "url": data.get("url"), "raw": data}
```

- [ ] **Step 4: Register in server.py**

```python
from src.tools.upload_image import upload_image

@mcp.tool()
async def ss_upload_image(image_data: str) -> dict:
    """Upload an image. Returns CDN URL usable as note attachment.
    Params: image_data (data URI 'data:image/jpeg;base64,...')."""
    return await upload_image(image_data=image_data)
```

- [ ] **Step 5: Run tests, verify PASS. Commit.**

```bash
git add src/tools/upload_image.py tests/unit/test_upload_image.py src/server.py
git commit -m "Sprint 7 Batch 3: ss_upload_image

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 13: Batch 3 checkpoint — full suite + deploy + reference doc + progress

- [ ] **Step 1: Run full test suite.**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: PASS, ~273 tests (228 + 6 publish_note + 8 restack + 4 comment + 3 note_replies + 4 react + 4 delete + 2 upload + 14 voice_check tests already added in Batch 2 = ~273).

- [ ] **Step 2: Deploy and verify**

```bash
fly deploy --remote-only -a ss-nav-3950b79a5cc7
fly status -a ss-nav-3950b79a5cc7
curl -sS -i https://ss-nav-3950b79a5cc7.fly.dev/health
```
Expected: 2 machines started, health 200.

- [ ] **Step 3: Smoke test the new tools live via MCP inspector**

```bash
# Quick MCP probe (requires OAuth token in $TOKEN; skip if unavailable in this env)
curl -sS -X POST https://ss-nav-3950b79a5cc7.fly.dev/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools[] | .name' | head -30
```
Expected: list includes `ss_publish_note`, `ss_restack`, `ss_comment_on_post`, `ss_get_post_comments`, `ss_get_note_replies`, `ss_react`, `ss_delete`, `ss_upload_image`.

If `$TOKEN` isn't set in the environment, skip this step. The smoke test will be done end-of-sprint.

- [ ] **Step 4: Update SUBSTACK_MCP_REFERENCE.md**

Add 9 new tool entries with method/endpoint/params/response/example. Bump to v1.2.0. Append changelog: `- v1.2.0 (2026-05-02): Sprint 7 Batch 3 — 9 Tier 1 write tools (publish_note, restack, unrestack, comment_on_post, get_post_comments, get_note_replies, react, delete, upload_image). Voice gate enforced.`

- [ ] **Step 5: Update PROGRESS.md**

Append:
```
### Batch 2: Voice gate — DONE 2026-05-02
- src/voice_check.py + 12 tests

### Batch 3: Tier 1 writes — DONE 2026-05-02
- 9 tools, 31 new tests
- Test count: ~273
- Live at https://ss-nav-3950b79a5cc7.fly.dev/mcp
```

- [ ] **Step 6: Commit**

```bash
git add docs/SUBSTACK_MCP_REFERENCE.md docs/PROGRESS.md
git commit -m "Sprint 7 Batch 3 checkpoint: deployed live, docs updated

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Batch 4 — Article drafts CRUD + post scheduling (8 tools)

These all hit the user's own publication subdomain (which we resolve via `ss_auth_check`'s cached profile data). The publication subdomain for Miles is whatever his `username.substack.com` resolves to from `/api/v1/user/profile/self`. The first task adds a helper that fetches it once.

## Task 14: Helper — fetch user's publication subdomain

**Files:**
- Modify: `src/tools/auth.py` to expose `get_my_publication_subdomain()`
- Modify: `tests/unit/test_auth.py` to verify the helper

- [ ] **Step 1: Read existing auth.py**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && cat src/tools/auth.py
```
Confirm where the `/api/v1/user/profile/self` response is parsed and whether a `publications` field is exposed.

- [ ] **Step 2: Add helper that returns the user's primary publication subdomain**

In `src/tools/auth.py`, add (after existing functions):

```python
async def get_my_publication_subdomain() -> str | None:
    """Return the user's primary publication subdomain (e.g., 'mileslozano') or None."""
    result = await auth_check()
    if result.get("error"):
        return None
    pubs = result.get("publications") or []
    if not pubs:
        return None
    # Prefer the first non-null subdomain
    for pub in pubs:
        sub = pub.get("subdomain")
        if sub:
            return sub
    return None
```

If `auth_check()` doesn't already expose `publications`, extend it to include `data.get("publications", [])` in the returned dict.

- [ ] **Step 3: Add test**

In `tests/unit/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_get_my_publication_subdomain():
    from src.tools.auth import get_my_publication_subdomain

    with patch("src.tools.auth.auth_check", new=AsyncMock(return_value={
        "user_id": 1, "name": "x", "publications": [{"subdomain": "mileslozano"}]
    })):
        sub = await get_my_publication_subdomain()
    assert sub == "mileslozano"


@pytest.mark.asyncio
async def test_get_my_publication_subdomain_none():
    from src.tools.auth import get_my_publication_subdomain

    with patch("src.tools.auth.auth_check", new=AsyncMock(return_value={
        "user_id": 1, "name": "x", "publications": []
    })):
        sub = await get_my_publication_subdomain()
    assert sub is None
```

- [ ] **Step 4: Run, verify PASS.**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest tests/unit/test_auth.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/tools/auth.py tests/unit/test_auth.py
git commit -m "Sprint 7 Batch 4 prep: get_my_publication_subdomain helper

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 15: ss_list_drafts + ss_get_draft + ss_delete_draft

**Files:**
- Create: `src/tools/drafts.py` (will hold all 8 drafts/scheduling tools)
- Create: `tests/unit/test_drafts.py`
- Modify: `src/server.py`

This task adds the read+delete trio. Tasks 16–17 add create/update and publish/schedule.

- [ ] **Step 1: Write tests for the read+delete trio**

```python
# tests/unit/test_drafts.py
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="GET"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://x.substack.com/api/v1/drafts"),
    )


class TestListDrafts:
    @pytest.mark.asyncio
    async def test_list_success(self):
        from src.tools.drafts import list_drafts

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = _make_response(
                    data={"drafts": [{"id": 1, "title": "T1"}], "hasMore": False}
                )
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await list_drafts(limit=20)

        assert result["drafts"][0]["title"] == "T1"


class TestGetDraft:
    @pytest.mark.asyncio
    async def test_get_success(self):
        from src.tools.drafts import get_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = _make_response(data={"id": 42, "title": "T"})
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await get_draft(draft_id="42")

        assert result["id"] == 42


class TestDeleteDraft:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        from src.tools.drafts import delete_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.delete.return_value = _make_response(method="DELETE")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await delete_draft(draft_id="42")

        assert result["success"] is True
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Create src/tools/drafts.py with helpers + list/get/delete**

```python
import httpx

from src.substack_client import create_client
from src.tools.auth import get_my_publication_subdomain
from src.voice_check import check as voice_check


def get_client():
    return create_client()


async def _http_request(method: str, url: str, **kwargs):
    """Issue an authenticated request to a publication subdomain URL."""
    client = get_client()
    if client is None:
        return None, {
            "error": True, "code": "AUTH_EXPIRED",
            "message": "Session cookie not configured.", "retry_after": None,
        }
    try:
        async with httpx.AsyncClient(cookies=client.get_cookies(), follow_redirects=True) as http:
            resp = await http.request(method, url, **kwargs)
            await resp.aread()
        return resp, None
    except Exception as e:
        return None, {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}


def _check_status(resp) -> dict | None:
    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}
    return None


async def _resolve_pub() -> tuple[str | None, dict | None]:
    sub = await get_my_publication_subdomain()
    if sub is None:
        return None, {"error": True, "code": "AUTH_EXPIRED",
                      "message": "Could not resolve your publication subdomain. Check ss_auth_check.",
                      "retry_after": None}
    return sub, None


async def list_drafts(limit: int = 20, offset: int = 0) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts"
    resp, err = await _http_request("GET", url, params={"limit": limit, "offset": offset})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return resp.json()


async def get_draft(draft_id: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}"
    resp, err = await _http_request("GET", url)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return resp.json()


async def delete_draft(draft_id: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}"
    resp, err = await _http_request("DELETE", url)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "action": "deleted"}
```

- [ ] **Step 4: Register the three in server.py**

```python
from src.tools.drafts import list_drafts, get_draft, delete_draft

@mcp.tool()
async def ss_list_drafts(limit: int = 20, offset: int = 0) -> dict:
    """List your article drafts. Params: limit, offset."""
    return await list_drafts(limit=limit, offset=offset)


@mcp.tool()
async def ss_get_draft(draft_id: str) -> dict:
    """Fetch a single article draft by id."""
    return await get_draft(draft_id=draft_id)


@mcp.tool()
async def ss_delete_draft(draft_id: str) -> dict:
    """Delete an article draft."""
    return await delete_draft(draft_id=draft_id)
```

- [ ] **Step 5: Run tests, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/drafts.py tests/unit/test_drafts.py src/server.py
git commit -m "Sprint 7 Batch 4: ss_list_drafts + ss_get_draft + ss_delete_draft

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 16: ss_create_draft + ss_update_draft

**Files:**
- Modify: `src/tools/drafts.py` (extend)
- Modify: `tests/unit/test_drafts.py` (extend)
- Modify: `src/server.py`

- [ ] **Step 1: Add tests for create/update**

Append to `tests/unit/test_drafts.py`:

```python
class TestCreateDraft:
    @pytest.mark.asyncio
    async def test_create_voice_blocks(self):
        from src.tools.drafts import create_draft

        result = await create_draft(title="ok", body_markdown="we leverage synergy")
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"

    @pytest.mark.asyncio
    async def test_create_force_bypasses(self):
        from src.tools.drafts import create_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.post.return_value = _make_response(
                    data={"id": 99}, method="POST"
                )
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await create_draft(
                    title="t", body_markdown="we leverage", force=True,
                )
        assert result["success"] is True
        assert result["id"] == 99


class TestUpdateDraft:
    @pytest.mark.asyncio
    async def test_update_title_only(self):
        from src.tools.drafts import update_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.put.return_value = _make_response(method="PUT")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await update_draft(draft_id="42", fields={"title": "new"})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_body_voice_blocks(self):
        from src.tools.drafts import update_draft

        result = await update_draft(
            draft_id="42",
            fields={"body_markdown": "we leverage synergy"},
        )
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement create_draft + update_draft + helper**

Append to `src/tools/drafts.py`:

```python
def _md_to_prosemirror(md: str) -> dict:
    """Minimal markdown-to-ProseMirror converter. For now, paragraph-only."""
    paragraphs = [p.strip() for p in md.split("\n\n") if p.strip()]
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1"},
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]}
            for p in paragraphs
        ],
    }


async def create_draft(
    title: str,
    body_markdown: str,
    subtitle: str | None = None,
    force: bool = False,
) -> dict:
    if not force:
        violations = voice_check(body_markdown) + voice_check(title) + (voice_check(subtitle) if subtitle else [])
        if violations:
            return {"error": True, "code": "VOICE_VIOLATION",
                    "violations": [v.to_dict() for v in violations],
                    "message": "Voice check failed. Use force=True to bypass.",
                    "retry_after": None}

    sub, err = await _resolve_pub()
    if err:
        return err

    body = {
        "draft_title": title,
        "draft_body": _md_to_prosemirror(body_markdown),
    }
    if subtitle:
        body["draft_subtitle"] = subtitle

    url = f"https://{sub}.substack.com/api/v1/drafts"
    resp, err = await _http_request("POST", url, json=body)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    data = resp.json()
    return {"success": True, "id": data.get("id"), "raw": data}


ALLOWED_UPDATE_FIELDS = {
    "title", "subtitle", "slug", "search_engine_title", "search_engine_description",
    "draft_section_id", "body_markdown",
}


async def update_draft(draft_id: str, fields: dict, force: bool = False) -> dict:
    bad = set(fields.keys()) - ALLOWED_UPDATE_FIELDS
    if bad:
        return {"error": True, "code": "VALIDATION",
                "message": f"unsupported fields: {sorted(bad)}",
                "retry_after": None}

    if not force:
        text_to_check = " ".join(
            [str(v) for k, v in fields.items() if isinstance(v, str)]
        )
        if text_to_check.strip():
            violations = voice_check(text_to_check)
            if violations:
                return {"error": True, "code": "VOICE_VIOLATION",
                        "violations": [v.to_dict() for v in violations],
                        "message": "Voice check failed. Use force=True to bypass.",
                        "retry_after": None}

    sub, err = await _resolve_pub()
    if err:
        return err

    body = {}
    for k, v in fields.items():
        if k == "body_markdown":
            body["draft_body"] = _md_to_prosemirror(v)
        elif k == "title":
            body["draft_title"] = v
        elif k == "subtitle":
            body["draft_subtitle"] = v
        else:
            body[k] = v

    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}"
    resp, err = await _http_request("PUT", url, json=body)
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "raw": resp.json()}
```

- [ ] **Step 4: Register both in server.py**

```python
from src.tools.drafts import create_draft, update_draft

@mcp.tool()
async def ss_create_draft(title: str, body_markdown: str, subtitle: str | None = None, force: bool = False) -> dict:
    """Create an article draft. Voice-checked. Params: title, body_markdown, subtitle (optional), force."""
    return await create_draft(title=title, body_markdown=body_markdown, subtitle=subtitle, force=force)


@mcp.tool()
async def ss_update_draft(draft_id: str, fields: dict, force: bool = False) -> dict:
    """Update fields on an existing article draft. Voice-checked when string fields change.
    Params: draft_id, fields (dict of allowed fields), force."""
    return await update_draft(draft_id=draft_id, fields=fields, force=force)
```

- [ ] **Step 5: Run, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/drafts.py tests/unit/test_drafts.py src/server.py
git commit -m "Sprint 7 Batch 4: ss_create_draft + ss_update_draft with voice gate

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 17: ss_publish_draft + ss_schedule_post + ss_unschedule_post

**Files:**
- Modify: `src/tools/drafts.py` (extend)
- Modify: `tests/unit/test_drafts.py` (extend)
- Modify: `src/server.py`

- [ ] **Step 1: Tests**

```python
# Append to tests/unit/test_drafts.py
class TestPublishDraft:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        from src.tools.drafts import publish_draft

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.post.return_value = _make_response(data={"id": 42}, method="POST")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await publish_draft(draft_id="42")
        assert result["success"] is True


class TestSchedulePost:
    @pytest.mark.asyncio
    async def test_schedule_success(self):
        from src.tools.drafts import schedule_post

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.post.return_value = _make_response(method="POST")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await schedule_post(draft_id="42", post_date_iso="2026-06-01T15:00:00Z")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unschedule(self):
        from src.tools.drafts import unschedule_post

        with patch("src.tools.drafts.get_client") as mock_gc, \
             patch("src.tools.drafts.get_my_publication_subdomain", new=AsyncMock(return_value="lenny")):
            mock_client = AsyncMock()
            mock_gc.return_value = mock_client

            with patch("src.tools.drafts.httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http.post.return_value = _make_response(method="POST")
                mock_http_cls.return_value.__aenter__.return_value = mock_http

                result = await unschedule_post(draft_id="42")
        assert result["success"] is True
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement publish/schedule/unschedule**

Append to `src/tools/drafts.py`:

```python
async def publish_draft(draft_id: str, send: bool = True, share_automatically: bool = False) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}/publish"
    resp, err = await _http_request("POST", url, json={"send": send, "share_automatically": share_automatically})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "raw": resp.json()}


async def schedule_post(draft_id: str, post_date_iso: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}/schedule"
    resp, err = await _http_request("POST", url, json={"post_date": post_date_iso})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "scheduled_for": post_date_iso}


async def unschedule_post(draft_id: str) -> dict:
    sub, err = await _resolve_pub()
    if err:
        return err
    url = f"https://{sub}.substack.com/api/v1/drafts/{draft_id}/schedule"
    resp, err = await _http_request("POST", url, json={"post_date": None})
    if err:
        return err
    err = _check_status(resp)
    if err:
        return err
    return {"success": True, "draft_id": draft_id, "action": "unscheduled"}
```

- [ ] **Step 4: Register all three in server.py**

```python
from src.tools.drafts import publish_draft, schedule_post, unschedule_post

@mcp.tool()
async def ss_publish_draft(draft_id: str, send: bool = True, share_automatically: bool = False) -> dict:
    """Publish an article draft now. Params: draft_id, send (email subscribers), share_automatically."""
    return await publish_draft(draft_id=draft_id, send=send, share_automatically=share_automatically)


@mcp.tool()
async def ss_schedule_post(draft_id: str, post_date_iso: str) -> dict:
    """Schedule an article draft for a future date. Params: draft_id, post_date_iso (ISO 8601 UTC)."""
    return await schedule_post(draft_id=draft_id, post_date_iso=post_date_iso)


@mcp.tool()
async def ss_unschedule_post(draft_id: str) -> dict:
    """Cancel a scheduled article publish. Params: draft_id."""
    return await unschedule_post(draft_id=draft_id)
```

- [ ] **Step 5: Run, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/drafts.py tests/unit/test_drafts.py src/server.py
git commit -m "Sprint 7 Batch 4: ss_publish_draft + ss_schedule_post + ss_unschedule_post

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 18: Batch 4 checkpoint — full suite + deploy + reference doc + progress

- [ ] **Step 1: Run full suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: PASS, ~298 tests.

- [ ] **Step 2: Deploy + verify** (commands as in earlier checkpoints).

- [ ] **Step 3: Update SUBSTACK_MCP_REFERENCE.md** with the 8 new tools, bump to v1.3.0, append changelog.

- [ ] **Step 4: Update PROGRESS.md.**

- [ ] **Step 5: Commit checkpoint.**

```bash
git add docs/SUBSTACK_MCP_REFERENCE.md docs/PROGRESS.md
git commit -m "Sprint 7 Batch 4 checkpoint: drafts + scheduling, deployed live

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Batch 5 — Note drafts + scheduling + Following (7 tools, HAR-confirmed)

## Task 19: ss_create_note_draft + ss_schedule_note + ss_list_note_drafts + ss_cancel_scheduled_note

**Files:**
- Create: `src/tools/note_drafts.py`
- Create: `tests/unit/test_note_drafts.py`
- Modify: `src/server.py`

- [ ] **Step 1: Tests**

```python
# tests/unit/test_note_drafts.py
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {"id": 1},
        request=httpx.Request(method, "https://substack.com/api/v1/comment/draft"),
    )


class TestCreateNoteDraft:
    @pytest.mark.asyncio
    async def test_create_unscheduled(self):
        from src.tools.note_drafts import create_note_draft

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 252827081, "trigger_at": None})
            mock_gc.return_value = mock_client

            result = await create_note_draft(text="some clean note text")

        assert result["success"] is True
        assert result["id"] == 252827081
        body = mock_client.post.call_args.kwargs["json"]
        assert "trigger_at" not in body or body["trigger_at"] is None
        assert body["bodyJson"]["content"][0]["content"][0]["text"] == "some clean note text"

    @pytest.mark.asyncio
    async def test_create_voice_blocks(self):
        from src.tools.note_drafts import create_note_draft

        result = await create_note_draft(text="we leverage synergy")
        assert result["error"] is True
        assert result["code"] == "VOICE_VIOLATION"


class TestScheduleNote:
    @pytest.mark.asyncio
    async def test_schedule_success(self):
        from src.tools.note_drafts import schedule_note

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response(data={"id": 252827081, "trigger_at": "2026-06-01T00:00:00.000Z"})
            mock_gc.return_value = mock_client

            result = await schedule_note(text="hi", trigger_at_iso="2026-06-01T00:00:00.000Z")

        assert result["success"] is True
        body = mock_client.post.call_args.kwargs["json"]
        assert body["trigger_at"] == "2026-06-01T00:00:00.000Z"


class TestListNoteDrafts:
    @pytest.mark.asyncio
    async def test_list(self):
        from src.tools.note_drafts import list_note_drafts

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(
                data={"drafts": [
                    {"id": 1, "trigger_at": None},
                    {"id": 2, "trigger_at": "2026-06-01T00:00:00.000Z"},
                ], "hasMore": False, "nextCursor": None},
                method="GET",
            )
            mock_gc.return_value = mock_client

            result = await list_note_drafts()

        assert len(result["drafts"]) == 2
        mock_client.get.assert_called_once_with("/api/v1/feed/drafts", params={"limit": 20})


class TestCancelScheduledNote:
    @pytest.mark.asyncio
    async def test_cancel(self):
        from src.tools.note_drafts import cancel_scheduled_note

        with patch("src.tools.note_drafts.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(method="DELETE")
            mock_gc.return_value = mock_client

            result = await cancel_scheduled_note(comment_id="252827081")

        assert result["success"] is True
        mock_client.delete.assert_called_once_with("/api/v1/comment/252827081")
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement src/tools/note_drafts.py**

```python
from src.substack_client import create_client
from src.voice_check import check as voice_check


def get_client():
    return create_client()


def _to_prosemirror(text: str) -> dict:
    return {
        "type": "doc",
        "attrs": {"schemaVersion": "v1", "title": None},
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def _post_draft(text: str, trigger_at: str | None, force: bool) -> dict:
    if not text or not text.strip():
        return {"error": True, "code": "VALIDATION",
                "message": "text required", "retry_after": None}

    if not force:
        violations = voice_check(text)
        if violations:
            return {"error": True, "code": "VOICE_VIOLATION",
                    "violations": [v.to_dict() for v in violations],
                    "message": "Voice check failed. Use force=True to bypass.",
                    "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}

    body = {
        "bodyJson": _to_prosemirror(text),
        "replyMinimumRole": "everyone",
    }
    if trigger_at:
        body["trigger_at"] = trigger_at

    try:
        resp = await client.post("/api/v1/comment/draft", json=body)
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    data = resp.json()
    return {"success": True, "id": data.get("id"), "trigger_at": data.get("trigger_at"), "raw": data}


async def create_note_draft(text: str, force: bool = False) -> dict:
    return await _post_draft(text=text, trigger_at=None, force=force)


async def schedule_note(text: str, trigger_at_iso: str, force: bool = False) -> dict:
    return await _post_draft(text=text, trigger_at=trigger_at_iso, force=force)


async def list_note_drafts(limit: int = 20) -> dict:
    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}
    try:
        resp = await client.get("/api/v1/feed/drafts", params={"limit": limit})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return resp.json()


async def cancel_scheduled_note(comment_id: str) -> dict:
    try:
        comment_int = int(comment_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "comment_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}
    try:
        resp = await client.delete(f"/api/v1/comment/{comment_int}")
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}

    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}

    return {"success": True, "comment_id": comment_id, "action": "deleted"}
```

- [ ] **Step 4: Register in server.py**

```python
from src.tools.note_drafts import (
    create_note_draft, schedule_note, list_note_drafts, cancel_scheduled_note,
)

@mcp.tool()
async def ss_create_note_draft(text: str, force: bool = False) -> dict:
    """Create a Note draft (unscheduled). Voice-checked. Params: text, force."""
    return await create_note_draft(text=text, force=force)


@mcp.tool()
async def ss_schedule_note(text: str, trigger_at_iso: str, force: bool = False) -> dict:
    """Schedule a Note for a future time. Voice-checked.
    Params: text, trigger_at_iso (ISO-8601 UTC e.g. 2026-06-01T00:00:00Z), force."""
    return await schedule_note(text=text, trigger_at_iso=trigger_at_iso, force=force)


@mcp.tool()
async def ss_list_note_drafts(limit: int = 20) -> dict:
    """List Note drafts and scheduled notes. Filter by trigger_at != null for scheduled."""
    return await list_note_drafts(limit=limit)


@mcp.tool()
async def ss_cancel_scheduled_note(comment_id: str) -> dict:
    """Cancel a scheduled Note (or delete a Note draft). Params: comment_id."""
    return await cancel_scheduled_note(comment_id=comment_id)
```

- [ ] **Step 5: Run, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/note_drafts.py tests/unit/test_note_drafts.py src/server.py
git commit -m "Sprint 7 Batch 5: ss_create_note_draft, ss_schedule_note, ss_list_note_drafts, ss_cancel_scheduled_note

All HAR-confirmed via may2capture.har 2026-05-02.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 20: ss_follow + ss_unfollow + ss_list_following

**Files:**
- Create: `src/tools/follow.py`
- Create: `tests/unit/test_follow.py`
- Modify: `src/server.py`

- [ ] **Step 1: Tests**

```python
# tests/unit/test_follow.py
import pytest
from unittest.mock import patch, AsyncMock
import httpx


def _make_response(data=None, status=200, method="POST"):
    return httpx.Response(
        status,
        json=data if data is not None else {},
        request=httpx.Request(method, "https://substack.com/api/v1/feed/44606/follow"),
    )


class TestFollow:
    @pytest.mark.asyncio
    async def test_follow_success(self):
        from src.tools.follow import follow_user

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.post.return_value = _make_response()
            mock_gc.return_value = mock_client

            result = await follow_user(user_id="44606")

        assert result["success"] is True
        mock_client.post.assert_called_once_with(
            "/api/v1/feed/44606/follow", json={"surface": "profile"}
        )

    @pytest.mark.asyncio
    async def test_follow_invalid_id(self):
        from src.tools.follow import follow_user
        result = await follow_user(user_id="not-numeric")
        assert result["error"] is True
        assert result["code"] == "VALIDATION"


class TestUnfollow:
    @pytest.mark.asyncio
    async def test_unfollow_success(self):
        from src.tools.follow import unfollow_user

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.delete.return_value = _make_response(method="DELETE")
            mock_gc.return_value = mock_client

            result = await unfollow_user(user_id="44606")

        assert result["success"] is True
        mock_client.delete.assert_called_once_with(
            "/api/v1/feed/44606/follow", json={"surface": "profile"}
        )


class TestListFollowing:
    @pytest.mark.asyncio
    async def test_list(self):
        from src.tools.follow import list_following

        with patch("src.tools.follow.get_client") as mock_gc:
            mock_client = AsyncMock()
            mock_client.get.return_value = _make_response(data=[1, 2, 3], method="GET")
            mock_gc.return_value = mock_client

            result = await list_following()

        assert result == {"user_ids": [1, 2, 3]}
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement src/tools/follow.py**

```python
from src.substack_client import create_client


def get_client():
    return create_client()


async def follow_user(user_id: str) -> dict:
    try:
        user_int = int(user_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "user_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}
    try:
        resp = await client.post(f"/api/v1/feed/{user_int}/follow", json={"surface": "profile"})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}
    return {"success": True, "user_id": user_id, "action": "followed"}


async def unfollow_user(user_id: str) -> dict:
    try:
        user_int = int(user_id)
    except (ValueError, TypeError):
        return {"error": True, "code": "VALIDATION",
                "message": "user_id must be numeric", "retry_after": None}

    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}
    try:
        resp = await client.delete(f"/api/v1/feed/{user_int}/follow", json={"surface": "profile"})
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}
    return {"success": True, "user_id": user_id, "action": "unfollowed"}


async def list_following() -> dict:
    client = get_client()
    if client is None:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie not configured.", "retry_after": None}
    try:
        resp = await client.get("/api/v1/feed/following")
    except Exception as e:
        return {"error": True, "code": "UNKNOWN", "message": str(e), "retry_after": None}
    if resp.status_code == 401:
        return {"error": True, "code": "AUTH_EXPIRED",
                "message": "Session cookie expired.", "retry_after": None}
    if resp.status_code != 200:
        return {"error": True, "code": "UNKNOWN",
                "message": f"Unexpected status {resp.status_code}", "retry_after": None}
    return {"user_ids": resp.json()}
```

- [ ] **Step 4: Register in server.py**

```python
from src.tools.follow import follow_user, unfollow_user, list_following

@mcp.tool()
async def ss_follow(user_id: str) -> dict:
    """Follow a Substack user. Params: user_id."""
    return await follow_user(user_id=user_id)


@mcp.tool()
async def ss_unfollow(user_id: str) -> dict:
    """Unfollow a Substack user. Params: user_id."""
    return await unfollow_user(user_id=user_id)


@mcp.tool()
async def ss_list_following() -> dict:
    """List user_ids you follow."""
    return await list_following()
```

- [ ] **Step 5: Run, verify PASS.**

- [ ] **Step 6: Commit**

```bash
git add src/tools/follow.py tests/unit/test_follow.py src/server.py
git commit -m "Sprint 7 Batch 5: ss_follow + ss_unfollow + ss_list_following (HAR-confirmed)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 21: Batch 5 checkpoint — full suite + deploy + reference doc + progress + navigator update

- [ ] **Step 1: Run full suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: PASS, ~336 tests.

- [ ] **Step 2: Deploy + verify** (commands as before).

- [ ] **Step 3: Update SUBSTACK_MCP_REFERENCE.md** — add 7 new tools, bump to v1.4.0.

- [ ] **Step 4: Update navigator TOOLS list with all new tools**

In `src/tools/navigator.py`, append to the `TOOLS = [...]` list entries for:
- ss_publish_note, ss_restack, ss_unrestack, ss_comment_on_post, ss_get_post_comments, ss_get_note_replies, ss_react, ss_delete, ss_upload_image
- ss_list_drafts, ss_get_draft, ss_create_draft, ss_update_draft, ss_delete_draft, ss_publish_draft, ss_schedule_post, ss_unschedule_post
- ss_create_note_draft, ss_schedule_note, ss_list_note_drafts, ss_cancel_scheduled_note
- ss_follow, ss_unfollow, ss_list_following

Each entry: `{"name": "<tool_name>", "description": "<one-line>"}`.

- [ ] **Step 5: Run navigator test, verify PASS.**

```bash
pytest tests/unit/test_navigator.py -v
```

- [ ] **Step 6: Update PROGRESS.md.**

- [ ] **Step 7: Commit**

```bash
git add docs/SUBSTACK_MCP_REFERENCE.md docs/PROGRESS.md src/tools/navigator.py
git commit -m "Sprint 7 Batch 5 checkpoint: 7 HAR-confirmed tools, navigator updated, deployed live

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Sprint 7 Final Phase — Sprint Review + Approval

## Task 22: Code review pass with parallel agent teams

This task uses agent teams per CLAUDE.md sprint protocol. Per CLAUDE.md: launch reviewers; do not present findings yet; re-read every cited file; remove any unverified finding; then present only verified findings.

- [ ] **Step 1: Launch 4 parallel code-reviewer agents**

Spawn agents in parallel (single message, multiple Agent calls). Each is a `feature-dev:code-reviewer` agent scoped to a slice of the changes.

Agent 1 — Foundations + voice gate:
> Review changes in src/dedup.py, src/voice_check.py, all tests/unit/test_voice_check.py and tests/unit/test_dedup.py, tests/integration/test_dedup_concurrency.py. Confirm event-loop blocking is eliminated. Confirm voice rules cover the spec's hard ban list (em dash, en dash, semicolon, colon-except-label, banned words, AI patterns). Cite file paths + line numbers + direct code quotes for every finding.

Agent 2 — Tier 1 writes (Batch 3):
> Review src/tools/publish_note.py, restack.py, comment_on_post.py, note_replies.py, react.py, delete_content.py, upload_image.py and their test files. Verify voice-gate is applied on every write-with-text and bypass-able via force=True. Verify error shape consistency. Cite findings with file:line + quote.

Agent 3 — Drafts (Batch 4):
> Review src/tools/drafts.py and tests/unit/test_drafts.py, plus the auth.py helper get_my_publication_subdomain. Verify each of the 8 drafts/scheduling tools mocks correctly and matches the spec's endpoint paths. Cite findings.

Agent 4 — Note drafts + Following (Batch 5):
> Review src/tools/note_drafts.py and src/tools/follow.py and their tests. Verify endpoints match HAR-confirmed paths from may2capture.har: POST /api/v1/comment/draft, DELETE /api/v1/comment/{id}, POST /api/v1/feed/{user_id}/follow with {surface: "profile"}, GET /api/v1/feed/following. Cite findings.

- [ ] **Step 2: Receive findings, then VERIFY each one**

For every finding from every agent:
1. Read the cited file at the cited line range
2. Confirm the quote matches actual code
3. Keep the finding only if verified

This is the per-CLAUDE.md "Verification Agent" pattern. Drop any finding you can't confirm with actual code.

- [ ] **Step 3: Fix verified findings**

For each verified finding, make the requested change. Test after each fix.

- [ ] **Step 4: Run full suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q
```
Expected: PASS.

- [ ] **Step 5: Commit any review fixes**

```bash
git add -A
git commit -m "Sprint 7 review: verified fixes from code-reviewer agent teams

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

## Task 23: Final approval — full suite, smoke test, deploy verification

- [ ] **Step 1: Full test suite**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack && pytest -q --tb=short
```
Expected: PASS, zero failures.

- [ ] **Step 2: Final deploy + verification**

```bash
fly deploy --remote-only -a ss-nav-3950b79a5cc7
fly status -a ss-nav-3950b79a5cc7
curl -sS -i https://ss-nav-3950b79a5cc7.fly.dev/health
```
Expected: 2 machines started, health 200.

- [ ] **Step 3: Live smoke test of new tools** (if MCP token available)

If `MCP_AUTH_TOKEN` is exposed in the env, run:

```bash
TOKEN=$(fly secrets list -a ss-nav-3950b79a5cc7 | grep MCP_AUTH_TOKEN || echo "missing")
# If missing, skip this step and document a manual smoke test as TODO.
```

Otherwise document a manual smoke check in PROGRESS.md: "Live MCP smoke test deferred — requires interactive client (Claude.ai connector)."

- [ ] **Step 4: Final code-review agent gate**

Spawn one more `pr-review-toolkit:code-reviewer` agent over the entire branch diff with prompt: "Review the entire Sprint 7 diff against the spec at docs/superpowers/specs/2026-05-02-substack-write-tools-and-voice-gate-design.md. Return PASS or list any blocking issues with file:line + quotes."

If FAIL: fix verified blockers, re-run from Step 1.
If PASS: continue.

- [ ] **Step 5: Final PROGRESS.md update**

Append:
```
### Sprint 7 — APPROVED 2026-05-02
- 24 new tools (Batch 1: foundations, Batch 2: voice gate, Batch 3: 9 Tier 1 writes, Batch 4: 8 drafts/scheduling, Batch 5: 7 note-drafts + following)
- Test count: ~336
- All deployed live at https://ss-nav-3950b79a5cc7.fly.dev/mcp
- Summarizer removed; google-genai dropped; GOOGLE_AI_API_KEY secret removed
- Async dedup eliminates event-loop blocking
- Voice gate enforces hard bans on every write-with-text tool (force=True bypass)
- Growth playbook baked into ss_navigator
```

- [ ] **Step 6: Final atomic commit**

```bash
cd /Users/mileslozano/mcp-servers/social-mcps/substack
git add docs/PROGRESS.md
git diff --staged
git commit -m "$(cat <<'EOF'
Sprint 7 APPROVED — 24 new tools, 336 tests, live and verified

Includes:
- Foundations: removed summarizer, async dedup
- Voice gate: hard-ban regex set with force=True override
- 9 Tier 1 write tools (publish_note, restack, unrestack, comment_on_post,
  get_post_comments, get_note_replies, react, delete, upload_image)
- 8 article drafts + scheduling (list/get/create/update/delete drafts,
  publish_draft, schedule_post, unschedule_post)
- 7 HAR-confirmed note-drafts + following (create_note_draft, schedule_note,
  list_note_drafts, cancel_scheduled_note, follow, unfollow, list_following)
- Growth playbook baked into ss_navigator
- Deployed and verified at https://ss-nav-3950b79a5cc7.fly.dev/mcp

Sprint 8 candidates (deferred): ss_send_dm, ss_reply_to_note.
Permanently out of scope: ss_subscribe_to_pub.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-review checklist

After completing all tasks above:

1. Every spec acceptance criterion has a corresponding task ✓
2. No "TBD" / "TODO" placeholders in any task body ✓
3. Tool method signatures consistent across files (e.g., `kind` param uniform across react/restack/delete) ✓
4. Voice gate applied on every text-posting tool ✓
5. Error shape consistent across every tool (`{error, code, message, retry_after}`) ✓
6. Every batch ends with deploy + verify + reference doc + progress + commit ✓

If any item fails self-review, return to that task and fix inline before proceeding to the next batch.
