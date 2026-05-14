# Exa API — Full endpoint reference

Read when the wrapper script doesn't expose what you need (e.g. you want to call `/websets`, design a `subpages` extraction, or compose a `outputSchema` for deep-reasoning).

- **Base**: `https://api.exa.ai`
- **Auth**: header `x-api-key: $EXA_API_KEY` (Bearer also works)
- **Content-Type**: `application/json` on all POSTs
- **Free tier**: 1k requests/month
- **Dashboard**: https://dashboard.exa.ai

## Endpoint map

| Endpoint                          | Method  | Purpose                                                                  |
|-----------------------------------|---------|--------------------------------------------------------------------------|
| `/search`                         | POST    | Search (neural, keyword, auto, deep, deep-reasoning, instant, fast)      |
| `/contents`                       | POST    | Extract page text, highlights, summary, subpages from URLs               |
| `/answer`                         | POST    | Web-grounded answer with citations (optional structured output)          |
| `/findSimilar`                    | POST    | Pages semantically similar to a given URL                                |
| `/research/v0/tasks`              | POST    | Async multi-step agentic research with citations                         |
| `/research/v0/tasks/{id}`         | GET     | Poll status / fetch result                                               |
| `/websets/v0/websets/...`         | various | Verified, enriched datasets at scale (async)                             |
| `/monitors`                       | various | Scheduled recurring searches with webhook delivery                       |

## Deprecations to know

- `/research/v1` is deprecated → use `/research/v0/tasks` (current) or `/search` with `type: deep-reasoning` (future-proof).
- `livecrawl` parameter → use `maxAgeHours` (positive int = use cache if newer, `0` = always live, `-1` = never live).
- `ids` field on `/contents` → use `urls`.

## `/search`

Vector-embedding semantic search. Optional content extraction in the same call.

### Body

| Field | Type | Default | Notes |
|---|---|---|---|
| `query` | string | required | Describe the page, not the fact. Word order matters. |
| `type` | enum | `auto` | `neural`, `keyword`, `auto`, `fast`, `deep`, `deep-reasoning`, `instant` |
| `category` | enum | — | `company`, `research paper`, `news`, `pdf`, `github`, `personal site`, `people`, `financial report` |
| `numResults` | int | 10 | Max 100. Sweet spot 10–15. |
| `includeDomains` / `excludeDomains` | string[] | — | Max 1200. `excludeDomains` not supported with `category:company` or `category:people`. For `category:people`, only LinkedIn allowed. |
| `startPublishedDate` / `endPublishedDate` | ISO 8601 | — | Not with `category:company`/`people`. |
| `startCrawlDate` / `endCrawlDate` | ISO 8601 | — | Same restriction. |
| `includeText` / `excludeText` | string[] (single item only) | — | Not with `company`/`people`. |
| `userLocation` | string | — | Two-letter ISO country code. |
| `additionalQueries` | string[] | — | `type: deep` or `deep-reasoning` only. |
| `outputSchema` | JSON Schema | — | Deep-search structured output. |
| `systemPrompt` | string | — | Guides synthesized output for deep variants. |
| `stream` | bool | false | SSE stream. |
| `moderation` | bool | false | Filter explicit content. |
| `contents` | object | — | See below. |

### `contents` sub-object (also accepted as siblings on `/search`)

| Field | Type | Notes |
|---|---|---|
| `text` | bool \| `{maxCharacters, includeHtmlTags, verbosity, includeSections, excludeSections}` | `verbosity`: `compact` (default), `standard`, `full` (requires `livecrawl: always`). |
| `highlights` | bool \| `{numSentences, highlightsPerUrl, query}` | Token-efficient default; recommended for agent loops. |
| `summary` | `{query, schema}` | LLM summary; `schema` for structured output. |
| `subpages` | int | 0 default. Crawl this many linked pages per result. |
| `subpageTarget` | string \| string[] | Keywords identifying subpages, e.g. `"references"`. |
| `extras` | `{links, imageLinks}` | Counts of links and image URLs. |
| `maxAgeHours` | int | Cache control. |
| `livecrawlTimeout` | int | ms, default 10000. |
| `context` | bool | Returns LLM-friendly concatenated context blob. |

### Response

