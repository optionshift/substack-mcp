# Self-Validating Sprint Orchestration Prompt
## substack-mcp — Autonomous Build Execution

**Usage:** Compact conversation, then paste the prompt below into Claude Code to kick off the sprint.

---

## THE PROMPT

~~~
You are executing an autonomous sprint for the substack-mcp project at /Users/mileslozano/mcp-servers/substack. This is a Python MCP server for Substack content ingestion.

BEFORE ANYTHING: Read these files to load full context:
1. /Users/mileslozano/mcp-servers/substack/CLAUDE.md (project rules + Sprint Protocol)
2. /Users/mileslozano/mcp-servers/substack/docs/PRD.md (Mini PRD batches with specs)
3. /Users/mileslozano/mcp-servers/substack/docs/PROGRESS.md (current state)
4. /Users/mileslozano/mcp-servers/substack/docs/DECISIONS.md (architecture decisions)

PRE-EXECUTION CHECK: Read docs/PROGRESS.md. If a batch shows Status="Complete", skip it and move to the next incomplete batch. Do NOT re-execute completed batches.

Execute Batches 1 through 4 (Foundation Sprint: scaffold, auth, subscriptions, dedup cache).
Execute batches SEQUENTIALLY in order. Never parallelize batch execution — later batches depend on earlier ones.

═══════════════════════════════════════════════
SPRINT PROTOCOL — EXECUTE EXACTLY AS WRITTEN
═══════════════════════════════════════════════

This protocol maps to CLAUDE.md's 5-phase Sprint Protocol:
- Phases 1-2 below = CLAUDE.md Phase 1 (Plan) + Phase 2 (TDD Cycle)
- Phase 3 below = Pre-commit gates (from CLAUDE.md Git Workflow section — not a numbered phase, but mandatory before every commit)
- Phase 4 below = CLAUDE.md Phase 3 (Batch Checkpoint)
- Sprint Review below = CLAUDE.md Phase 4 (Sprint Review) + Phase 5 (Final Approval)

For EACH batch, execute these 4 phases in order:

━━━ PHASE 1: PLAN ━━━

Step 1 — Read the batch's Mini PRD section in docs/PRD.md. Identify: scope, files to create, spec (endpoints/params/schemas), test requirements, gate criteria.

Step 2 — Check the "Depends on:" line if present. Verify all dependency batches are complete in PROGRESS.md before proceeding.

━━━ PHASE 2: TDD CYCLE (RED → GREEN) ━━━

Step 1 — RED: Write ALL test files FIRST. Tests must cover every item listed in the batch's "Tests:" line. All external API calls (Substack HTTP, Gemini) must be MOCKED in tests — use `unittest.mock.patch` or `pytest-httpx`. Never make real network calls in the test suite. Run the test suite — confirm tests FAIL (red). If tests pass before implementation, they are not testing anything useful — rewrite them.

Step 2 — CODE: Implement the MINIMUM code to make tests pass. Follow the batch's "Spec:" section exactly — no extras, no optimizations, no speculative features. Every line of code must trace to a PRD requirement.

Step 3 — GREEN: Run the test suite — confirm ALL tests PASS (green). If any test fails, fix the implementation first. If the test itself contains a factual error against the PRD spec, fix the test — but document why in PROGRESS.md. Then run the FULL test suite (all previous batches too) — zero regressions allowed.

BATCH 1 SPECIAL: After creating pyproject.toml, you MUST install the project before running any tests:
  python -m venv .venv && .venv/bin/pip install -e ".[dev]"
IMPORTANT: venv activation does NOT persist across tool calls. For ALL subsequent commands in this sprint, use explicit venv paths:
  .venv/bin/python -m pytest tests/ -v    (not just "python -m pytest")
  .venv/bin/python -c "import pytest; print(pytest.__version__)"
Verify pytest is importable with the command above before proceeding.
pyproject.toml MUST include:
  [project.optional-dependencies]
  dev = ["pytest", "pytest-asyncio", "pytest-httpx"]
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  pythonpath = ["."]

