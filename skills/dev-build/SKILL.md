---
name: dev-build
description: Implementation workflow for any coding task — feature, bug fix, or refactor. Handles building, code review, fixes, and shipping on main. Loops through active Linear issues by priority for a target project. Language and project agnostic. Use when the user says "build", "implement", "fix", "refactor", or references a task to work on.
---

# Dev Build

Workflow: **Context → Build → Smoke Test → Review → Fix → Ship → Next Issue**.
After all issues are done, run final review sweep + update README if needed.

---

## Phase 0: Context

1. Read the next active issue by **priority** from **Linear** for the target project — description, acceptance criteria, design doc link
2. `git status` + `git log --oneline -5` — detect uncommitted changes or prior progress

**If resuming**: diff what's done vs. what's left, jump to the earliest incomplete phase.

---

## Phase 1: Build

Spin up a **Claude Code** session with:
- Instructions to read `CLAUDE.md` for build/test/lint commands and conventions
- Linear issue description and acceptance criteria
- Design doc if one exists

Let Claude Code build on **main** branch. Monitor progress — this may take time.

**Gate**: `build + test + lint` must all pass before proceeding. Claude Code iterates until green.

**Stuck?** If Claude Code cannot resolve build/test/lint failures after reasonable attempts, stop and report the issue to the human with context on what failed and what was tried.

Update Linear issue → In Progress.

---

## Phase 2: End-to-End Smoke Test

**Before code review, verify the feature actually works as an end user would use it.**

Spin up a **separate Claude Code session** that does NOT read the source code. It only knows:
- What the feature is supposed to do (from the Linear issue description)
- The public API / CLI / interface to interact with it

The smoke test session must:
1. **Start the app** from scratch (build, run, start server — whatever applies)
2. **Exercise the happy path** — use the feature as described in the issue
3. **Exercise failure paths** — bad input, missing data, permission denied, network errors
4. **Verify output** — does it return what was promised? Are error messages useful?
5. **Try to break it** — unexpected input types, concurrent access, large payloads, empty strings

No mocks, no stubs, no reading implementation. Real processes, real calls, real output.

**If smoke test fails:** Send findings back to the build session (Phase 1) for fixes before proceeding. Loop until smoke test passes.

**If smoke test passes:** Proceed to code review.

---

## Phase 3: Review (Per-Issue, Mandatory)

Once build is green AND smoke test passes, run a **Codex review** for this issue's changes.

Default reviewer:
- ACP runtime: `codex`
- Model: `codex-5.4`

If Codex is unavailable, fallback to Claude reviewer and note fallback in the issue summary.

Reviewer should use the **code-review-expert** skill (`~/.agents/skills/code-review-expert`) for structured review with checklists.

| Axis | Focus |
|------|-------|
| SOLID + Architecture | SRP, OCP, LSP, ISP, DIP violations; code smells; refactor candidates |
| Security | Injection, traversal, auth gaps, race conditions, secrets, runtime risks |
| Quality | Error handling, performance, boundary conditions, dead code, naming |
| Design adherence | Matches design doc? Structural drift? (if design exists) |
| **Test quality** | Tests must verify actual application behavior, not just exist. Check: do tests cover real use cases? Do they test edge cases and failure modes? Are assertions meaningful (not just "it didn't crash")? Would a broken implementation still pass these tests? Flag any test that's testing implementation details instead of behavior. Rewrite weak tests with concrete scenarios. |

Findings:
- **P0** — blocker, fix before shipping
- **P1** — should fix, low effort
- **P2** — log as follow-up issue

---

## Phase 4: Fix

1. Feed P0s (and easy P1s) back to **Claude Code**
2. Re-run `build + test + lint`
3. If P0s existed: reviewers re-check changed code only
4. Log remaining P1/P2s as follow-up issues in Linear

---

## Phase 5: Ship

1. Commit with descriptive message referencing the Linear issue ID
2. Push to remote
3. Update Linear issue → Done, attach summary of changes
4. Create follow-up issues for any deferred P1/P2 findings

---

## Loop

After shipping, present a brief summary of what was completed to the human. Check Linear for remaining active issues in the target project.

- **Issues remain** → confirm with human to continue, then return to **Phase 0** with the next priority issue
- **All issues complete** → run **Phase 6 Final Review Sweep**, then proceed to README

---

## Phase 6: Final Review Sweep (Whole Batch)

After all active issues are complete, run one final **Codex 5.4** review across the full changed range (not just last issue):

1. Review combined diff across all completed issues
2. Re-check architecture consistency across modules
3. Re-check test suite quality as a whole (missing E2E paths, flaky tests, redundant tests)
4. Verify no regressions between issue boundaries
5. Produce final findings summary (P0/P1/P2) and either:
   - apply fixes before final ship, or
   - create follow-up Linear issues

This final sweep is mandatory for multi-issue batches.

---

## README

Once all active issues are shipped (or the human stops the loop):
- New project → create `README.md` with project overview, setup instructions, usage
- Existing project → update if new features, dependencies, or config changed
- No meaningful changes → skip

---

## Invariants

- Code on main always passes build + test + lint
- Linear issue reflects actual state at all times
- Builder and reviewer must be separate sessions (no self-review)
- Per-issue review is mandatory, plus one final batch-level review when all issues are done
