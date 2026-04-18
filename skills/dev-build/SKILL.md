---
name: dev-build
description: Implementation workflow for coding tasks. Iterates Linear issues by priority per project. Spawns Codex for TDD-style implementation, runs full gate, Claude review, fix loop, and ships on main. Use when the user says "build", "implement", "fix", or references a task to work on.
---

# Dev Build

This skill processes one project at a time. The caller (cron prompt or user)
chooses the target project and invokes this skill. The skill iterates that
project's actionable issues by priority until the project is clear or blocked.

Workflow per issue: **Fetch Issue -> Build (TDD) -> Full Gate -> Review -> Evaluate Findings -> Fix -> Ship -> Next Issue**.

The Linear issue is the source of truth for what to build. Preserve and pass
the issue description, acceptance criteria, implementation notes, and relevant
comments to Codex. The orchestrator may add workflow constraints around the
issue text, but must not replace the issue instructions with a loose summary.

OpenClaw supervises. Codex does all repo work: git inspection, formatting,
linting, tests, full gates, code edits, commits, and pushes.

## Paths

- Blocker latch: `/Users/sujshe/.openclaw/workspace/dev-sessions/state/night-build-blocked.json`
- Night memory: `/Users/sujshe/.openclaw/workspace/dev-sessions/memory/YYYY-MM-DD-night.md`
- Project registry: `/Users/sujshe/.openclaw/workspace/PROJECTS.yaml`

## CLI Invocations

OpenClaw orchestrates via the `exec` tool and invokes the Codex and Claude CLIs
directly. No ACP subagents, no announce-timeout. Each run is bounded by the
`exec` tool's per-call `timeoutSec`.

Prompts are passed via heredoc on stdin — no prompt files to maintain, no shell
escaping, no ARG_MAX concerns, safe for any content (code snippets, JSON
blobs, quotes, `$`, backticks). The quoted `<<'EOF'` delimiter prevents shell
expansion inside the prompt.

**Verify CLI flags once against your installed versions** —
`codex exec --help` and `claude --help`. The skill assumes:

- Codex new session: `codex exec`
- Codex continuation: `codex exec resume --last` (fallback if `--last` is not
  supported: capture the session id printed by the initial run, then use
  `codex exec resume <session-id>`).
- Claude new session (print mode): `claude -p`
- Claude continuation: `claude -p --continue` (fallback: `claude -p --resume <session-id>`).

### Codex builder / fixer / shipper — new session

```bash
exec(
  cwd="<repo>",
  timeoutSec=1800,
  command="""
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  <<'CODEX_EOF'
<builder prompt>
CODEX_EOF
"""
)
```

### Codex continuation — follow-up work in the same project

```bash
exec(
  cwd="<repo>",
  timeoutSec=1800,
  command="""
codex exec resume --last \
  --dangerously-bypass-approvals-and-sandbox \
  <<'CODEX_EOF'
<next task prompt>
CODEX_EOF
"""
)
```

### Claude reviewer — new session, per issue

```bash
exec(
  cwd="<repo>",
  timeoutSec=1200,
  command="""
claude -p \
  --dangerously-skip-permissions \
  <<'CLAUDE_EOF'
<reviewer prompt>
CLAUDE_EOF
"""
)
```

### Claude continuation — if review is incomplete or asks to continue

```bash
exec(
  cwd="<repo>",
  timeoutSec=1200,
  command="""
claude -p --continue \
  --dangerously-skip-permissions \
  <<'CLAUDE_EOF'
Continue the review you started. Finish it in one run.
CLAUDE_EOF
"""
)
```

### Output handling

The CLI exits non-zero on failure. The orchestrator parses stdout for the
structured output contract — `CHANGED_FILES` / `VERIFICATION` / `SUMMARY` or
`FAILED_NO_CHANGES` for Codex; `OUTCOME` / `FINDINGS` / `SUMMARY` for Claude.
No separate status-polling step is needed — process exit is the completion
signal.