━━━ PHASE 3: PRE-COMMIT VALIDATION GATE ━━━

This gate MUST pass before committing. No exceptions.

Gate 1 — TESTS + TYPE-CHECK: Run `.venv/bin/python -m pytest tests/ -v`. Zero failures. Run type-check if configured (ruff check or mypy). If any fail, fix before proceeding. Do NOT dismiss as pre-existing — verify against the previous commit.

Gate 2 — DIFF AUDIT: Run `git diff --staged` and `git status`. Verify ONLY files from this batch are modified/created. Exception: `__init__.py` files may be updated in any batch that adds a new module to an existing package — this does not violate batch scope. If truly unrelated files appear, unstage them with `git restore --staged <file>`. The batch's Mini PRD "Files to create:" section is the source of truth.

Gate 3 — PRD COMPLIANCE: For each changed file, verify the change maps to a specific line in the batch's Mini PRD section. If you cannot point to a PRD requirement, remove the change. No speculative parameter changes. No "while I'm here" improvements. No docstrings or comments on code you didn't write.

Gate 4 — NO REGRESSIONS: If this is Batch 2+, run the full test suite including all previous batches. Zero regressions. If a previous test breaks, the new code has a bug — fix it before committing.

Gate 5 — CACHING COMPLIANCE (feed tool batches only): For any batch implementing a feed tool (Batches 6, 7, 9, 10), verify: (a) dedup check runs server-side before returning articles, (b) cache insertions happen in server code — never delegated to clients, (c) lookup is by post ID against the `seen_articles` table.

Gate 6 — LIVE-TEST (if required by batch gate): Some batches require live endpoint testing (e.g., Batch 2). If the batch's "Gate:" line includes a live-test requirement AND `SUBSTACK_SESSION_COOKIE` is set, execute the live test. If the live-test fails for ANY reason (credentials missing, network error, unexpected response, rate limit), document in PROGRESS.md with the specific error and note "Live-test deferred" — then proceed with mocked tests only. Do NOT let a live-test failure block the sprint.

━━━ PHASE 4: BATCH CHECKPOINT ━━━

Step 1 — UPDATE PROGRESS: Edit docs/PROGRESS.md — update the batch's row in the tracking table: Status → "Complete", Tests → count, Notes → any deviations or deferred live-tests.

Step 2 — ATOMIC COMMIT: Stage ONLY batch files + PROGRESS.md + any updated `__init__.py` files. Commit with message format:
  "Batch N: [description] — [test count] tests passing"

Step 3 — VERIFY: Run `git log --oneline -1` and `git status` to confirm clean state. Never amend a previous commit without first running `git diff --staged` to verify no unrelated files are included.

═══════════════════════════════════════════════
AFTER ALL BATCHES — SPRINT REVIEW
═══════════════════════════════════════════════

Once all batches in this sprint are committed:

━━━ REVIEW PHASE 1: CODE REVIEW WITH GATES ━━━

Launch 3 agent teams IN PARALLEL:

Agent 1 — Code Reviewer (subagent_type: feature-dev:code-reviewer):
"Review all Python source files in /Users/mileslozano/mcp-servers/substack/src/tools/ for bugs, logic errors, security issues, and adherence to the PRD specs in docs/PRD.md. For each finding: (a) exact file path + line number, (b) direct quote of problematic code, (c) why it's wrong with concrete evidence, (d) confidence level 0-100. RESEARCH ONLY — do not modify files."

Agent 2 — Test Coverage Reviewer (subagent_type: feature-dev:code-reviewer):
"Review all test files in /Users/mileslozano/mcp-servers/substack/tests/ against the PRD Mini PRD batch sections in docs/PRD.md. For each batch, verify: (1) every item in the 'Tests:' line has a corresponding test, (2) edge cases are covered (empty responses, auth failures, network errors), (3) no tests are testing implementation details instead of behavior. Report coverage gaps with specific test names that should exist but don't. Include confidence level 0-100 per finding. RESEARCH ONLY."

