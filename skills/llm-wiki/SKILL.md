---
name: llm-wiki
description: >
  Build and maintain LLM-powered personal knowledge bases using Karpathy's Wiki pattern.
  Handles wiki initialization (directory structure, schema), source ingestion (articles,
  papers, notes into structured wiki pages), knowledge querying (synthesis with citations),
  and wiki health checks (lint for contradictions, orphans, gaps). Use this skill whenever
  the user mentions knowledge bases, research wikis, ingesting sources, research notes,
  adding articles or papers to a collection, synthesizing research, "add to wiki",
  "ingest this", wiki maintenance, or asks to organize/structure their knowledge on any
  topic. Also trigger when the user works in a directory containing a wiki/ and raw/
  folder structure, or references index.md/log.md in a knowledge base context.
---

# LLM Wiki

Build compounding personal knowledge bases based on Andrej Karpathy's LLM Wiki pattern.
Humans curate sources and ask good questions — the LLM handles all the bookkeeping that
causes people to abandon wikis.

## Three Layers

1. **Raw sources** (`raw/`) — immutable files the user collects. Never modify these.
2. **Wiki pages** (`wiki/`) — LLM-maintained markdown with frontmatter, cross-references, and citations.
3. **Schema** (`wiki-schema.md`) — per-wiki configuration defining structure, workflows, and conventions.

Every interaction adds structured knowledge. The wiki compounds over time.

## Storage Model

Wikis can live in two places depending on the agent environment:

| Agent type | Wiki location | When |
|------------|--------------|------|
| Has project context (Claude Code) | Inside the project directory | Default for project-scoped work |
| No project context (OpenClaw, etc.) | `~/wikis/{wiki-name}/` | Default for standalone wikis |

All wikis register in a **global registry** at `~/wikis/registry.json`, so any agent can
discover and operate on any wiki regardless of where the data lives.

### Registry format

```json
{
  "wikis": [
    {
      "name": "ml-research",
      "path": "/Users/username/projects/ml-research",
      "domain": "Machine learning papers and research",
      "created": "2026-04-05",
      "local": true
    },
    {
      "name": "book-notes",
      "path": "/Users/username/wikis/book-notes",
      "domain": "Non-fiction book summaries",
      "created": "2026-04-05",
      "local": false
    }
  ]
}
```

- `local: true` — wiki lives inside a project directory
- `local: false` — wiki lives under `~/wikis/`

## Detect the Operation

Read the user's request and the current directory to determine which operation to run:

| Signal | Operation |
|--------|-----------|
| No `wiki/` directory exists, or user says "set up a wiki", "create a knowledge base", "initialize" | **Init** |
| User says "ingest", "add this", "process this source", or references a file in `raw/` | **Ingest** |
| User asks a question about the wiki's domain, says "what do we know about", "synthesize", "summarize across" | **Query** |
| User says "lint", "check health", "find contradictions", "orphan pages", "what's missing" | **Lint** |

### Finding the right wiki

1. If you're in a project directory that has `wiki/` and `raw/`, use that wiki.
2. If the user names a wiki ("ingest into ml-research"), look it up in `~/wikis/registry.json`.
3. If ambiguous and multiple wikis exist, list them and ask which one.
4. If no wikis exist, start Init.

---

## Init — Set Up a New Wiki

### Step 1: Ask the user

- What topic or domain is this wiki for?
- Any custom sub-categories beyond the defaults?
- Project-local or standalone? (Default: project-local if in a project directory, standalone otherwise)

### Step 2: Create directory structure

```
{wiki-root}/
├── raw/
│   ├── articles/
│   ├── papers/
│   ├── repos/
│   ├── data/
│   ├── images/
│   └── assets/
├── wiki/
│   ├── index.md
│   ├── log.md
│   ├── overview.md
│   ├── concepts/
│   ├── entities/
│   ├── sources/
│   └── comparisons/
└── wiki-schema.md
```

Create each directory with `mkdir -p`. Add any user-specified custom sub-categories.

### Step 3: Seed the special files

**wiki/index.md** — the navigation hub:

```markdown
# {Domain} Wiki Index

> Last updated: {today's date}

## Sources
_No sources ingested yet._

## Concepts
_No concept pages yet._

## Entities
_No entity pages yet._

## Comparisons
_No comparison pages yet._
```

**wiki/log.md** — activity timeline:

```markdown
# Wiki Activity Log

## [{today's date}] init | Wiki created for {domain}
- Directory structure created
- Schema configured
```

**wiki/overview.md**:

```markdown
---
title: "{Domain} — Overview"
type: overview
sources: []
related: []
created: {today's date}
updated: {today's date}
confidence: speculative
---

# {Domain} Overview

_This overview will be updated as sources are ingested._
```

### Step 4: Generate wiki-schema.md

This is the per-wiki schema. Customize the domain name and conventions based on what the
user told you. Include:

