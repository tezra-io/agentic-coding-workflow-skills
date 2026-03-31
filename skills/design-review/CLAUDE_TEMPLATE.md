# CLAUDE.md Template
# Copy into new projects. Fill in {placeholders}. Remove comments.

# {Project Name}

## Project
<!-- One-liner: what it is, stack, key deps -->

## How to Work

### Planning
- Plan mode for any non-trivial task (3+ steps or architectural decisions)
- Detailed specs upfront — good plan = 1-shot implementation
- If something goes sideways, STOP and re-plan

### Test-First (Mandatory)
1. Write failing tests that define correct behavior
2. Make them pass
3. Refactor while green

"Write failing tests, then make them pass" — not "implement this feature."

### Verification
1. Write failing tests
2. Implement to pass them
3. Typecheck: `{typecheck_command}`
4. Full test suite: `{test_command}`
5. Lint: `{lint_command}`

Never mark done without proving it works.

## Code Rules (Non-Negotiable)

1. **Linear flow.** Max 2 nesting levels. Top to bottom.
2. **Bound loops.** Explicit max on retries, polls, recursion. Define cap behavior.
3. **Small functions.** 40-60 lines max. One job per function.
4. **Own resources.** Open → close on every path, including errors.
5. **Narrow state.** No module globals. Pass deps explicitly.
6. **Assert assumptions.** Guards and validation on every public function. Fail loud.
7. **Never swallow errors.** No bare `rescue`. No `{:error, _} -> :ok`. Log, raise, or return.
8. **Visible side effects.** I/O obvious at call site. Separate pure from effectful.
9. **Minimal indirection.** Readable > elegant. One layer of abstraction max.
10. **Warnings = errors.** Linters, typecheckers, analyzers are hard gates. Zero warnings.

## Conventions
<!-- Project-specific: language idioms, error handling patterns, naming -->

## Commands
```sh
{build_command}
{test_command}
{lint_command}
{format_command}
```

## Docs
- `docs/spec.md` — Product spec: features, business rules
- `docs/tech.md` — Architecture: stack, schema, decisions
- `docs/lessons.md` — Rules from past mistakes (update immediately on correction)

## Don'ts
<!-- Most valuable section — add aggressively over time -->
- Don't commit without running tests
- Don't implement without failing tests first
- Don't add abstractions you weren't asked for
- Don't assume intent on ambiguous bugs — ask

## Principles
- Simplest correct solution
- Find root causes, no band-aids
- Minimal blast radius
- Own mistakes — write a rule to prevent repeating

## Known Pitfalls
<!-- Grows over time -->

---
_Every mistake is a rule waiting to be written._