---

## Phase 0: Issue Selection

The caller provides the target project. This skill fetches and processes its
issues.

1. Fetch Linear issues for the target project, sorted by priority. Skip issues
   that are Done, Cancelled, or Blocked.
2. If an issue depends on another issue that is not Done, skip it.
3. If no actionable issues exist, return to the caller with status `clear`.

### Repo state check

The repo state check is done by Codex inside the CLI run, not by OpenClaw.
Before changing files, Codex must run and report:

```bash
git branch --show-current
git status --short
git log --oneline -5
```

- Night builds work on the repo default branch (`main`). Do not create
  `night/`, `feature/`, or `dev` branches.
- If on a non-default branch, switch back when safe. If ambiguous branch-local
  work exists, block.
- If dirty, check whether the changes relate to a prior issue in the same
  project (check night memory and recent git log). If they do, continue on
  top of them. If the changes are unrelated or you cannot determine their
  origin, block.
- Lock files (`pnpm-lock.yaml`, `package-lock.json`, `Cargo.lock`, etc.) are
  not blockers. Stage and include them if they result from dependency changes.
- If dirty with the current issue's in-progress work, resume.

If the repo is unsafe to continue, Codex must stop without editing and return
`FAILED_NO_CHANGES: <exact blocker>`.

## Phase 1: Build (TDD)

Run the Codex CLI for the project. For the first issue in a project use
`codex exec` (new session). For follow-up issues **in the same project**, use
`codex exec resume --last` so Codex retains codebase context from the previous
issue. Capture any session id printed by the CLI — it's the fallback if
`--last` is not supported or the most-recent-session pointer gets lost.

**Session continuation is scoped to the current project only.** When the
caller moves to a different project, start a fresh `codex exec` (new session)
in the new repo. Do not carry a session from one project's repo into another.

When continuing a session for a follow-up issue, instruct Codex to run
`/compact` before starting any new work to free up context from the previous
issue.

If continuation fails (the CLI reports no session to resume, or the prior
session id is invalid), fall back to a fresh `codex exec` call and instruct
Codex to read the repo's AGENTS.md and explore the codebase structure before
making any changes.

### Orchestrator pre-work

Before spawning Codex, prepare a concrete brief:

1. Read the issue description, acceptance criteria, implementation notes,
   relevant comments, and any linked design docs.
2. Read the project's `CLAUDE.md` (or `AGENTS.md` / `.agents/`) for conventions
   and commands. Codex auto-reads `AGENTS.md` and `.agents/` from the repo root,
   so do not repeat their content in the builder prompt.
3. Find design docs or implementation plans linked in the issue or in the
   repo's `docs/` directory. Include the path in the builder prompt if found.
4. If existing interfaces, types, or stubs are relevant, include them as
   reference. For new implementations where files don't exist yet, skip this.
5. Identify the gate commands (from project config or `PROJECTS.yaml`).

### Builder prompt

The Linear issue contains the implementation instructions. Pass them to Codex
verbatim with this structure:

```text
You are the Codex builder for <issue-id>: <issue-title>.

Repo: <cwd>
Branch: stay on the repo default branch. Do not create or switch branches.
Do not commit or push yet — you will be told to ship after review passes.

## Task

<issue description, acceptance criteria, implementation notes, and relevant
Linear comments pasted verbatim>

## References

<design doc or implementation plan path, if available>
<relevant interfaces/types/stubs from the codebase, if they exist>

## Approach

First, run the repo state check:
- git branch --show-current
- git status --short
- git log --oneline -5

If the repo is on the wrong branch or dirty with unrelated/ambiguous work, stop
without editing and return FAILED_NO_CHANGES with the exact blocker.

Before writing any code, read the repo's AGENTS.md (or CLAUDE.md) and explore
the codebase to understand the existing architecture, module boundaries, and
how similar features are wired together. Understand where your changes need to
integrate before you start implementing.

Deliver a complete, integrated feature — not just isolated code. Wire your
implementation into the rest of the system: update callers, register routes,
add exports, connect config, and update any entry points so the feature is
actually reachable and functional without manual follow-up.

Prefer tests first: write or update the failing test that proves the requested
behavior, then implement until the tests pass. If the repo already has a test
pattern, follow it. If tests-first is not practical, explain why in the final
summary and still add appropriate coverage before finishing.

## Gate

Run before finishing. Include formatting, linting, tests, and any full gate
configured for this project:
<gate commands from project config>

## Output

End with exactly one of:

CHANGED_FILES:
- <path>

SUMMARY:
<what you did>

VERIFICATION:
- <command>: <pass/fail and key output>
- git status --short: <output>
- git diff --name-only: <output>

or:

FAILED_NO_CHANGES: <exact blocker>
```

### Outcome check

After every Codex run, inspect the CLI's stdout (and stderr on non-zero exit).
Do not run repo commands from OpenClaw.

- Missing changed files, missing `git status --short`, missing
  `git diff --name-only`, or missing verification output = no-op.
- Commentary-only output = no-op.
- Non-zero exit with no structured output = treat as failure, not no-op;
  report stderr in the blocker evidence.
- First no-op gets one corrective retry via `codex exec resume --last` with
  concrete evidence of what was missing and explicit file-level instructions.
- Second no-op = hard blocker. Write latch, log to memory, stop queue.

If Codex asks a question inferable from the issue, design doc, repo, or
instructions, answer once via `codex exec resume --last` to continue the same
session. Only escalate for real product decisions, missing credentials,
missing external facts, or unresolvable ambiguity.

## Phase 2: Gate

Codex runs the project's full gate after producing a real diff. OpenClaw does
not run gate commands directly.

```bash
<gate command from PROJECTS.yaml>
<any additional gate commands from project CLAUDE.md or package scripts>
```

If the full gate fails:

- Have Codex compare against clean `HEAD` to distinguish regressions from
  baseline.
- Only ask Codex to fix failures if the current diff introduced or worsened
  them.
- If the failure exists on clean `HEAD` too, record it as baseline debt and
  continue only when the issue's relevant checks passed and the failure is
  clearly unrelated baseline debt. Record the baseline debt in memory; do not
  chase unrelated regressions.

## Phase 3: Review

Claude review is mandatory after a real diff and passing gate. The builder must
not review its own work.

```text
You are the Claude reviewer for <issue-id>: <issue-title>.

Review only. Do not edit, commit, or push.
Finish the full review in one run. Do not pause to ask whether to continue.

Think like a staff engineer and a product manager. Review both the quality of
the implementation and whether it actually delivers working functionality.

Review the diff against the issue description and acceptance criteria.
Focus on:
- **Integration**: Is the new code wired into the rest of the system? Are
  callers updated, routes registered, exports added, config connected? Code
  that implements a feature in isolation but is never called is incomplete.
- **Correctness**: Logic errors, off-by-one, null handling, concurrency.
- **Regressions**: Does the change break existing behavior?
- **Edge cases**: Boundary conditions, error paths, empty/missing input.
- **Test quality**: Do tests exercise the actual behavior, not just prove
  the code compiles? Are integration touchpoints covered?
- **Completeness**: Would a user or caller of this feature get working
  functionality without manual follow-up work?

Classify findings:
- P0: must fix before shipping
- P1: should fix now
- P2: follow-up

OUTCOME: pass | revise | blocked

FINDINGS:
- <severity> <file>: <issue and why>

SUMMARY:
<one-line verdict>
```

If Claude returns incomplete or asks to continue, resume once via
`claude -p --continue`. If still incomplete, treat as blocked.

## Phase 4: Fix

If review returns `revise`:

