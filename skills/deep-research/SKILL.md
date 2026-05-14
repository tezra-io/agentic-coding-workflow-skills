---
name: deep-research
description: Grounded research on places, businesses, restaurants, hotels, people, products, events, travel and flights, and similar real-world subjects. Use whenever the answer should be cited, might have changed since training data, or needs to be verified against current sources rather than recalled from memory.
---

# Deep Research (Exa + Parallel)

Direct-HTTP web research that combines Exa (fast, semantic, broad) with Parallel (fresh, structured, deep). No MCP — calls the public APIs via a Python wrapper at `scripts/research.py`.

## Auth

Set in your shell or `~/.claude/settings.json` env block:

- `EXA_API_KEY` — required for `search`, `answer`, `contents`, `similar`, `task`
- `PARALLEL_API_KEY` — required for `p-search`, `p-task`, `p-extract`, `p-chat`

The script errors with the exact missing variable if either is absent. If only one key is set, fall back to whichever provider you have.

## Two-line orientation

- **Default to Exa** for almost everything; it's cheaper and faster.
- **Reach for Parallel** when (a) you need a JSON object with per-field citations, (b) the topic is breaking news / very recent, or (c) Exa returned thin or stale results.

## Quick start

The script lives at `scripts/research.py` (relative to this skill). Invoke it directly — it's executable. JSON goes to stdout; pipe through `jq` to slice it.

```bash
# 1. Direct answer with citations  — best for "what is the X of Y" style questions
./scripts/research.py answer "What is SpaceX's current valuation?" --text --pretty

# 2. Search with summaries  — best for "find me X" style questions
./scripts/research.py search "best wood-fired pizza in Brooklyn" --num 10 \
  --summary "What kind of pizza, address, what reviewers praise" --pretty

# 3. Single entity, several named fields  — `answer` with a JSON schema, NOT `task`
./scripts/research.py answer \
  "Le Bernardin in NYC: head chef, michelin stars, cuisine type, average dinner price USD, dress code, reservation URL." \
  --text --schema /tmp/schema.json --pretty
```

## Choosing the right subcommand

Pick the smallest tool that can answer the question. Most questions need one call.

| Question shape                                                                | Subcommand                                | Cost / latency        |
|-------------------------------------------------------------------------------|-------------------------------------------|-----------------------|
| Single fact — "what / who / where / when is X"                                | `answer`                                  | ~$0.005 / ~3–5 s      |
| Single entity, several named fields ("X: chef, stars, price, URL")            | `answer` (+ `--schema` if you want JSON)  | ~$0.005 / ~3–5 s      |
| "Find me a list of X matching Y" — discovery                                  | `search` (+ `--summary` per result)       | ~$0.007–0.015 / 1–3 s |
| "Get the content of these specific URLs"                                      | `contents`                                | ~$0.001/page          |
| "More like this URL" — competitor or analog discovery                         | `similar`                                 | search-priced         |
| **Multi-source synthesis** — "compare 3 X by Y/Z", "build me an itinerary"    | `task` (Exa) or `p-task core` (Parallel)  | $0.05–$0.50 / 1–10 m  |
| Need a JSON object with **per-field provenance** (different source per field) | `p-task base`/`core`                      | $0.01–$0.025 / 1–5 m  |
| Breaking news from the last hours/days                                        | `p-search --mode advanced`                | $0.009 / 15–70 s      |
| URLs that are JS-heavy or PDFs and `contents` falls flat                      | `p-extract`                               | per-page              |

**Don't reach for `task` when `answer` will do.** A single restaurant / company / person profile, even with 6+ named fields, is `answer` territory — it's ~100× cheaper and ~50× faster than `task`. Use `task` only when (a) you genuinely need multi-source synthesis the model has to reason about, or (b) you want per-field citations from different sources (and even then `p-task` is usually better than Exa `task`).

When unsure which Exa search `--type` to use, omit it (defaults to `auto`). Use `--type deep` or `--type deep-reasoning` only when you also pass `--additional-queries` or `--schema`.

### Exa schema gotcha

