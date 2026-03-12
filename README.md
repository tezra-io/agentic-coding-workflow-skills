# Agentic Coding Workflow Skills

Public reference implementation of two workflow skills used in our founder-builder coding system.

## Included Skills

- `skills/design-review` — project kickoff architecture workflow
- `skills/dev-build` — implementation + review + ship workflow loop

## Why these exist

This workflow splits planning from execution, keeps human steering in the loop, and avoids context overload by delegating focused steps to specialized agents.

## Usage Notes

These are OpenClaw skill folders. To use them in your own setup:

1. Copy each skill folder into your skills directory.
2. Keep file names unchanged (`SKILL.md`, templates, references).
3. Trigger `design-review` at project kickoff.
4. Trigger `dev-build` for implementation loops.

## Suggested Flow

1. `design-review` to produce approved design doc + CLAUDE.md + Linear task breakdown
2. `dev-build` to execute issues in priority order with test/review/fix/ship loop

## License

MIT
