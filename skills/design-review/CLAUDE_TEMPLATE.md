# CLAUDE.md Template
# Based on Boris Cherny's CLAUDE.md conventions.
# Copy into new projects and fill in project-specific sections.
# Remove comments and unused sections.

# {Project Name}

This file is Claude's project memory. Update it whenever Claude makes a mistake so it doesn't repeat it.

## Project Overview
<!-- Tech stack, purpose, key dependencies -->

## How to Work

### Planning
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- Write detailed specs upfront to reduce ambiguity — a good plan means a 1-shot implementation
- If something goes sideways, STOP and re-plan. Don't keep pushing.
- Use plan mode for verification steps, not just building

### Verification
Every change follows this loop before it's considered done:
1. Make changes
2. Run typecheck: `{typecheck_command}`
3. Run tests: `{test_command}`
4. Lint: `{lint_command}`
5. Before PR: run full suite, diff behavior against main when relevant

Never mark a task complete without proving it works. Ask yourself: "Would a staff engineer approve this?"

### Parallel Work
- Use subagents to keep the main context window clean and focused
- One task per subagent — offload research, exploration, and analysis
- Only one agent should edit a given file at a time
- For fully parallel workstreams: `git worktree add .claude/worktrees/<n> origin/main`

### Bug Fixing
- Clear reproduction? Investigate and fix directly — check logs, errors, failing tests
- Fix failing CI without being told how
- Ambiguous bug? Clarify scope before proceeding

## Project Documentation (`docs/`)
Living knowledge base. Consult at session start alongside this CLAUDE.md.

- **`docs/spec.md`** — Product specification: feature behaviors, business rules, constraints.
- **`docs/tech.md`** — Technical architecture: stack, schema, infrastructure, key decisions.
- **`docs/lessons.md`** — Rules derived from past mistakes. Review at session start.

### When to update docs
- **`docs/spec.md`**: When behavior changes — new features, modified flows, changed business rules.
- **`docs/tech.md`**: When architecture changes — new dependencies, schema migrations, infrastructure decisions.
- **`docs/lessons.md`**: Immediately after any correction.

## Task Management Workflow
1. **Plan First**: Write a plan with checkable items before starting.
2. **Verify Plan**: Check in before starting implementation.
3. **Track Progress**: Mark items complete as you go.
4. **Explain Changes**: High-level summary at each step.
5. **Update Docs**: Update spec.md and tech.md if behavior or architecture changed.
6. **Capture Lessons**: If corrected, update lessons.md immediately.

## Code Quality
<!-- Fill in project-specific commands -->
- Format code: `{format_command}`
- Lint code: `{lint_command}`
- Fix linting issues: `{lint_fix_command}`

## Key Files
- `CLAUDE.md` — This file, Claude Code memory
- `docs/spec.md` — Product specification
- `docs/tech.md` — Technical architecture
- `docs/lessons.md` — Lessons from past mistakes

## Code Style & Conventions
<!-- Project-specific conventions: naming, patterns, preferences -->

## Commands Reference
```sh
# Build & verify (customize for your project)
{build_command}
{test_command}
{lint_command}
{format_command}
```

## Known Pitfalls
<!-- Add as they're discovered — this section grows over time -->

## Things Claude Should NOT Do
<!-- Most valuable section over time — add to it aggressively -->
- Don't skip error handling
- Don't commit without running tests first
- Don't add abstractions or refactor code you weren't asked to touch
- Don't assume intent on ambiguous bugs — ask first

## Principles
- **Simplest correct solution.** Don't over-engineer. Don't gold-plate.
- **Find root causes.** No temporary fixes. No band-aids.
- **Minimal blast radius.** Only touch what's necessary.
- **Own your mistakes.** When corrected, write a rule to prevent repeating it.

## Project-Specific Patterns
<!-- Add patterns as they emerge from your codebase -->

---

_Every mistake is a rule waiting to be written._