Exa's `outputSchema` (on `/answer`, `/search` deep-reasoning, and `/research/v0/tasks`) requires **every root-level property to appear in `required[]`**. Optional fields cause a 400. Either include every property in `required` or move it to a sub-object. Same applies to `--schema` files.

## Domain playbook

Quick-start invocations per common entity type. Adapt the query — don't paste verbatim.

### Companies

Use `--category company` so Exa biases toward homepages and primary sources. Note: with this category, date filters and `--exclude-domains` are ignored, and `--include-text` accepts only one item.

```bash
./scripts/research.py search "category:company developer tools API testing Series B" \
  --num 15 --summary "What they do, funding stage, HQ" --pretty
```

For a single named company with structured fields, use `answer` (cheap, fast, includes citations):

```bash
./scripts/research.py answer \
  "Company Anthropic: HQ city, employee count, latest funding round size and date, three top execs." \
  --text --schema /tmp/co.json --pretty
```

Reach for `task` / `p-task` only if you need multi-source synthesis (e.g., "compare Anthropic, OpenAI, and Mistral on commercial traction").

### People

Use `--category people` (LinkedIn-only domain restriction). For individuals you already named, `answer` is usually enough:

```bash
./scripts/research.py answer "Who is the current Head of Research at Anthropic, and when did they start?" --text --pretty
```

Discovery (find people by role/criteria):

```bash
./scripts/research.py search "category:people Head of Growth B2B SaaS startup San Francisco" \
  --num 12 --highlights --pretty
```

### Places (cities, neighborhoods, attractions)

No category for places — use site signals (`--include-domains`) for tourism boards / TripAdvisor / Atlas Obscura:

```bash
./scripts/research.py search "things to do in Lisbon Alfama district neighborhood guide" \
  --num 10 --summary "Top recommendations, opening hours, getting there" --pretty
```

For "give me a real itinerary" style asks where you want synthesis, use `task`:

```bash
./scripts/research.py task \
  "Build a 2-day Lisbon itinerary focused on Alfama and Belém. Include opening hours, transit, and one good food stop per half-day." \
  --wait --pretty
```

**Always include an explicit closure/renovation check** in itinerary research — Exa's neural index lags on temporary closures and the result will quietly skip them:

```bash
./scripts/research.py answer \
  "Are any of these Lisbon attractions currently closed for renovation in 2026: Belém Tower, Jerónimos Monastery, Castelo de São Jorge, MAAT, National Pantheon?" \
  --text --pretty
```

If you skip this, you risk recommending a venue that's been shut for a year (the Belém Tower restoration was the canonical example of this trap).

### Restaurants

Combine semantic search with strong site signals. For lists / comparisons:

```bash
./scripts/research.py search "best omakase sushi Manhattan under $200 per person 2026" \
  --num 12 --include-domains eater.com nytimes.com infatuation.com theinfatuation.com \
  --summary "Cuisine, price range, what reviewers praise" --pretty
```

