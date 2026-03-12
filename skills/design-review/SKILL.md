---
name: design-review
description: Architecture and design review for new projects or major features. Use at project kickoff when the task involves new modules, multi-file changes, or architectural decisions. Produces an approved design doc, a CLAUDE.md, and creates Linear issues for implementation. Not needed for small bug fixes or single-file changes.
---

# Design Review

Run once at project start. Produces a design doc, project CLAUDE.md, gets reviewed and approved, then breaks into Linear issues.

## Phase 0: Setup

1. Read the issue from **Linear** for the target project — description, goals, acceptance criteria, linked references
2. For new projects: create directory structure and initialize git repo
   ```
   /home/sujshe/projects/<project-name>/
   └── docs/
   ```
3. For existing projects: verify `docs/` exists, check for prior design docs and CLAUDE.md

## Phase 1: Draft

**IMPORTANT: Always delegate this to Claude Code.** The orchestrator (you) should NOT draft the design doc itself — that fills your context with code and architecture details you don't need to hold. Your job is to steer, not write.

Spin up a **Claude Code** session with these instructions:
- Read CLAUDE.md if it exists
- Pass in the Linear issue description and any linked design docs
- Draft the design doc at `docs/<issue-id>-design.md`

Design doc covers:
- **Problem**: what and why, not how
- **Tech stack**: language, runtime version, key dependencies, and why they were chosen
- **Approach**: chosen solution with key trade-offs documented
- **Scope**: what's in, what's explicitly out
- **Data flow**: how components interact (diagram if complex)
- **User scenarios**: concrete walkthrough of how a user/agent interacts with this feature end-to-end
- **Agent scenarios**: how the agent discovers, triggers, and uses this feature autonomously
- **Edge cases & failure modes**: what happens when things go wrong — bad input, partial failure, resource exhaustion, race conditions, false positives, graceful degradation
- **Error UX**: what the user/agent sees when something fails — not just "returns error" but the actual message and recovery path
- **Security boundaries**: trust model, what's allowed, what's blocked, how it's enforced
- **Open questions**: unresolved decisions flagged for human input

**IMPORTANT: Focus on DESIGN, not code.** Keep code snippets minimal — only where they clarify an interface contract or data format. The doc should read as architecture and scenario coverage, not implementation pseudocode. A reader should understand every scenario, edge case, and UX decision without reading a single line of code.

In the same session, create or update `CLAUDE.md` at project root using the standard template at `skills/design-review/CLAUDE_TEMPLATE.md` as a base. Fill in the project-specific sections (build/test/lint commands, tech stack, conventions, structure) and keep the workflow orchestration and core principles sections intact.

Keep both docs concise — docs that nobody reads are worse than no docs.

## Phase 2: Review

Spin up **Claude agent team** (Sonnet models) to review the draft. Evaluate on:

| Axis | Key Questions |
|------|--------------|
| Requirements | Does it satisfy acceptance criteria? Missing anything? |
| Architecture | Clean boundaries? Appropriate abstractions? Over-engineered? |
| Tech stack | Right tool for the job? Dependencies justified? |
| Trade-offs | Are alternatives considered? Is the rationale clear? |
| Risk | What breaks first? What's hardest to change later? |
| Testability | Can the design be validated with automated tests? |

Categorize findings:
- **Blocker** — must resolve before build starts
- **Recommendation** — should address, human decides
- **Note** — context for the builder, no action needed

## Phase 3: Human Review

Present the design doc, CLAUDE.md, and review findings to the human. Iterate until:
- All blockers are resolved
- Tech stack is confirmed
- CLAUDE.md accurately reflects project setup
- Human explicitly approves

Update both docs with any changes from this phase.

## Phase 4: Task Breakdown

Once approved, break the design into implementation tasks:

1. Decompose into discrete, shippable units of work
2. Order by dependency — set **Linear priority** so the build skill processes them in the correct sequence:
   - **P1 (Urgent):** Foundational work that everything else depends on (core structs, traits, base modules)
   - **P2 (High):** Features and changes that build on P1 foundations
   - **P3-P4 are reserved for upstream port issues** — never use them for manual/feature work
3. Each task: title, description, acceptance criteria, estimated scope
4. Create issues in **Linear** under the target project
5. Link the design doc in each issue

## Output

- Approved design doc at `docs/<issue-id>-design.md`
- `CLAUDE.md` at project root with build/test/lint commands and conventions
- Linear issues created with priorities set, linked to the design