Agent 3 — Architecture Reviewer (subagent_type: feature-dev:code-reviewer):
"Review /Users/mileslozano/mcp-servers/substack/src/__init__.py, /Users/mileslozano/mcp-servers/substack/src/server.py, /Users/mileslozano/mcp-servers/substack/src/substack_client.py, and /Users/mileslozano/mcp-servers/substack/src/dedup.py (top-level modules only, NOT src/tools/) for: (1) error shape matches PRD standard {error, code, message, retry_after} everywhere, (2) all imports resolve correctly, (3) no duplicate logic across files, (4) environment variables match CLAUDE.md section, (5) dedup cache follows CLAUDE.md Caching rules. Include confidence level 0-100 per finding. RESEARCH ONLY."

━━━ REVIEW PHASE 2: VERIFICATION GATE ━━━

CRITICAL: When the 3 review agents return, DO NOT present findings yet.

Collect ALL findings from Agents 1, 2, and 3. Concatenate them into a single findings list. Then launch a Verification Agent with the concatenated findings included in the prompt:

Launch a Verification Agent (subagent_type: feature-dev:code-reviewer):
"You are verifying findings from 3 code review agents. For EACH finding listed below, read the cited file at the cited line number. Quote the exact code from the file. Produce a filtered report keeping ONLY findings where the quoted code actually supports the claim. Remove any finding where: the line number is wrong, the quoted code doesn't match, or the reasoning is speculative.

FINDINGS TO VERIFY:
{include the full text output from all 3 agents here}"

The orchestrating agent (you) must construct this prompt by inserting the actual agent outputs where indicated. Do NOT pass the literal placeholder text.

Only present the Verification Agent's filtered findings.

━━━ REVIEW PHASE 3: FIX AND VERIFY ━━━

For each verified finding:
1. Fix the issue
2. Run targeted tests on the affected area
3. Run full test suite — zero regressions

After fixing all findings, write a numbered list of verified findings and fixes to docs/PROGRESS.md under a "Sprint Review Findings" section. Use this list as the authoritative count for the sprint report.

Commit fixes as: "Sprint review: fix [description] — [test count] tests passing"

━━━ REVIEW PHASE 4: FINAL APPROVAL ━━━

1. Run FULL test suite one final time: `.venv/bin/python -m pytest tests/ -v`
2. Run type-check if configured (ruff check or mypy)
3. Launch a final code-review agent (subagent_type: feature-dev:code-reviewer):
   "Final gate review of /Users/mileslozano/mcp-servers/substack/src/. Verify: (1) all tests pass, (2) no unresolved findings from sprint review, (3) error shapes are consistent, (4) dedup logic is correct in all feed tools. Return PASS or FAIL with reasons. RESEARCH ONLY."
   This agent must return PASS before proceeding. If FAIL: fix the reported issues, re-run full test suite, then re-launch the final gate agent. Repeat until PASS. If stuck after 3 attempts, document in PROGRESS.md and stop.
4. Update docs/PROGRESS.md:
   - Each batch row: status, test count, notes
   - Add "APPROVED" stamp with date and total test count
   - Add sprint summary section
5. Final commit: "Sprint [N] APPROVED: [batch range] complete — [total tests] tests, [files changed] files"

━━━ SPRINT REPORT (present to user) ━━━

Generate and display a structured sprint report:

```
## Sprint Report: [Sprint Name]
### Batches Completed: [N]
### Total Tests: [count] passing, 0 failing

| Batch | Status | Tests Added | Files Created | Gate |
|-------|--------|------------|---------------|------|
| 1     | ✓      | N          | file list     | PASS |
| ...   | ...    | ...        | ...           | ...  |

### Code Review Results
- Findings: [N] total → [N] verified → [N] fixed
- [List each verified finding and fix]

### Deviations from Plan
- [Any spec questions, blocked items, or decisions made]

### Test Suite Summary
- Total: [N] tests
- Categories: [N] unit, [N] integration
- Coverage: [areas covered]

### Next Sprint
- Batches [N-M] ready to execute
- Blockers: [any]
```

═══════════════════════════════════════════════
CRITICAL RULES — VIOLATIONS ARE SPRINT FAILURES
═══════════════════════════════════════════════