```json
{
  "requestId": "string",
  "results": [
    {
      "id": "string", "url": "...", "title": "...",
      "publishedDate": "YYYY-MM-DD | null", "author": "string | null",
      "image": "uri | null", "favicon": "uri | null",
      "score": 0.87,
      "text": "...", "highlights": ["..."], "highlightScores": [0.91],
      "summary": "...",
      "subpages": [/* nested */],
      "extras": { "links": [...], "imageLinks": [...] }
    }
  ],
  "searchType": "neural | deep | ...",
  "output": {
    "content": "string | object",
    "grounding": [{ "field": "leader", "citations": [...], "confidence": "high" }]
  },
  "costDollars": { "total": 0.007, "breakDown": [...] }
}
```

### Examples

```bash
# Default
curl -X POST 'https://api.exa.ai/search' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"blog post by senior engineer about LLM eval framework tradeoffs","numResults":10,"contents":{"highlights":true}}'

# Category-filtered with summary
curl -X POST 'https://api.exa.ai/search' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"category:company developer tools API testing Series A",
       "numResults":15,
       "contents":{"text":{"maxCharacters":2000},
                   "summary":{"query":"What does the company do? Funding stage?"}}}'

# Deep search w/ structured output (replaces deprecated /research/v1 for many cases)
curl -X POST 'https://api.exa.ai/search' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"Who is the CEO of OpenAI and when did they start?",
       "type":"deep-reasoning",
       "additionalQueries":["OpenAI leadership","Sam Altman OpenAI tenure"],
       "outputSchema":{"type":"object","properties":{
         "leader":{"type":"string"},"title":{"type":"string"},
         "startDate":{"type":"string"},"sourceCount":{"type":"number"}},
         "required":["leader","title"]},
       "contents":{"text":true}}'
```

## `/contents`

Extract content from known URLs.

### Body

`urls` (string[], required). Plus `text`, `highlights`, `summary`, `subpages`, `subpageTarget`, `extras`, `maxAgeHours`, `livecrawlTimeout`, `context` — same shape as `/search` `contents`.

### Examples

```bash
# Simple
curl -X POST 'https://api.exa.ai/contents' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"urls":["https://arxiv.org/abs/2307.06435"],"text":true}'

# Bounded text + scoped highlights + summary + subpage crawl
curl -X POST 'https://api.exa.ai/contents' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"urls":["https://arxiv.org/abs/2307.06435"],
       "text":{"maxCharacters":1000,"includeHtmlTags":false},
       "highlights":{"numSentences":3,"highlightsPerUrl":2,"query":"Key findings"},
       "summary":{"query":"Main research contributions"},
       "subpages":1,"subpageTarget":"references",
       "extras":{"links":2,"imageLinks":1}}'

# Force fresh crawl
curl -X POST 'https://api.exa.ai/contents' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"urls":["https://news.example.com/breaking"],"text":true,"maxAgeHours":0}'
```

## `/answer`

| Field | Type | Notes |
|---|---|---|
| `query` | string | required |
| `text` | bool | Include full text in citations |
| `stream` | bool | SSE stream |
| `outputSchema` | JSON Schema Draft 7 | Returns `answer` as object instead of string |

### Response

```json
{
  "answer": "string OR object matching outputSchema",
  "citations": [{"id":"...","url":"...","title":"...","author":"...","publishedDate":"...","text":"...","image":"...","favicon":"..."}],
  "costDollars": {"total": 0.005}
}
```

### Examples

```bash
curl -X POST 'https://api.exa.ai/answer' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"What is the latest valuation of SpaceX?","text":true}'

# Structured
curl -X POST 'https://api.exa.ai/answer' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"Who is the current CEO of Anthropic?",
       "outputSchema":{"type":"object",
         "properties":{"name":{"type":"string"},"since":{"type":"string"}},
         "required":["name"]}}'
```

## `/findSimilar`

| Field | Type | Notes |
|---|---|---|
| `url` | string | required |
| `excludeSourceDomain` | bool | Drop results from the same domain |
| (rest) | — | Same as `/search`: `numResults`, `includeDomains`, etc., plus `contents`. |

```bash
curl -X POST 'https://api.exa.ai/findSimilar' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"url":"https://stripe.com","category":"company","numResults":15,
       "contents":{"summary":{"query":"What does this company do?"}}}'
```

## `/research/v0/tasks`

Async; create then poll.

### Create — POST `/research/v0/tasks`

| Field | Type | Default | Notes |
|---|---|---|---|
| `instructions` | string | required | Max 4096 chars. |
| `model` | enum | `exa-research` | `exa-research` (balanced) or `exa-research-pro` (deeper). **`exa-research-fast` does not exist** — older docs mention it but the API rejects it with a 400. |
| `output.schema` | JSON Schema | — | Optional structured output. **All root-level properties must be in `required[]`** — Exa rejects optional roots. |
| `output.inferSchema` | bool | false | If true and no schema given, the model generates one (and correctly puts every property in `required[]`). |

