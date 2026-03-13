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

Before spawning sessions, gauge the scope:

- **Trivial** (config, strings, docs, imports, single-line fixes): skip to Fast Path
- **Small** (1-3 files, well-understood pattern): full build, skip smoke test, lightweight review
- **Standard** (4+ files, new logic): full pipeline
- **Complex** (new subsystem, performance-critical, security-sensitive): full pipeline with extra attention to edge cases

### Fast Path (trivial changes only)

For trivial changes that don't affect behavior:
1. Make the change directly (no need to spawn Claude Code for one line)
2. Run `build + test + lint` to verify nothing broke
3. Commit with issue reference, push, update Linear → Done
4. Skip smoke test and code review — they add nothing here
5. Move to next issue

---

## Phase 1: Build

Spawn a **Claude Code** session (`sessions_spawn` with `runtime: "acp"`) with a task that includes:
- "Read CLAUDE.md for build/test/lint commands and conventions"
- The Linear issue description and acceptance criteria (paste full text)
- Design doc path if one exists (e.g., "Read docs/TEZ-175-design.md for the design")
- "Build on main branch. Run build+test+lint until all pass."

Let Claude Code build. It will auto-announce when done.

**Gate**: `build + test + lint` must all pass before proceeding. Claude Code iterates until green.

**Rate-limit fallback:** If Claude Code hits rate limits (HTTP 429, spawn failure, or timeout), immediately fall back to OpenAI Codex (`codex` ACP/runtime) for the same issue. Note the fallback in the issue summary. If both Claude Code and Codex are unavailable, stop and notify the human.

**Stuck?** If the builder cannot resolve build/test/lint failures after reasonable attempts (~3 cycles), stop and report to the human with: what failed, what was tried, and the error output.

Update Linear issue → In Progress.

---

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

**Skip for trivial changes** (handled by Fast Path).

**For small changes** (1-3 files): lightweight review — the orchestrator reads the diff (`git diff HEAD~1`) and checks for obvious issues. No need to spawn a full reviewer session.

**For standard/complex changes:** spawn a reviewer session.

Default reviewer:
- ACP runtime: `codex`
- Model: `codex-5.4`

If Codex is unavailable, fall back to Claude Code as reviewer. Note fallback in summary.

Reviewer task should include:
- "Review the changes in the last commit (`git diff HEAD~1`)"
- "Use the code-review-expert skill at `~/.agents/skills/code-review-expert` for structured review"
- The Linear issue description for context

| Axis | Focus |
|------|-------|
| SOLID + Architecture | SRP, OCP, LSP, ISP, DIP violations; code smells; refactor candidates |
| Security | Injection, traversal, auth gaps, race conditions, secrets, runtime risks |
| Quality | Error handling, performance, boundary conditions, dead code, naming |
| Design adherence | Matches design doc? Structural drift? (if design exists) |
| **Test quality** | Tests must verify actual behavior, not just exist. Check: do tests cover real use cases and edge cases? Are assertions meaningful? Would a broken implementation pass these tests? Flag tests that test implementation details instead of behavior. |

Findings:
- **P0** — blocker, fix before shipping
- **P1** — should fix, low effort
- **P2** — log as follow-up issue

---

## Phase 4: Fix

1. Feed P0s (and easy P1s) back to the **builder session**
2. Re-run `build + test + lint`
3. If P0s existed: reviewer re-checks changed code only
4. Log remaining P1/P2s as follow-up issues in Linear

---

## Phase 5: Ship

1. Commit with message format: `feat(TEZ-XXX): <description>` (or `fix(TEZ-XXX):` for bug fixes). Follow CLAUDE.md conventions if they specify a different format.
2. Push to remote
3. Update Linear issue → Done, attach summary of what changed (files modified, key decisions, any follow-ups created)
4. Create follow-up issues for any deferred P1/P2 findings

---

## Loop

After shipping, move to the next priority issue. No confirmation needed — the issues in Linear are the approved work queue. Keep building until:

- **All issues complete** → run Phase 6 Final Review Sweep, then README
- **A build fails and can't be fixed** → stop, report to human
- **Rate limits on all providers** → stop, report to human

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
- Builder and reviewer must be separate sessions (no self-review) — except for lightweight reviews of small changes
- Trivial changes use Fast Path (no smoke test, no review)
- Issues in Linear are pre-approved work — no confirmation needed between issues
