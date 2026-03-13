---
name: design-review
description: Architecture and design review for new projects or major features. Use at project kickoff when the task involves new modules, multi-file changes, or architectural decisions. Produces an approved design doc, a CLAUDE.md, and creates Linear issues for implementation. Also use when someone asks to "design", "architect", or "plan" a feature, or when a task touches 4+ files or introduces a new subsystem. Not needed for small bug fixes, single-file changes, or well-understood patterns under 3 files.
---

# Design Review

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

## Phase 0.5: Approaches (before drafting)

Before committing to a design, propose **2-3 architectural approaches** with trade-offs. For each:
- Brief description of the approach
- Key trade-offs (complexity, performance, maintainability, risk)
- Your recommendation and why

Present these to the human. Only proceed to Phase 1 after an approach is chosen. This catches bad architectural decisions before anyone spends time writing a full design doc.

## Phase 1: Draft

**IMPORTANT: Always delegate this to Claude Code.** The orchestrator (you) should NOT draft the design doc itself — that fills your context with code and architecture details you don't need to hold. Your job is to steer, not write.

Spawn a **Claude Code** session (via `sessions_spawn` with `runtime: "acp"` or the coding-agent skill) with these instructions in the task:
- Read CLAUDE.md if it exists in the project repo
- The Linear issue description and acceptance criteria (paste the full text)
- The chosen approach from Phase 0.5 (paste your recommendation and the human's choice)
- Any linked design docs or prior art
- Draft the design doc at `docs/<issue-id>-design.md`
- Create or update `CLAUDE.md` at project root using the template at `skills/design-review/CLAUDE_TEMPLATE.md`

If `CLAUDE_TEMPLATE.md` doesn't exist, create a basic CLAUDE.md with: project overview, tech stack, build/test/lint commands, directory structure, and coding conventions.

### Design Doc Sections

The design doc should cover these sections. Not every section needs to be long — scale depth to complexity. A simple webhook system needs 1-2 sentences per section; a real-time voice pipeline needs paragraphs.

- **Problem**: what and why, not how
- **Tech stack**: language, runtime version, key dependencies, and why they were chosen
- **Approach**: chosen solution with key trade-offs documented
- **Scope**: what's in, what's explicitly out
- **Data flow**: how components interact (diagram if complex)
- **User scenarios**: concrete walkthrough of how a user/agent interacts with this feature end-to-end
- **Agent scenarios**: how the agent discovers, triggers, and uses this feature autonomously
- **Edge cases & failure modes**: what happens when things go wrong. Start with the generic list (bad input, partial failure, resource exhaustion, race conditions), then add domain-specific failures:
  - *Real-time/streaming*: buffer management, jitter, latency budget breakdown per stage, graceful degradation under load
  - *Security/crypto*: key rotation, revocation, timing attacks
  - *Voice/audio*: hot mic, silence detection, audio corruption, concurrent sessions
  - *Networking*: thundering herd, connection pooling, retry storms
  - *Data pipeline*: schema drift, backpressure, exactly-once vs at-least-once
- **Error UX**: what the user/agent sees when something fails — not just "returns error" but the actual message, recovery path, and fallback behavior
- **Security & privacy**: trust model, what's allowed, what's blocked, how it's enforced. For sensitive data types (audio, PII, credentials, location), explicitly address: storage, transmission, retention, consent, and local-only processing requirements
- **Performance requirements**: if the feature has latency, throughput, or resource constraints, state them explicitly with targets (e.g., "P50 < 10ms, P99 < 100ms"). Include a latency budget breakdown if multiple stages are involved
- **Open questions**: unresolved decisions flagged for human input

**IMPORTANT: Focus on DESIGN, not code.** Keep code snippets minimal — only where they clarify an interface contract or data format. The doc should read as architecture and scenario coverage, not implementation pseudocode. A reader should understand every scenario, edge case, and UX decision without reading a single line of code.

Target length: 2-5 pages for most features. If it's getting longer, you're probably including too much implementation detail.

Keep both docs concise — docs that nobody reads are worse than no docs.

## Phase 2: Review Loop

Spawn a **reviewer session** (Sonnet model via `sessions_spawn` with `model: "sonnet"`) with this task:

> Review the design doc at `docs/<issue-id>-design.md` in the project at `<repo-path>`. Evaluate on these axes and categorize each finding as Blocker, Recommendation, or Note. Write your review to `docs/<issue-id>-review.md`.

Review axes:

| Axis | Key Questions |
|------|--------------|
| Requirements | Does it satisfy acceptance criteria? Missing anything? |
| Architecture | Clean boundaries? Appropriate abstractions? Over-engineered? |
| Tech stack | Right tool for the job? Dependencies justified? |
| Trade-offs | Are alternatives considered? Is the rationale clear? |
| Performance | Can the design meet stated latency/throughput targets? Is there a credible latency budget? |
| Risk | What breaks first? What's hardest to change later? |
| Testability | Can the design be validated with automated tests? |

Categorize findings:
- **Blocker** — must resolve before build starts
- **Recommendation** — should address, human decides
- **Note** — context for the builder, no action needed

**Review loop:** If blockers are found, send them back to a Claude Code session to fix in the design doc, then re-dispatch the reviewer. Repeat until all blockers are resolved. **Max 5 iterations** — if still unresolved after 5 rounds, escalate to the human with all findings and the full review history.

## Phase 3: Human Review

Present to the human:
1. A **summary** of the design (3-5 bullet points covering approach, key trade-offs, and scope)
2. The **review findings** (blockers resolved, open recommendations)
3. The **file paths** to the full design doc and CLAUDE.md for deep reading

Iterate until:
- All blockers are resolved
- Tech stack is confirmed
- CLAUDE.md accurately reflects project setup
- Human explicitly approves

Update both docs with any changes from this phase.

## Phase 4: Task Breakdown

Once approved, break the design into implementation tasks:

1. Decompose into discrete, shippable units of work. Each issue should be completable in roughly 1-3 hours of agent time. If an issue feels bigger, split it.
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
- `CLAUDE.md` at project root with build/test/lint commands and conventions
- Linear issues created with priorities set, linked to the design