1. **Wiki identity** — what domain this wiki covers, its purpose
2. **Page frontmatter spec**:
   ```yaml
   ---
   title: Page Title
   type: concept|entity|source|comparison|overview
   sources: [raw/ file paths or URLs]
   related: [wiki page paths]
   created: YYYY-MM-DD
   updated: YYYY-MM-DD
   confidence: high|medium|low|speculative
   ---
   ```
3. **Naming conventions** — kebab-case filenames, e.g., `wiki/concepts/gradient-descent.md`
4. **Cross-referencing rules** — relative markdown links, update both sides of a link
5. **Ingest workflow** — summarized steps
6. **Query workflow** — summarized steps
7. **Lint workflow** — summarized steps
8. **Confidence levels**:
   - `high` — multiple corroborating sources, well-established
   - `medium` — single reliable source, consistent with other knowledge
   - `low` — single source, not yet corroborated
   - `speculative` — inferred/synthesized, needs verification

### Step 5: Register the wiki

Create `~/wikis/` and `~/wikis/registry.json` if they don't exist. Add the new wiki entry.
Use the full expanded path (not `~`).

Tell the user the wiki is ready and suggest they drop sources into `raw/` and ask to ingest.

---

## Ingest — Process a New Source

### Step 1: Read the source

Read the raw file. If the user gave a URL instead of a file, fetch it and save to the
appropriate `raw/` subdirectory before proceeding.

### Step 2: Discuss takeaways

Present 3-5 key takeaways to the user. Ask if they want to highlight anything specific
or if these look right.

### Step 3: Create the source summary

Write to `wiki/sources/{kebab-case-title}.md` with full frontmatter. Include:
- One-paragraph summary
- Key claims or findings (bulleted)
- Notable quotes with section references
- Limitations or caveats

### Step 4: Update related wiki pages

For each key concept:
- If `wiki/concepts/{concept}.md` exists → update it, add source to `sources` list
- If not → create it, mark confidence as `low`

For each entity (person, org, tool, product):
- Same logic with `wiki/entities/`

If the source directly compares things, create or update `wiki/comparisons/`.

### Step 5: Update index.md

Add one-line entries for all new/updated pages. Keep entries sorted alphabetically.

### Step 6: Consider the overview

If the new source changes the big picture, update `wiki/overview.md`. If it just
adds detail to existing themes, skip.

### Step 7: Log the activity

Append to `wiki/log.md`:

```markdown
## [{today's date}] ingest | {Source Title}
- Source: `raw/{path}`
- Created: {list of new pages}
- Updated: {list of updated pages}
```

---

## Query — Answer Questions from the Wiki

### Step 1: Read the index

Read `wiki/index.md` to identify relevant pages.

### Step 2: Read relevant pages

Read identified pages. Follow cross-references if needed.

### Step 3: Synthesize an answer

Answer with citations to specific wiki pages using relative links.
If the wiki doesn't have enough information, say so and suggest what sources might help.

### Step 4: Offer to file new insights

If synthesis produced a genuinely new insight, offer to save it as a new page.
Only for lasting value — don't file every query answer.

### Step 5: Log the query

Append to `wiki/log.md`:

```markdown
## [{today's date}] query | {Question summary}
- Pages consulted: {list}
- New pages created: {list, or "none"}
```

---

## Lint — Health Check the Wiki

### Step 1: Scan for contradictions

Read all wiki pages. Report conflicting claims with page references and quotes.

### Step 2: Find orphan pages

Check every file in `wiki/` subdirectories against `wiki/index.md` and cross-references.
Report pages not linked from anywhere.

### Step 3: Identify missing concepts

Scan for concept names mentioned across pages that don't have their own page in
`wiki/concepts/`. Prioritize ones mentioned in multiple pages.

### Step 4: Flag stale claims

Look for pages with old `updated` dates covering fast-moving topics. Suggest refreshes.

### Step 5: Suggest investigations

Propose 3-5 sources or topics to research next to fill gaps.

### Step 6: Log the lint

Append to `wiki/log.md`:

```markdown
## [{today's date}] lint | Health check
- Contradictions: {count}
- Orphan pages: {count}
- Missing concepts: {count}
- Stale pages: {count}
- Suggestions: {brief list}
```

---

## Conventions

- **Filenames**: kebab-case, `.md` extension. e.g., `neural-network-architectures.md`
- **Frontmatter**: Every wiki page gets the full YAML block. Always update `updated` when modifying.
- **Cross-references**: Relative markdown links. When linking A→B, also add A to B's `related` list.
- **Confidence progression**: `low` (1 source) → `medium` (2 sources) → `high` (3+ sources). `speculative` for synthesized insights.
- **Raw sources are immutable**: Never modify `raw/`. Annotations go in wiki pages.
- **Index is the hub**: `wiki/index.md` must always reflect every page. Create a page → update index. Delete a page → update index.