1. NEVER commit without passing ALL validation gates. No exceptions.
2. NEVER bundle changes from multiple batches in one commit.
3. NEVER write implementation code before tests exist and fail.
4. NEVER dismiss a test failure without verifying it's not a regression.
5. NEVER modify files outside the current batch's scope (exception: `__init__.py` for new modules).
6. NEVER add features, params, or optimizations not in the Mini PRD.
7. NEVER skip the progress log update — it's the audit trail.
8. NEVER present code review findings without running the Verification Agent.
9. NEVER proceed to the next batch if the current batch has failing tests.
10. NEVER make real network calls in tests — all external APIs must be mocked.
11. NEVER amend a commit without first verifying staged files with `git diff --staged`.
12. If blocked, STOP and document the blocker in PROGRESS.md — do NOT improvise.

═══════════════════════════════════════════════

Begin with Batch 1. Read the Mini PRD section for Batch 1 in docs/PRD.md now.
~~~

---

## SPRINT GROUPINGS

Use these groupings to run multi-batch sprints. Execute batches sequentially within each sprint.

| Sprint | Batches | Name | Estimated Tests | Prerequisites |
|--------|---------|------|----------------|---------------|
| Sprint 1 | 1-4 | Foundation | ~25-35 | None |
| Sprint 2 | 5-8 | Core Pipeline | ~35-45 | Sprint 1 complete |
| Sprint 3 | 9-12 | Features | ~30-40 | Sprint 1 + Sprint 2 complete |
| Sprint 4 | 13 | Deploy | Manual verification | Sprints 1-3 complete |

**Dependency notes:**
- Sprint 2 requires Sprint 1: Batch 5 (summarizer) needs package setup from Batch 1; Batch 6 (FYP feed) needs dedup from Batch 4 + summarizer from Batch 5
- Sprint 3 requires Sprint 2: Batch 9 (likes/restacks) needs `user_id` cached from Batch 2 + feed patterns from Batch 6
- Sprint 4 (Deploy) skips the code review phase — proceed directly to post-deploy verification per CLAUDE.md Deployment rules

To run a specific sprint, change the first instruction line:
- Sprint 1: "Execute Batches 1 through 4 (Foundation Sprint)"
- Sprint 2: "Execute Batches 5 through 8 (Core Pipeline Sprint)"
- Sprint 3: "Execute Batches 9 through 12 (Features Sprint)"
- Sprint 4: "Execute Batch 13 (Deploy Sprint) — skip Sprint Review, use Deployment verification only"

---

## RESUMING AFTER INTERRUPTION

If a sprint is interrupted (context limit, error, etc.), compact and paste:

~~~
Resume the substack-mcp sprint. Read these files first:
1. /Users/mileslozano/mcp-servers/substack/CLAUDE.md
2. /Users/mileslozano/mcp-servers/substack/docs/PRD.md
3. /Users/mileslozano/mcp-servers/substack/docs/PROGRESS.md
4. /Users/mileslozano/mcp-servers/substack/docs/DECISIONS.md

Activate the venv: all commands must use `.venv/bin/python` and `.venv/bin/pip` explicitly.

Check PROGRESS.md to determine sprint state:
- If a batch shows "Complete" → skip it
- If a batch shows "Tests Written" → proceed to CODE phase (Step 2 of TDD)
- If a batch shows "In Progress" → check which files exist, read them, then continue from where it left off
- If a batch shows "Not Started" but test files already exist at the expected paths, read those files before re-writing them

Continue from the next incomplete phase following the exact Sprint Protocol. Do NOT re-execute completed batches or phases.

If all batches are "Complete" but no "APPROVED" stamp exists:
- Check if a "Sprint Review Findings" section exists in PROGRESS.md
- If it exists with some findings marked "fixed" and others not → continue fixing from the first unfixed finding
- If it does not exist → execute Sprint Review from Phase 1 (launch review agents)
- If all findings are fixed but no APPROVED stamp → execute Review Phase 4 (Final Approval) only
~~~
