# Query patterns by entity type

Deeper recipes than what's in SKILL.md — read this when the basic playbook doesn't fit. Each section gives: how Exa likes the query phrased, which `--category` to use (if any), and how to escalate to Parallel.

## General principles

- **Describe the *page*, not the *fact*.** Exa is vector-similarity, not keyword. Bad: `"Tesla 2026 Q1 revenue"`. Good: `"Tesla 2026 Q1 earnings press release with revenue and guidance"`.
- **Word order matters.** `"Python web scraping async"` and `"async Python web scraping"` return overlapping but different sets. For coverage on hard queries, run two phrasings.
- **Use `category:` inline OR via `--category`.** Both work; the inline form is convenient when running ad-hoc curls. The script's `--category` is the cleaner form.
- **Time semantics in the query string** beat date filters when category restrictions block dates: `"published in March 2026"` or `"announced last week"`.
- **`numResults`**: 5 for named entity lookups, 10 for precise filters, 15 for broad discovery. Above 25 is wasteful — run another query instead.
- **Exa returns *similarity*, not *truth*.** Always inspect `title` and `score` before citing.
- **Default to `answer` for single entities, even when many fields are requested.** It's ~$0.005 per call vs $0.05–$0.50 for `task`. Reserve `task` / `p-task` for genuine multi-source synthesis (comparisons, itineraries, market scans).
- **Run a closure / status check before recommending a venue or attraction.** Exa's neural index lags on temporary closures. One extra `answer` call is much cheaper than the embarrassment of recommending something that's been shut for renovation. See "Closure & status checks" below.

## Closure & status checks (before recommending anything dated)

If the answer to "is this still operating?" might have changed in the last 12 months, run an explicit status check before you cite anything that assumes it's open. Cheap, fast, catches a class of failure that snippet-style search misses.

```bash
# Single venue
./scripts/research.py answer \
  "Is the Belém Tower in Lisbon currently open to visitors in 2026, or closed for renovation?" \
  --text --pretty

# Several at once (one call)
./scripts/research.py answer \
  "As of 2026, are any of these Lisbon attractions closed or under renovation: Belém Tower, Jerónimos Monastery, Castelo de São Jorge, MAAT, National Pantheon, National Coach Museum?" \
  --text --pretty

# Restaurants — closures, ownership change, chef departure all matter
./scripts/research.py answer \
  "Is Le Bernardin in NYC currently open in 2026? Any announced closures, renovations, or chef changes since 2024?" \
  --text --pretty
```

When to bother:
- Itineraries — every monastery / castle / museum / tower
- Restaurant recommendations — anything Michelin-tier or chef-driven (chefs move; restaurants close)
- Travel planning — airports, train stations, ferries (route suspensions / strikes)
- Software / SaaS recommendations — startups that may have been acquired or shut down

When NOT to bother:
- One-off facts that don't depend on operational status ("when was X founded")
- Major institutions whose closure would be huge news (universities, capitals, well-known museums)

## Companies

### Discovery (find companies matching criteria)

```bash
./scripts/research.py search "category:company developer tools API testing Series B" \
  --num 15 --summary "What they do, funding stage, HQ" --pretty

./scripts/research.py search "category:company AI inference infrastructure GPU rental startup 2025" \
  --num 15 --highlights --pretty
```

Note: `category:company` blocks `--exclude-domains`, date filters, and `--include-text`/`--exclude-text`.

### Single-entity profile

```bash
# Cheapest: one-line answer with citations
./scripts/research.py answer "Where is Anthropic headquartered, and what was their last funding round?" --text --pretty

# Structured fields with per-field citations (Parallel's basis[])
./scripts/research.py p-task \
  "Company Anthropic. Return: hq_city, founded_year, employee_count, latest_funding_round_size_usd, latest_funding_round_date, ceo_name." \
  --processor base --schema /tmp/co.json --wait --pretty
```

### Competitor / analog discovery from one URL

```bash
./scripts/research.py similar "https://stripe.com" \
  --category company --num 15 --exclude-source-domain \
  --summary "What they do, target customer" --pretty
```

## People

### Single named person

```bash
# Most efficient: answer
./scripts/research.py answer \
  "Who is the current Head of Research at Anthropic, and when did they start?" \
  --text --pretty

# When you need a structured bio
./scripts/research.py p-task \
  "Person Dario Amodei: current title, company, prior roles, notable publications." \
  --processor base --infer-schema --wait --pretty
```

