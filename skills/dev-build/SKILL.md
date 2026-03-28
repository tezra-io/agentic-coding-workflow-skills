---
name: dev-build
description: Implementation workflow for any coding task — feature, bug fix, or refactor. Handles building, code review, fixes, and shipping on main. Loops through active Linear issues by priority for a target project. Language and project agnostic. Use when the user says "build", "implement", "fix", "refactor", or references a task to work on.
---

# Dev Build

Workflow: **Context → Build → Verify → Review → Fix → Ship → Next Issue**.
After all issues are done, run final review sweep + update README if needed.

---

## Phase 0: Usage Gate

Before starting any issue, check Claude Code usage:

```bash
usg claude --json
```

- **Session < 90%** → proceed normally
- **Session ≥ 90%** → parse `resets_at`, sleep until reset, re-check, continue. Fully automatic.
- **Weekly ≥ 90%** → parse `resets_at`, sleep until weekly reset, re-check, continue. Same behavior — wait it out.

Run this check **before every issue**, not just at the start of the loop.

---

## Phase 0b: Context

1. Read the next active issue by **priority** from **Linear** for the target project — description, acceptance criteria, design doc link. If the target project isn't clear, ask the human once at the start (not per issue).
2. `git status` + `git log --oneline -5` — detect uncommitted changes or prior progress
3. **Dependency check**: if this issue depends on another issue (referenced in description or design doc), verify the dependency is marked Done in Linear. If not, skip this issue and move to the next one — don't build on a broken foundation.

**If resuming**: diff what's done vs. what's left, jump to the earliest incomplete phase.

### Complexity assessment

Before spawning sessions, gauge the scope:

- **Trivial** (config, strings, docs, imports, single-line fixes): skip to Fast Path
- **Small** (1-3 files, well-understood pattern): full build, skip smoke test, Codex review
- **Standard** (4+ files, new logic): full pipeline
- **Complex** (new subsystem, performance-critical, security-sensitive): full pipeline with extra attention to edge cases

### ULTRATHINK for complex issues

When spawning Claude Code for **complex** issues, prepend `ULTRATHINK` to the task prompt to trigger extended reasoning.

**Detection**: Before spawning, fetch issue metadata via `linear issue view TEZ-XXX --json` and check labels. If any of these labels are present, use ULTRATHINK:

- `Architecture`, `Design`, `Security`, `Performance`, `Complex`

No fallback heuristics. Labels are the single source of truth — set them explicitly when creating the issue.

When triggered, the Claude Code task prompt should start with:
```
ULTRATHINK

[rest of the task description]
```

This gives Claude Code's extended thinking mode more budget for upfront reasoning — architecture decisions, edge cases, failure modes — before it starts writing code. Don't use it for trivial/small issues; it burns tokens for no benefit.

### Fast Path (trivial changes only)

For trivial changes that don't affect behavior (must be single-file, no logic changes — if it touches conditionals, function bodies, or type signatures, reclassify as Small):
1. Make the change directly (no need to spawn Claude Code for one line)
2. Run `build + test + lint` to verify nothing broke
3. Commit with issue reference, push, update Linear → Done
4. Skip smoke test and code review — they add nothing here
5. Move to next issue

---

## Phase 1: Build

Spawn a **persistent Claude Code** session (`sessions_spawn` with `runtime: "acp"`, `mode: "session"`) so it stays alive for the fix cycle in Phase 4. Task should include:
- "Read CLAUDE.md for build/test/lint commands and conventions"
- The Linear issue description and acceptance criteria (paste full text)
- Design doc path if one exists (e.g., "Read docs/TEZ-175-design.md for the design")
- "Build on main branch. Run build+test+lint until all pass."
- "Do NOT commit or push. Leave changes staged/unstaged. The orchestrator will commit after review."

Let Claude Code build. It will auto-announce when done.

**Gate**: `build + test + lint` must all pass before proceeding. Claude Code iterates until green.

**IMPORTANT: Claude Code must NOT commit or push.** Changes stay uncommitted until Codex review passes (Phase 3-4). This prevents shipping unreviewed code.

**Pre-review validation:** Before starting Phase 3, the orchestrator must run `git log --oneline -1` and verify no new commits were made since Phase 1 started. If Claude Code committed despite the instruction, reset with `git reset HEAD~1` and warn the human. This is the safety net for the no-commit rule.

**Rate-limit handling:** If Claude Code hits rate limits (HTTP 429, spawn failure, or timeout) mid-build, run `usg claude --json`. If session is capped, sleep until `resets_at`, then resume automatically.

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

**Codex review is MANDATORY for all small, standard, and complex changes.** No exceptions. No lightweight orchestrator-only reviews. Claude Code makes mistakes on complex work — Codex catches them.

For **complex** issues (ULTRATHINK-labeled), Codex review runs with extra scrutiny — include "This is a complex/architectural change. Be thorough on edge cases, error handling, and logic correctness." in the reviewer task.

Spawn a reviewer session:

Default reviewer:
- ACP runtime: `codex`
- Model: `codex-5.4`

If Codex is unavailable, fall back to a **separate** Claude Code session as reviewer. The builder session must NOT review its own code. Note the fallback in the issue summary.

Reviewer task should include:
- "Review the uncommitted changes (`git diff`) against the issue requirements"
- "Use the code-review-expert skill at `~/.agents/skills/code-review-expert` for structured review"
- "Your role is AUDIT ONLY. Do NOT make any code changes. Report findings with specific file, line, and suggested fix for each issue."
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

1. Feed P0s (and easy P1s) back to the **builder session** (same persistent session from Phase 1)
2. Re-run `build + test + lint`
3. **Codex re-reviews the FULL diff** after any fix (P0 or P1). This is mandatory — partial re-reviews miss interaction bugs between the fix and original code. A P1 fix can introduce a new P0.
4. Repeat Phase 3→4 loop until Codex returns zero P0s. **Max 3 fix cycles** — if still P0s after 3 rounds, escalate to human with: specific P0s found, attempted fixes, and error output.
5. P1/P2 follow-up issues are created in Phase 5 (not here — avoid duplicates)

---

## Phase 5: Ship

**Only reach this phase after Codex review passes with zero P0s.**

The **orchestrator** performs all steps in this phase. The builder session is not involved.

1. Commit with message format: `feat(TEZ-XXX): <description>` (or `fix(TEZ-XXX):` for bug fixes). Follow CLAUDE.md conventions if they specify a different format.
2. Push to remote
3. Update Linear issue → Done, attach summary of what changed (files modified, key decisions, any follow-ups created)
4. Create follow-up issues for any deferred P1/P2 findings
5. **Terminate the builder session.** Spawn a fresh session for the next issue to avoid context contamination across issues.

---

## Loop

After shipping, go back to **Phase 0: Usage Gate**. Check Claude Code usage before pulling the next issue. No confirmation needed — the issues in Linear are the approved work queue. Keep building until:

- **All issues complete** → run Phase 6 Final Review Sweep, then README
- **A build fails and can't be fixed** → stop, report to human
- **Claude Code session or weekly ≥ 90%** → auto-sleep until reset, then continue

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
