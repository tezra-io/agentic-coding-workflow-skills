---
name: design
description: Architecture and design for new projects, major features, or significant changes. Use at project kickoff when the task involves new modules, multi-file changes, or architectural decisions. Produces an approved design doc, a CLAUDE.md, and creates Linear issues for implementation. Also use when someone asks to "design", "architect", or "plan" a feature, when writing a design doc, or when a task touches 4+ files or introduces a new subsystem. Applies to new features, feature upgrades, design changes, and architectural changes. Not needed for small bug fixes, single-file changes, or well-understood patterns under 3 files.
---

# Design

Run once at project start. Produces a design doc, project CLAUDE.md, gets reviewed and approved, then breaks into Linear issues.

## Phase 0: Scope Check

Before running the full process, assess whether this task actually needs a design review.

**Full design review** when:
- New subsystem or module (4+ files)
- Multiple components need to interact in new ways
- Performance or latency requirements that constrain the design
- Security-sensitive feature (auth, crypto, data handling)
- The human explicitly asks for one

**Skip or go lightweight** when:
- Well-understood pattern (rate limiting, pagination, CRUD endpoint) under 3 files
- Single-file refactor
- Bug fix with clear root cause

If the task is borderline, tell the human: "This looks small enough to skip a full design review. Want me to do a quick approach check instead, or go straight to implementation?" A quick approach check = Phase 0.5 only (propose approaches, pick one, done — no design doc, no review loop).

## Phase 0.1: Setup

1. Read the issue from **Linear** for the target project — description, goals, acceptance criteria, linked references
2. For new projects: create directory structure and initialize git repo
   ```
   ~/projects/<project-name>/
   └── docs/
   ```
3. For existing projects: verify `docs/` exists, check for prior design docs and CLAUDE.md

## Phase 0.2: ACP Tooling (optional)

After the tech stack is identified, install project-scoped language tooling only if the active ACP builder supports it.

- Keep it project-local
- Install only the primary language tool
- Skip this step if the builder has no equivalent support

Good design work matters more than editor extras.

## Phase 0.5: Approaches (before drafting)

Before committing to a design, propose **2-3 architectural approaches** with trade-offs. For each:
- Brief description of the approach
- Key trade-offs (complexity, performance, maintainability, risk)
- Your recommendation and why

Present these to the human. Only proceed to Phase 1 after an approach is chosen. This catches bad architectural decisions before anyone spends time writing a full design doc.

## Phase 1: Draft

**IMPORTANT: Always delegate this to Codex.** The orchestrator should not draft the design doc itself. Your job is to steer, not write.

