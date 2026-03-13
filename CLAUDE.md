# Agentic Coding Workflow Skills

## Project
This repo contains reusable agent skills for coding workflows (design review, dev build, code review).

## Task
You have access to the Anthropic skill-creator at `skills/anthropic-skill-creator/SKILL.md`. 
Use it to evaluate and improve the `code-review-expert` skill at `skills/code-review-expert/SKILL.md`.

Follow the skill-creator's process for evaluating an EXISTING skill:
1. Read the code-review-expert skill
2. Create 3 realistic test prompts and run them yourself (follow the skill instructions for each prompt)
3. Grade the results with assertions
4. Generate the eval viewer with `--static` flag
5. Based on findings, optimize the skill
6. Re-run evals on the optimized version

Since you're in Claude Code (not Claude.ai), follow the main workflow section, but since you don't have subagents, follow the Claude.ai adaptation: run test cases sequentially yourself.

Put all eval workspace files in `skills/code-review-expert-workspace/`.

## Commands
- Python: `python3`
- Eval viewer: `cd skills/anthropic-skill-creator && python3 -m eval-viewer.generate_review <workspace-path> --skill-name code-review-expert --static /tmp/code-review-expert-eval.html`
