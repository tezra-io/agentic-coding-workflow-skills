# dev-build

Implementation workflow for coding tasks: **Context → Build → Smoke Test → Review → Fix → Ship → Next Issue**.

## Best for
- Feature implementation
- Bug fixes
- Refactors
- Multi-issue delivery loops using Linear priorities

## Core guarantees
- Build/test/lint gate before shipping
- Mandatory per-issue review + final batch review
- Explicit Linear state updates
- Human steering retained at loop boundaries

See `SKILL.md` for full phase-by-phase execution.