### Discovery (find people by role/criteria)

```bash
./scripts/research.py search "category:people Head of Growth B2B SaaS startup San Francisco" \
  --num 12 --highlights --pretty
```

`category:people` only allows `--include-domains` of LinkedIn-shaped domains.

### Expert finding (criteria-driven, not name-driven)

Two-pass pattern — pass 1 finds what practitioners value, pass 2 finds people:

```bash
# Pass 1: criteria
./scripts/research.py search "what makes a great staff engineer at scale-stage startups practitioner perspective" \
  --num 10 --summary "Concrete criteria they cite" --pretty

# Pass 2: candidates against the criteria from pass 1
./scripts/research.py search "category:people Staff Engineer scaled engineering org systems thinking writing" \
  --num 15 --highlights --pretty
```

## Places (cities, neighborhoods, attractions)

No category — use site signals + descriptive phrasing.

### General orientation

```bash
./scripts/research.py search "Lisbon Alfama district neighborhood guide things to do food walking" \
  --include-domains atlasobscura.com tripadvisor.com timeout.com nytimes.com \
  --num 10 --summary "Top recommendations, opening hours, getting there" --pretty
```

### Itinerary synthesis

When the user wants a real plan, use `task` so it synthesizes:

```bash
./scripts/research.py task \
  "Build a 2-day Lisbon itinerary focused on Alfama and Belém. Include opening hours, transit, and one good food stop per half-day. Cite sources for hours and prices." \
  --model exa-research --wait --pretty
```

### Niche / off-the-beaten-path

```bash
./scripts/research.py search "underrated viewpoints Lisbon away from tourists local recommendations" \
  --num 10 --highlights --pretty
```

## Restaurants

### Discovery / "best of" lists

Strong site signals matter — Eater, Infatuation, NYT, Michelin Guide:

```bash
./scripts/research.py search "best omakase sushi Manhattan under \$200 per person 2026" \
  --include-domains eater.com nytimes.com theinfatuation.com infatuation.com \
  --num 12 --summary "Cuisine, price, what reviewers praise, address" --pretty
```

### Single-restaurant profile

**Default to `answer` with a schema** — one call, ~$0.005, includes citations. Don't reach for `task` / `p-task` unless you genuinely need synthesis or different sources per field.

Schema (`/tmp/restaurant.json`) — note **every property must be in `required[]`** for Exa:

```json
{
  "type": "object",
  "properties": {
    "head_chef": {"type": "string"},
    "michelin_stars": {"type": "integer"},
    "cuisine_type": {"type": "string"},
    "average_dinner_price_usd": {"type": "number"},
    "reservation_url": {"type": "string"},
    "dress_code": {"type": "string"},
    "neighborhood": {"type": "string"},
    "noise_level": {"type": "string"}
  },
  "required": ["head_chef","michelin_stars","cuisine_type","average_dinner_price_usd","reservation_url","dress_code","neighborhood","noise_level"]
}
```

```bash
# Default — fast, cheap
./scripts/research.py answer \
  "Le Bernardin in NYC: head_chef, michelin_stars, cuisine_type, average_dinner_price_usd, reservation_url, dress_code, neighborhood, noise_level." \
  --text --schema /tmp/restaurant.json --pretty

# Then run a closure check (cheap insurance)
./scripts/research.py answer \
  "Is Le Bernardin in NYC currently open in 2026? Any announced renovations or chef changes since 2024?" \
  --text --pretty

# Only escalate to p-task if you need per-field citations from different sources
./scripts/research.py p-task \
  "Restaurant Le Bernardin in NYC. Fill the schema, with citations per field." \
  --processor base --schema /tmp/restaurant.json --wait --pretty
```

### Live reservation availability

Neither API touches live booking data. State this to the user and direct them to OpenTable / Resy. You can still find phone numbers and reservation page URLs.

## Hotels

```bash
./scripts/research.py search "boutique hotels Tokyo Shibuya under \$300 per night 2026" \
  --include-domains tablethotels.com booking.com nytimes.com cntraveler.com \
  --num 12 --summary "Style, price, location, what reviewers note" --pretty
```

For comparing 3 specific hotels with structured criteria:

```bash
./scripts/research.py p-task \
  "Compare The Ace Hotel NYC, The Mark, and The Greenwich Hotel: nightly rate ranges, neighborhood, signature amenities, recent reviews highlights." \
  --processor core --wait --pretty
```

## Flights & travel logistics

Caveat to set with the user upfront: **neither API hits live booking data**. They surface schedules, route info, policy docs — not real-time prices or seat availability.

### Policies / rules / generic info

```bash
./scripts/research.py search "United Airlines policy for changing international flights award booking" \
  --include-domains united.com transportation.gov \
  --num 8 --text --max-chars 3000 --pretty
```

### Route / airline info

```bash
./scripts/research.py p-task \
  "Direct flights between SFO and Tokyo Narita in October 2026. Return: airline, weekly frequency, aircraft, typical economy round-trip price band, codeshare partners." \
  --processor pro --wait --pretty
```

### "Where can I fly nonstop to from X"

```bash
./scripts/research.py search "all nonstop destinations from San Francisco SFO international 2026" \
  --num 15 --text --max-chars 2000 --pretty
```

## News / current events

Freshness wins — Parallel `advanced` mode is built for this:

```bash
./scripts/research.py p-search \
  --objective "Material developments at Anthropic in the last 30 days: funding, products, leadership, regulation." \
  --queries "Anthropic news 2026" "Anthropic Claude release" "Anthropic funding round" \
  --mode advanced --num 10 --pretty
```

When you have a known timeframe and want Exa-style links:

```bash
./scripts/research.py search "Anthropic enterprise product launches" \
  --category news --start-date 2026-04-01 --end-date 2026-05-09 \
  --num 12 --highlights --pretty
```

## Research papers

```bash
./scripts/research.py search "category:research paper sparse attention long-context transformers efficient inference" \
  --num 12 --highlights --pretty
```

For literature synthesis (multi-paper review):

```bash
./scripts/research.py task \
  "Survey of sparse attention mechanisms for long-context transformers, 2024-2026. Summarize 5-8 key papers with their core idea, dataset, and headline result. Include arxiv links." \
  --model exa-research-pro --wait --pretty
```

For one paper's contents:

```bash
./scripts/research.py contents https://arxiv.org/abs/2307.06435 \
  --text --max-chars 4000 --summary "Main contribution and method" --pretty
```

## Code / GitHub

```bash
./scripts/research.py search "category:github open source rate limiter middleware Go fiber" \
  --num 10 --highlights --pretty

./scripts/research.py search "category:github example sqlite full text search trigram tokenizer" \
  --num 8 --text --max-chars 2000 --pretty
```

For a specific repo's README / docs:

```bash
./scripts/research.py contents https://github.com/some/repo \
  --text --summary "What it does, who it's for, install steps" --pretty
```

## Products / reviews

```bash
./scripts/research.py search "best wired earbuds for stage musicians under \$300 2026 reviews" \
  --include-domains rtings.com wirecutter.com soundguys.com \
  --num 12 --summary "Sound quality, comfort, price, who they're for" --pretty
```

For one product, structured comparison-friendly:

```bash
./scripts/research.py p-task \
  "Sony WH-1000XM5: release year, ANC quality, battery life hours, weight, current MSRP, common complaints." \
  --processor base --infer-schema --wait --pretty
```

## Comparison ("X vs Y vs Z")

For any entity type, Parallel `core` task is usually the right tool — it does the multi-source synthesis you want:

```bash
./scripts/research.py p-task \
  "Compare GitLab vs Linear vs Jira on: pricing for 50-person team, killer features, biggest weakness in 2026." \
  --processor core --wait --pretty
```

Avoid running three separate `search` calls and trying to synthesize in your head — wastes calls and tokens.

## When the obvious approach returns nothing

1. **Rephrase by angle, not synonym.** If "best" returned nothing useful, try "underrated", "what practitioners actually use", "what shipped to production".
2. **Drop the category.** Sometimes `category:company` is too restrictive for very small or very new entities.
3. **Run two parallel phrasings** (don't actually parallelize — call sequentially):
   - `search "X for Y use case"` and `search "Y problem solved by X"`.
4. **Escalate provider.** Exa thin → Parallel `Search base` → Parallel `Search pro` → Parallel `Task core`.
5. **Check if it's a real-time data question.** If yes (live prices, reservations, traffic, flight status), say so to the user — neither provider helps and pretending otherwise is worse than admitting the limit.
