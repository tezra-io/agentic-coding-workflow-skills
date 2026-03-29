---
description: "Run an expert review using the local OpenAI Codex CLI. Use when the user asks for a code review, design doc review, architecture review, PR review, file review, or says 'codex review'. Supports branch diffs, PRs, single files, staged changes, unstaged changes, and all uncommitted changes."
allowed-tools: ["Bash", "Read", "Glob", "Grep"]
---

# Codex Review

Use the local `codex` CLI to perform the review. Your job is to determine the scope, verify there is something reviewable, run the correct command, and return Codex's review with minimal framing.

Do not perform a second manual review on top of Codex unless the user explicitly asks for your own opinion as well.

## Review Standard

For any custom prompt you pass to Codex, enforce this review style:

- Findings first, ordered by severity.
- Prioritize correctness, regressions, security issues, edge cases, missing validation, missing tests, and design risk over style commentary.
- Cite exact file paths and lines for code, or exact headings and sections for documents.
- Keep summaries brief.
- If there are no findings, say that explicitly and mention residual risks or testing gaps.

## Argument Parsing

The user invokes this as `/codex-review [ARGS]`. Parse `$ARGUMENTS` into one of these modes:

| User Input | Mode | Command |
|---|---|---|
| *(empty / no args)* | Branch diff vs base | `codex review --base <base-branch>` |
| `#123` or `123` | PR review | `gh pr diff 123 \| codex review --title "PR #123" -` |
| `--staged` | Staged changes only | `git diff --cached \| codex review --title "Staged changes" -` |
| `--unstaged` | Unstaged changes only | `git diff \| codex review --title "Unstaged changes" -` |
| `--uncommitted` | All local changes | `codex review --uncommitted` |
| Existing file path | Single file review | `codex exec --sandbox read-only "<expert review prompt that references the path>"` |

If a file path is followed by extra text, treat the remaining text as additional review focus and append it to the prompt.

## Execution Rules

- Always shell-quote interpolated values such as file paths and titles.
- Never inline file contents with command substitution such as `$(cat file)` inside the prompt.
- Prefer pointing Codex at files that already exist in the workspace.
- For review-only single-file analysis with `codex exec`, prefer `--sandbox read-only` unless the user explicitly wants edits.
- If the argument is ambiguous, check whether it resolves to a real file before assuming it is free text.

## Step-by-Step Execution

### 1. Detect the base branch

Prefer a local symbolic ref instead of `git remote show origin`:

```bash
git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@'
```

If that returns nothing, fall back to `main`.

### 2. Validate the input

- PR mode: strip a leading `#` and require digits only.
- File mode: verify the file exists with `test -f`.
- Flag mode: support only `--staged`, `--unstaged`, and `--uncommitted`.
- Empty input: use branch diff mode.
- Anything else: if it is not a real file and does not match a supported mode, stop and say the argument was not understood.

### 3. Check for reviewable content

Before calling Codex, verify there is actually something to review:

- Branch diff mode: run `git diff <base>...HEAD --stat`.
- Staged mode: run `git diff --cached --stat`.
- Unstaged mode: run `git diff --stat`.
- PR mode: run `gh pr diff <number> --stat`.

If the selected scope is empty, stop and tell the user there is nothing to review for that scope.

### 4. Choose file review type

For single-file reviews, classify the file before building the prompt.

Treat these as documents by default:

- `.md`
- `.txt`
- `.rst`
- `.adoc`
- filenames containing `design`, `rfc`, `spec`, `proposal`, or `architecture`

Treat normal source extensions such as `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.kt`, `.rb`, `.c`, `.cc`, `.cpp`, `.h`, and `.hpp` as code.

If the extension is ambiguous, inspect the file briefly and choose the better mode.

### 5. Run the review

Use the built-in `codex review` flow whenever the review target is a diff. Use `codex exec --sandbox read-only` for single-file document or code review where you need a custom prompt.

#### Branch diff mode

```bash
codex review --base <base-branch>
```

#### PR mode

```bash
gh pr diff <number> | codex review --title "PR #<number>" -
```

#### Staged mode

```bash
git diff --cached | codex review --title "Staged changes" -
```

#### Unstaged mode

```bash
git diff | codex review --title "Unstaged changes" -
```

#### Uncommitted mode

```bash
codex review --uncommitted
```

#### Single document mode

Run `codex exec --sandbox read-only`. `codex exec` already runs non-interactively by default, and the explicit sandbox keeps review-only analysis read-only.

Suggested prompt:

```text
Review the document at <path> as an expert technical reviewer.

Output findings first, ordered by severity.
Prioritize architecture quality, feasibility, correctness of assumptions, missing edge cases, operational risk, security implications, migration or rollback gaps, and whether the document is implementable from the current level of detail.
Cite exact sections or headings.
If there are no findings, say that explicitly and mention residual risks or unanswered questions.

Additional focus: <extra focus if any>
```

#### Single code file mode

Run `codex exec --sandbox read-only`. `codex exec` already runs non-interactively by default, and the explicit sandbox keeps review-only analysis read-only.

Suggested prompt:

```text
Review the code at <path> as an expert code reviewer.

Output findings first, ordered by severity.
Prioritize bugs, behavioral regressions, security issues, performance traps, edge cases, missing validation, contract mismatches, and missing tests over style comments.
Cite exact file lines.
If there are no findings, say that explicitly and mention residual risks or testing gaps.

Additional focus: <extra focus if any>
```

### 6. Present the results

- Return Codex's review directly, with at most one short lead-in identifying what was reviewed.
- Do not add your own second-pass review unless the user asks for it.
- If Codex returns an error, show the error and give the most likely fix:
  - `codex login`
  - missing API credentials
  - `gh auth status` for PR mode
  - no diff in the selected scope