Spawn a **Codex ACP** session (`sessions_spawn` with `runtime: "acp"` and `agentId: "codex"`, or the coding-agent skill if it preserves the same Codex ACP target) with these instructions in the task:
- Read CLAUDE.md if it exists in the project repo
- The Linear issue description and acceptance criteria (paste the full text)
- The chosen approach from Phase 0.5 (paste your recommendation and the human's choice)
- Any linked design docs or prior art
- Draft the design doc at `docs/<issue-id>-design.md`
- Create or update `CLAUDE.md` at project root using the template at `skills/design-review/CLAUDE_TEMPLATE.md`
- Merge the template with any existing project-specific guidance, do not bluntly overwrite useful repo-specific instructions
- Preserve these behavioral guardrails from the template:
  - state assumptions explicitly and surface ambiguity instead of guessing
  - ask when the request is unclear, and push back if a simpler approach is better
  - use short `step -> verify` plans for multi-step work
  - keep test-first and explicit verification gates intact
  - keep changes surgical, with minimal blast radius and no adjacent-drive-by cleanup
  - prefer the simplest correct solution and avoid speculative abstractions

**Fail closed:** If the ACP spawn fails or Codex cannot start, stop and report the exact error. Do **not** draft the design locally or substitute a different code-writing agent unless the human explicitly approves.

If `CLAUDE_TEMPLATE.md` doesn't exist, create a basic CLAUDE.md with: project overview, tech stack, build/test/lint commands, directory structure, coding conventions, explicit ambiguity-handling rules, surgical-change rules, and test-first verification rules.

### Design Doc Sections

The design doc should cover these sections. Not every section needs to be long, scale depth to complexity. A simple webhook system needs 1-2 sentences per section; a real-time voice pipeline needs paragraphs.

- **Problem**: what and why, not how
- **Tech stack**: language, runtime version, key dependencies, and why they were chosen
- **Approach**: chosen solution with key trade-offs documented
- **Scope**: what's in, what's explicitly out
- **Data flow**: how components interact (diagram if complex)
- **User scenarios**: concrete walkthrough of how a user or agent interacts with this feature end-to-end
- **Agent scenarios**: how the agent discovers, triggers, and uses this feature autonomously
- **Edge cases & failure modes**: what happens when things go wrong. Start with the generic list (bad input, partial failure, resource exhaustion, race conditions), then add domain-specific failures:
  - *Real-time/streaming*: buffer management, jitter, latency budget breakdown per stage, graceful degradation under load
  - *Security/crypto*: key rotation, revocation, timing attacks
  - *Voice/audio*: hot mic, silence detection, audio corruption, concurrent sessions
  - *Networking*: thundering herd, connection pooling, retry storms
  - *Data pipeline*: schema drift, backpressure, exactly-once vs at-least-once
- **Error UX**: what the user or agent sees when something fails
- **Security & privacy**: trust model, what's allowed, what's blocked, how it's enforced
- **Performance requirements**: explicit targets if latency, throughput, or resource constraints matter
- **Open questions**: unresolved decisions flagged for human input

**IMPORTANT: Focus on DESIGN, not code.** Keep code snippets minimal, only where they clarify an interface contract or data format. The doc should read as architecture and scenario coverage, not implementation pseudocode.

Target length: 2-5 pages for most features. If it's getting longer, you're probably including too much implementation detail.

Keep both docs concise, docs that nobody reads are worse than no docs.

## Phase 2: Review Loop

Spawn a **Claude Code reviewer** session via ACP (`sessions_spawn` with `runtime: "acp"` and `agentId: "claude"`) with this task:

> Review the design doc at `docs/<issue-id>-design.md` in the project at `<repo-path>`. Evaluate on these axes and categorize each finding as Blocker, Recommendation, or Note. Write your review to `docs/<issue-id>-review.md`. Do not edit the design doc.

Review axes:

| Axis | Key Questions |
|------|--------------|
| Requirements | Does it satisfy acceptance criteria? Missing anything? |
| Architecture | Clean boundaries? Appropriate abstractions? Over-engineered? |
| Tech stack | Right tool for the job? Dependencies justified? |
| Trade-offs | Are alternatives considered? Is the rationale clear? |
| Performance | Can the design meet stated latency or throughput targets? |
| Risk | What breaks first? What's hardest to change later? |
| Testability | Can the design be validated with automated tests? |

Categorize findings:
- **Blocker** — must resolve before build starts
- **Recommendation** — should address, human decides
- **Note** — context for the builder, no action needed

**Review loop:** If blockers are found, send them back to a fresh Codex ACP session (`runtime: "acp"`, `agentId: "codex"`) to revise the design doc, then re-dispatch Claude review. Repeat until all blockers are resolved. **Max 5 iterations** — if still unresolved after 5 rounds, escalate to the human with all findings and the full review history.

If Claude review cannot run, stop and report the exact error. Do not silently skip review.

## Phase 3: Human Review

Present to the human:
1. A **summary** of the design (3-5 bullet points covering approach, key trade-offs, and scope)
2. The **review findings** (blockers resolved, open recommendations)
3. The **file paths** to the full design doc and CLAUDE.md for deep reading

Iterate until:
- All blockers are resolved
- Tech stack is confirmed
- CLAUDE.md accurately reflects project setup
- CLAUDE.md still preserves the core guardrails from the template instead of drifting into vague project-only prose
- Human explicitly approves

Update both docs with any changes from this phase.

## Phase 4: Task Breakdown

Once approved, break the design into implementation tasks:

1. Decompose into discrete, shippable units of work. Each issue should be completable in roughly 1-3 hours of agent time. If an issue feels bigger, split it. **Every implementation task must start with writing failing tests** — include this in the acceptance criteria.
2. Order by dependency — set **Linear priority** so the build skill processes them in the correct sequence:
   - **P1 (Urgent):** Foundational work that everything else depends on (core structs, traits, base modules)
   - **P2 (High):** Features and changes that build on P1 foundations
   - **P3-P4 are reserved for upstream port issues** — never use them for manual/feature work
3. Each task: title, description with acceptance criteria, and estimated scope (S/M/L)
4. Create issues in **Linear** — **always pass `--project "<project-name>"`** so they're tagged to the correct project. Look up the project name from `linear project list --team <team>` or ask the human. Issues without a project tag won't be picked up by build crons.
5. Link the design doc in each issue description (relative path from repo root, e.g., `docs/TEZ-200-design.md`)
6. If the feature has performance requirements, include a dedicated benchmarking issue (e.g., "Add benchmarks to validate sub-200ms latency target")

## Output

- Approved design doc at `docs/<issue-id>-design.md`
- `CLAUDE.md` at project root with build/test/lint commands, project conventions, and the preserved behavioral guardrails from the template
- Linear issues created with priorities set, linked to the design
