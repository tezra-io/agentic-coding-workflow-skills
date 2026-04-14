---
name: dev-build
description: Implementation workflow for any coding task — feature, bug fix, or refactor. Handles building, code review, fixes, and shipping on main. Loops through active Linear issues by priority for a target project. Language and project agnostic. Use when the user says "build", "implement", "fix", "refactor", or references a task to work on.
---

# Dev Build

Workflow: **Context → Build → Verify → Review → Fix → Ship → Next Issue**.
After all issues are done, run final review sweep + update README if needed.

---

## Phase 0: Context

1. Read the next active issue by **priority** from **Linear** for the target project — description, acceptance criteria, design doc link. If the target project isn't clear, ask the human once at the start (not per issue).
2. `git status` + `git log --oneline -5` — detect uncommitted changes or prior progress
3. **Dependency check**: if this issue depends on another issue (referenced in description or design doc), verify the dependency is marked Done in Linear. If not, skip this issue and move to the next one — don't build on a broken foundation.

**If resuming**: diff what's done vs. what's left, jump to the earliest incomplete phase.

### Complexity assessment

Before spawning sessions, gauge the issue size:

- **Small** (1-3 files, well-understood pattern): full build, skip smoke test, Claude review
- **Medium** (4-10 files or some ambiguity): full flow
- **Large/complex** (cross-cutting, architecture-sensitive, perf/security risk): full flow + deep reasoning prompt to Codex

### Deep reasoning for complex issues

When spawning Codex for **complex** issues, prepend `ULTRATHINK` to the task prompt so it spends more effort on upfront reasoning before editing files.

Use this when the issue has architectural impact, concurrency, tricky state transitions, or failure-mode risk.

**Skip it** for straightforward CRUD, small refactors, or obvious bug fixes.

### Fast Path (trivial changes only)

Fast Path is disabled whenever the work requires Codex ACP. If the issue is truly trivial and can be completed directly in the current session with low risk, you may do so. Otherwise, build with Codex.

## Phase 1: Build

Spawn a **persistent Codex** session (`sessions_spawn` with `runtime: "acp"`, `agentId: "codex"`, `thread: true`, `mode: "session"`) to implement the issue.

Task should include:
- issue title + full description
- acceptance criteria
- relevant file paths / design doc
- explicit instruction to write tests first when appropriate
- explicit instruction to stop after implementation + local verification, without committing

**Fail closed:** If the ACP spawn fails or Codex cannot start, stop and report the exact error. Do not substitute a different builder unless the human approves.

Codex owns the implementation loop until the issue is built and locally verified.

## Phase 2: Verify

**Skip this phase if:** the feature is an internal module with no external interface (traits, engines, data structures, internal refactors). Rely on unit/integration tests from Phase 1 instead.

**For features with an external interface** (API endpoint, CLI command, tool, channel):

Spawn a **separate session** that does NOT read source code. It only knows:
- What the feature does (from the Linear issue description)
- The public API / CLI / interface to interact with it

The verify session must:
1. **Start the app** from scratch (build, run, start server — whatever applies)
2. **Exercise the happy path** — use the feature as described
3. **Exercise failure paths** — bad input, missing data, edge cases
4. **Verify output** — does it return what was promised?

No mocks, no stubs, no reading implementation. Real processes, real calls, real output.

**If verification fails:** send findings back to the build session (Phase 1) for fixes. Loop until green.

---

## Phase 3: Review

**Claude review is mandatory.** The builder session must not review its own work.

Spawn a **Claude Code reviewer** session (`sessions_spawn` with `runtime: "acp"`, `agentId: "claude"`) with a task like:
- review only, do not edit files
- inspect this issue's diff / changed files
- categorize findings as P0, P1, P2
- pay special attention to correctness, edge cases, regressions, test quality, and whether the implementation actually satisfies the issue

For complex issues, tell Claude to review with extra scrutiny on architecture, concurrency, state transitions, and failure modes.

If Claude review cannot run, stop and report the exact error. Do not silently downgrade or skip review.

## Phase 4: Fix

1. Feed P0s (and easy P1s) back to the **builder session** (same persistent Codex session if still alive, otherwise a fresh Codex ACP session).
2. Re-run the relevant local verification.
3. Re-run **Claude review**.
4. Repeat until Claude returns zero P0s.

If the loop stalls, exceeds 5 rounds, or the reviewer and builder keep disagreeing, escalate to the human with the issue, current diff, and review summary.

## Phase 5: Ship

**Only reach this phase after Claude review passes with zero P0s.**

The **orchestrator** performs all steps in this phase. The builder session is not involved.

1. Commit with message format: `feat(TEZ-XXX): <description>` (or `fix(TEZ-XXX):` for bug fixes). Follow CLAUDE.md conventions if they specify a different format.
2. Push to remote
3. Update Linear issue → Done, attach summary of what changed (files modified, key decisions, any follow-ups created)
4. Create follow-up issues for any deferred P1/P2 findings
5. **Terminate the builder session.** Spawn a fresh session for the next issue to avoid context contamination across issues.

---

## Loop

After shipping, go back to **Phase 0: Context**. No confirmation needed — the issues in Linear are the approved work queue. Keep building until:

- **All issues complete** → run Phase 6 Final Review Sweep, then README
- **A build fails and can't be fixed** → stop, report to human

Present a running scorecard after each issue:
```
Progress: 3/8 done
✅ TEZ-175: Sentinel core engine
✅ TEZ-176: Unicode pipeline  
✅ TEZ-177: RedactingChannel decorator
➡️ TEZ-178: Tool scanning (next)
```

---

## Phase 6: Final Review Sweep (Whole Batch)

After all issues are complete, run one final review across the full changed range:

1. Determine diff range: `git diff <hash-before-first-issue>..HEAD`
2. Review architecture consistency across all new modules
3. Review test suite as a whole (missing E2E paths, flaky tests, redundant tests)
4. Verify no regressions between issue boundaries
5. Produce final findings (P0/P1/P2) and either apply fixes or create follow-up Linear issues

This final sweep is mandatory for batches of 3+ issues. For 1-2 issues, the per-issue review is sufficient.

---

## README

Once all issues are shipped:
- New project → create `README.md` with project overview, setup instructions, usage
- Existing project → update if new features, dependencies, or config changed
- No meaningful changes → skip

---

## Invariants

- Code on main always passes build + test + lint
- Linear issue reflects actual state at all times
- Builder and reviewer must be separate sessions (no self-review) — no exceptions
- Trivial changes use Fast Path (no smoke test, no review)
- Issues in Linear are pre-approved work — no confirmation needed between issues