Returns 201 with `{ id, outputSchema }`. **The id field is named `id`, not `researchId`** (older docs say `researchId` but the live API returns `id`). The wrapper script accepts both.

### Poll — GET `/research/v0/tasks/{id}`

Status enum: `pending`, `running`, `completed`, `canceled`, `failed`.

Live response shape (verified 2026-05):

```json
{
  "id": "01kr6...",
  "createdAt": 1778344088500,
  "status": "completed",
  "instructions": "...",
  "schema": { /* the outputSchema (auto-inferred or user-supplied) */ },
  "data": { /* structured object matching schema — this is the result */ },
  "citations": [/* AnswerCitation-style; may be omitted when schema is auto-inferred */],
  "costDollars": {"total": 0.42, "numSearches": 17, "numPages": 31, "reasoningTokens": 124000}
}
```

Older docs describe this as `{researchId, output: {content, parsed}}`. The current API returns `{id, data}`.

Query params: `?stream=true`, `?events=true`.

### List — GET `/research/v0/tasks?cursor=...&limit=25`

Limit 1–200, default 25.

## `/websets/v0/...`

Async, large-scale, *verified* web data collection. Searches, verifies each result against criteria, enriches with extra fields. Items billed per row.

| Endpoint | Method | Purpose |
|---|---|---|
| `/websets/v0/websets` | POST | Create (search + criteria + enrichments) |
| `/websets/v0/websets/{id}` | GET / PUT / DELETE | Status / update / remove |
| `/websets/v0/websets/{id}/cancel` | POST | Stop |
| `/websets/v0/websets/{id}/preview` | POST | Preview decomposition before charging |
| `/websets/v0/websets/{id}/searches` | POST | Add another search |
| `/websets/v0/websets/{id}/items` | GET | List verified, enriched results |
| `/websets/v0/websets/{id}/imports` | POST | Upload existing data into webset |
| `/websets/v0/websets/{id}/enrichments` | POST | Add a new column |
| `/websets/v0/websets/{id}/monitors` | POST | Continuous-update monitor |
| `/webhooks` | POST/GET/PUT/DELETE | Webhook config |

```bash
curl -X POST 'https://api.exa.ai/websets/v0/websets' \
  -H "x-api-key: $EXA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"search":{"query":"Series A B2B SaaS in NYC building developer tools","count":50},
       "enrichments":[{"description":"CEO name","format":"text"},
                      {"description":"Last funding $","format":"number"},
                      {"description":"Headcount","format":"number"}]}'
```

Webset use case: "find 100 X meeting Y criteria with these data points filled in." Skip for one-off questions.

## Pricing (per 1k requests)

| | Cost |
|---|---|
| Search (auto/neural/keyword/instant/fast) | $7 + $1 per result over 10 |
| Deep search | $12–15 |
| Deep-reasoning | $15 |
| Contents | $1 per 1k pages |
| AI summaries (any endpoint) | +$1 per 1k pages |
| Answer | $5 |
| Monitors | $15 |
| Research / Websets | per-token / per-item |

## Field-tested gotchas

- `category:company` and `category:people` block date filters, domain excludes, and `includeText`/`excludeText`. Hitting them returns 400.
- `includeText` / `excludeText` accept single-item arrays only.
- `excludeDomains` for `category:people` only accepts LinkedIn domains.
- Word order in queries affects embeddings — run multiple phrasings for coverage.
- `numResults > 25` is wasteful. Run more queries at 10–15 each.
- Exa returns *similarity*, not validated matches — always inspect titles/snippets before citing.
- `/research/v1` is being phased out; use `/research/v0/tasks` or `/search` with `type: deep-reasoning`.

## SDKs (if you want them)

- Python: `pip install exa-py` → `from exa_py import Exa; exa = Exa(KEY)`. Methods: `exa.search_and_contents`, `exa.answer`, `exa.find_similar_and_contents`, `exa.get_contents`.
- JS/TS: `npm install exa-js` → `import Exa from 'exa-js'`. Methods: `searchAndContents`, etc.

## Useful URLs

- Pricing: https://exa.ai/pricing
- Full docs index: https://exa.ai/docs/llms.txt
- OpenAPI YAML: https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml
- Reference skill repo: https://github.com/exa-labs/exa-mcp-server (the `skills/search` directory)