1. Evaluate the findings first. Determine which P0s and P1s actually need
   fixing, which are out of scope, and which should become follow-up issues.
2. Send the actionable findings to the **same Codex session** via
   `codex exec resume --last` with the current diff context and the builder
   output contract.
3. After fixes, re-run the gate (Phase 2).
4. Re-run Claude review (Phase 3) as a fresh `claude -p` session — the
   reviewer should not remember prior rounds.
5. Max 5 fix/review rounds. If the loop does not converge, write blocker latch
   and stop.

## Phase 5: Ship

Codex handles shipping — the orchestrator does not commit or push.

When Claude review returns `OUTCOME: pass`, resume the same Codex session
with `codex exec resume --last`:

```text
Review passed. Commit the current changes on the default branch and push.

Commit format: <type>(<issue-id>): <short summary>
Use the repo's convention from AGENTS.md or CLAUDE.md if it specifies one.

If hooks fail, fix the issue, rerun checks, and retry.

After pushing, report:
COMMIT: <sha>
PUSH: <success or failure>
```

After Codex confirms a successful push, the orchestrator:

1. Update Linear issue to Done with summary, changed files, and commit SHA.
2. Create follow-up issues for deferred P1/P2 findings.
3. Log a running scorecard to night memory:
   ```
   Progress: <completed>/<total> done
   completed <issue-id>: <title>
   ...
   next <issue-id>: <title>
   ```
4. Pick the next issue in the same project. Go to Phase 1.

## Phase 6: Final Sweep

Runs only when **all** actionable issues for the project were successfully
shipped. Skip entirely if any issues remain blocked or failed.

For batches of 3+ issues, spawn a Claude review of the full diff range first:

1. Determine diff range: `git diff <hash-before-first-issue>..HEAD`
2. Claude checks: architecture consistency, test suite as a whole, regressions
   between issue boundaries.
3. Send all findings to the same Codex session for fixes. Only create follow-up
   Linear issues (tagged to the originals) for findings Codex cannot resolve.

Then resume the same Codex session with `codex exec resume --last`:

```text
All issues for this project are shipped.

1. If 3+ issues were shipped, fix any cross-issue findings from the review
   above. Commit and push fixes.

2. Check if README.md needs updating. Read the existing README. If shipped
   changes introduced new features, dependencies, setup steps, or config not
   reflected in the README, update only the affected sections. Do not rewrite
   from scratch. If nothing meaningful changed, skip.

3. Commit and push any README changes.

If nothing to do, reply: NO_SWEEP_CHANGES.
```

## Session Cleanup

CLI invocations exit on their own — there are no long-lived sessions to
terminate. After the project is fully done (issues + sweep + README):

1. Stop using `codex exec resume --last` for this project. The next project
   starts with a fresh `codex exec` call, which establishes its own session.
2. Return to the caller with status `clear` or `blocked`.

---

## Blocker Handling

If a hard blocker cannot be resolved in-flow:

1. Write latch:
   ```json
   {
     "issue": "<issue-id>",
     "project": "<project>",
     "timestamp": "<ISO-8601>",
     "blocker": "<exact root cause>",
     "evidence": ["<short evidence>"]
   }
   ```
2. Append to night memory.
3. Reply: `<issue> blocked: <exact root cause>. Need human help.`
4. Stop the queue. Do not continue to other issues.

## Memory

Append to night memory after each issue attempt:

- issue id, title, project
- status: completed / blocked / failed
- first Codex run: real work or no-op
- changed files
- gate results
- review outcome
- commit SHA if shipped
- blocker and evidence if blocked

## Invariants

- Code on main always passes the full gate.
- Ship on the default branch only. No per-issue branches.
- Builder and reviewer are always separate sessions.
- Orchestrator never edits source code or runs git commit/push.
- Tests before implementation (TDD).
- One corrective retry on no-op, then hard block.
- Reuse Codex session within a project for codebase continuity.