For a structured profile of one named restaurant, **default to `answer` with a schema** (cheap, fast, returns citations). Only escalate to `p-task` if you genuinely want a different source per field (Parallel's `basis[]` provenance), and only if `PARALLEL_API_KEY` is set:

```bash
# Default — one cheap call
./scripts/research.py answer \
  "Le Bernardin in NYC: head_chef, michelin_stars, cuisine_type, average_dinner_price_usd, reservation_url, dress_code." \
  --text --schema /tmp/restaurant.json --pretty

# Only if you need different sources per field (Parallel must be set up)
./scripts/research.py p-task \
  "Restaurant Le Bernardin in NYC. Return: head_chef, michelin_stars, cuisine_type, average_dinner_price_usd, reservation_url, dress_code." \
  --processor base --schema /tmp/restaurant.json --wait --pretty
```

**Schema must include EVERY property in `required[]`** (Exa rejects optional root properties):

```json
{
  "type": "object",
  "properties": {
    "head_chef": {"type": "string"},
    "michelin_stars": {"type": "integer"},
    "cuisine_type": {"type": "string"},
    "average_dinner_price_usd": {"type": "number"},
    "reservation_url": {"type": "string"},
    "dress_code": {"type": "string"}
  },
  "required": ["head_chef","michelin_stars","cuisine_type","average_dinner_price_usd","reservation_url","dress_code"]
}
```

**Before recommending a venue, run a fast closure check.** Exa's neural index can lag on temporary closures and renovations. One extra `answer` call is cheap insurance:

```bash
./scripts/research.py answer "Is Le Bernardin in NYC currently open, or closed for renovation? Any 2026 announced closures?" --text --pretty
```

Same applies to attractions/monasteries/towers (e.g., the Belém Tower restoration that runs through ~mid-2026 — easy to miss without an explicit "is it open?" query).

### Flights & travel logistics

Flights are tricky — neither provider hits live booking data. Two viable paths:

1. **Policies, routes, generic info** — works fine via search:

   ```bash
   ./scripts/research.py search "United Airlines policy for changing international flights award booking" \
     --include-domains united.com transportation.gov --num 8 --text --pretty
   ```

2. **Live prices / schedules** — use Parallel `p-task` with `pro` for synthesis. Note that real-time booking data is a known weak spot for both APIs; tell the user to verify on Google Flights / airline sites.

   ```bash
   ./scripts/research.py p-task \
     "Direct flights between SFO and Tokyo Narita in October 2026. Return: airline, weekly frequency, aircraft, typical economy round-trip price band." \
     --processor pro --wait --pretty
   ```

### News / current events

Freshness wins — go straight to Parallel `advanced` mode:

```bash
./scripts/research.py p-search \
  --objective "Latest material developments at Anthropic in the last 30 days: funding, products, leadership, regulation." \
  --queries "Anthropic news 2026" "Anthropic Claude release" "Anthropic funding round" \
  --mode advanced --num 10 --pretty
```

Or Exa with date filters when you have a known timeframe:

```bash
./scripts/research.py search "Anthropic enterprise product launches" --category news \
  --start-date 2026-04-01 --end-date 2026-05-09 --num 12 --highlights --pretty
```

### Research papers

```bash
./scripts/research.py search "category:research paper sparse attention long-context transformers efficient" \
  --num 12 --highlights --pretty
```

For a deep literature scan with synthesis, use Exa `task` with `--model exa-research-pro`.

### Code / GitHub

```bash
./scripts/research.py search "category:github open source rate limiter middleware Go fiber" \
  --num 10 --highlights --pretty
```

## When Exa is thin or stale → fall back

Symptoms that mean "switch to Parallel":

- Top results are tangential or all from one low-signal source
- Snippets are months out of date for a question that is time-sensitive
- The user wanted a structured object and Exa's answer is freeform prose

Fallback recipe:

```bash
# 1. Quick fallback — Parallel basic mode
./scripts/research.py p-search \
  --objective "<copy the user's intent>" \
  --queries "<3-5 word query>" "<another angle>" "<third angle>" \
  --mode basic --num 8 --pretty

# 2. If still thin or news is breaking — escalate to advanced
# (same call, --mode advanced, expect 15–70s)

# 3. If they need a JSON object with per-field provenance — task
./scripts/research.py p-task "<the entity or question>" \
  --processor base --schema /tmp/schema.json --wait --pretty
```

Don't redundantly chain Exa search → Exa answer → Exa task on the same query; pick one then escalate to Parallel if it underperforms.

## Working with the JSON output

All commands print one JSON object. A few useful shapes:

| Provider/cmd       | Top-level path to results               | Top-level path to citations               |
|--------------------|------------------------------------------|--------------------------------------------|
| Exa `search`       | `.results[]`                             | each result is its own citation            |
| Exa `answer`       | `.answer`                                | `.citations[]`                             |
| Exa `contents`     | `.results[]`                             | `.results[].url`                           |
| Exa `task`         | `.output.content` / `.output.parsed`     | `.citations[]`                             |
| Parallel `search`  | `.results[]` with `excerpts[]`           | each result is its own citation            |
| Parallel `task`    | `.output.content`                        | `.output.basis[]` (per-field!)             |
| Parallel `extract` | `.results[]` with `excerpts[]`           | each result is its own citation            |

Useful one-liners:

```bash
# Just titles + URLs from an Exa search
./scripts/research.py search "..." | jq -r '.results[] | "\(.title)\t\(.url)"'

# Answer + citation list
./scripts/research.py answer "..." --pretty | jq '{answer, citations: [.citations[] | {title, url}]}'

# Parallel task — show per-field provenance
./scripts/research.py p-task "..." --schema s.json --wait \
  | jq '.output.basis[] | {field, confidence, sources: [.citations[].url]}'
```

## Keeping result text compact

Result `text` blobs from Exa can be huge. Don't truncate them — pick a different extraction mode that returns less text by design:

| Want | Exa flag | Parallel equivalent |
|---|---|---|
| 3–5 most-relevant sentences per result | `--highlights` | default — `results[].excerpts[]` (already compact) |
| LLM-condensed blurb per result, biased to your question | `--summary "What does this place do?"` | `--objective "..."` shapes which excerpts are returned |
| Full extracted page text | `--text` | `p-extract` |

**Default to `--highlights` for agent loops.** Reach for `--text` only when (a) you need verbatim quotes, (b) the page is short, or (c) you've already filtered to a handful of URLs and the cost of full text is acceptable. If you must use `--text` on long pages, pass `--max-chars N` so the cap is intentional, not silent.

Parallel doesn't have a separate "highlights" mode because its `excerpts[]` are already the compact unit — the API is excerpts-first by design. Use `--max-chars-total` (Search top-level) or `--max-chars-per-result` (Search advanced settings) to tighten further; for Extract, `--max-chars` maps to `max_chars_total`.

## Cost awareness

Order-of-magnitude per call (single request, default options):

- Exa `search` / `contents`: cents — cheap; default to it.
- Exa `answer`: $0.005 — cheapest way to get a one-line answer with citations.
- Exa `task` (`exa-research`): typically $0.05–$0.50 depending on depth.
- Parallel `search base`: $0.004. `pro`: $0.009.
- Parallel `task lite`/`base`/`core`: $0.005 / $0.01 / $0.025. `pro`: $0.10.
- Parallel `task ultra*`: $0.30–$2.40 — **not supported** by this script (requires webhooks).

Don't fan out 10 parallel `task` calls without a reason. Prefer one well-scoped task over many speculative ones.

## Gotchas

- **`category:company` and `category:people`** disable date filters, `--exclude-domains`, and `--include-text` / `--exclude-text`. The API returns 400 if you combine them.
- **`--include-text` / `--exclude-text`** accept only a single item.
- **`numResults > 25` is wasteful** — run more queries at 10–15 each rather than one fat 50-result query.
- **Word order matters** in Exa queries (vector embeddings, not keyword). "Python async patterns for scraping" ≠ "Web scraping async patterns Python". For coverage, run two phrasings.
- **Don't use `--type deep` without `--additional-queries`** — wastes the deep-search compute. If you only have one phrasing, use `--type auto`.
- **Quote handling**: pass queries as a single argv (already a string in argparse). Strings with `"` need shell-escaping.
- **Parallel `ultra*` processors** require webhooks for delivery and are intentionally not exposed by this script. Cap at `pro`.
- **Don't trust results blindly** — Exa returns *similarity*, not validated matches. Skim titles/snippets before you cite anything.
- **Date drift**: today is whatever today is — don't reuse "2025" or "2026" from these examples; compute the actual date for time-sensitive queries.

## Reference docs

For full endpoint surfaces (every parameter, every response field, more curl examples):

- `references/exa-endpoints.md` — Exa `search`, `answer`, `contents`, `findSimilar`, `research/v0/tasks`, `websets`
- `references/parallel-endpoints.md` — Parallel `search`, `tasks`, `extract`, `chat`, `findall`, `monitor`
- `references/query-patterns.md` — extra query templates by entity type (deeper than the SKILL.md playbook)

Read a reference only when the SKILL.md doesn't cover what you need (e.g., advanced `subpages` extraction, custom `outputSchema` design, or websets-style enrichment).
