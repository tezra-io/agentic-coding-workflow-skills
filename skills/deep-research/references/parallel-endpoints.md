# Parallel AI API — Full endpoint reference

Read when the wrapper script doesn't expose what you need (e.g. you want FindAll, monitors, or to call `/chat/completions` with a specific model not in the script).

- **Base**: `https://api.parallel.ai`
- **Auth**: header `x-api-key: $PARALLEL_API_KEY` (or `Authorization: Bearer ...`)
- **Content-Type**: `application/json` on all POSTs
- **Beta**: some FindAll routes also need `parallel-beta: <feature>-YYYY-MM-DD`
- **Free tier**: 20,000 requests across all APIs
- **Versioned paths**: `/v1/...` stable, `/v1beta/...` beta, `/alpha/...` legacy
- **Dashboard**: https://platform.parallel.ai

## Endpoint map

| Endpoint | Path | Best for |
|---|---|---|
| **Search** | `POST /v1/search` | Quick, LLM-optimized web search with extended excerpts |
| **Extract** | `POST /v1/extract` | Convert specific URLs (incl. JS pages, PDFs) to clean excerpts |
| **Task — create** | `POST /v1/tasks/runs` | Long-horizon structured research with citations |
| **Task — result (blocking)** | `GET /v1/tasks/runs/{run_id}/result` | Block until done; safe up to ~10 min (`pro`); webhooks for `ultra*` |
| **Task — status** | `GET /v1/tasks/runs/{run_id}` | Poll status |
| **Task — events (SSE)** | `GET /v1/tasks/runs/{run_id}/events` | Stream progress; supports `last_event_id` resume |
| **Chat (OpenAI-compat)** | `POST /chat/completions` | OpenAI shape; models: `speed`, `lite`, `base`, `core` |
| **FindAll (beta)** | `POST /v1beta/findall/runs` | Discover/verify lists of entities |
| **Monitor** | `POST /v1/monitors` | Continuous web watching |

## `/v1/search`

The closest match to Exa's `/search`. AI-native search returning ranked URLs with **extended excerpts** sized for LLM context (not teaser snippets).

### Body (verified against live OpenAPI spec, 2026-05)

Top-level fields:

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `objective` | string | one of these required | — | NL goal (max ~5000 chars). Used together with `search_queries` to focus excerpts. |
| `search_queries` | string[] | one of these required | — | 2–3 diverse keyword queries, 3–6 words each |
| `mode` | enum | optional | `basic` | `basic` (1–3s, ~$0.004) or `advanced` (15–70s, ~$0.009, freshness-prioritized). **NOT `processor`** — older docs are wrong. |
| `max_chars_total` | int | optional | — | Cap on total chars across all excerpts |
| `client_model` | string | optional | — | e.g. `claude-opus-4-7` — informs excerpt sizing |
| `session_id` | string | optional | — | Group related calls for analytics |
| `advanced_settings` | object | optional | — | Per-result tuning (see below) |

`advanced_settings` sub-object:

| Sub-field | Type | Notes |
|---|---|---|
| `max_results` | int | Cap on returned results |
| `excerpt_settings.max_chars_per_result` | int | Per-URL excerpt char cap |
| `source_policy` | object | `{include_domains: [...], exclude_domains: [...], after_date: "..."}` |
| `fetch_policy` | object | Cached vs live content |
| `location` | string | ISO 3166-1 alpha-2 country code |

### Response

```json
{
  "search_id": "search_...",
  "session_id": "sess_...",
  "results": [
    {
      "url": "https://...",
      "title": "...",
      "publish_date": "2026-04-12",
      "excerpts": ["long passage 1 ...", "long passage 2 ..."]
    }
  ],
  "warnings": null,
  "usage": [...]
}
```

Citations are implicit: each `result.url` + `excerpts` is the source. No separate `basis` (that's Task-only).

### Examples

```bash
# Quick basic search (mode default)
curl -X POST https://api.parallel.ai/v1/search \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"objective":"Joe Pizza Bleecker hours and menu",
       "search_queries":["Joe Pizza Bleecker hours","Joe Pizza Bleecker menu 2026"],
       "max_chars_total":4000,
       "advanced_settings":{"max_results":5,
                            "excerpt_settings":{"max_chars_per_result":2000}}}'

# Fresh-prioritized advanced mode
curl -X POST https://api.parallel.ai/v1/search \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"objective":"Latest funding rounds and product launches for Anthropic in last 90 days",
       "search_queries":["Anthropic funding 2026","Anthropic Claude release"],
       "mode":"advanced"}'

# Domain-scoped (source_policy lives under advanced_settings)
curl -X POST https://api.parallel.ai/v1/search \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"objective":"United Airlines policies for changing international flights",
       "search_queries":["United change international flight policy"],
       "advanced_settings":{
         "source_policy":{"include_domains":["united.com","transportation.gov"]}}}'
```

## `/v1/tasks/runs`

Structured, citation-bearing research. Use when you need a **JSON object back with per-field sources**, or when the question takes minutes-to-hours of agentic research.

### Create — POST `/v1/tasks/runs`

| Field | Type | Required | Notes |
|---|---|---|---|
| `input` | string \| object | yes | Question (string) or structured entity to enrich (object) |
| `processor` | enum | yes | `lite` ($0.005) / `base` ($0.01) / `core` ($0.025) / `pro` ($0.10) / `ultra` ($0.30) / `ultra2x`/`4x`/`8x` ($0.60–$2.40) |
| `task_spec.output_schema` | object | optional | `{type:"text"}` or `{type:"json", json_schema:{...}}` or `{type:"auto"}` |
| `metadata` | object | optional | KV pairs |
| `enable_events` | bool | optional | Enable SSE event stream |
| `mcp_servers` | array | optional | MCP server configs the task can call |
| `source_policy` | object | optional | `{include_domains: [...], exclude_domains: [...]}` |
| `webhook` | object | optional | `{url, event_types}`. **Required** for `ultra*` |

### Latency / blocking

- `lite`–`pro`: blocking `GET /result` is safe (timeout up to 600s default; SDK supports `api_timeout=3600`).
- `ultra*`: can run up to 2 hours. **Always use webhooks**, never block.

### Result (from `GET /v1/tasks/runs/{run_id}/result`)

```json
{
  "run": {
    "run_id": "run_...",
    "status": "completed",
    "processor": "core",
    "is_active": false,
    "created_at": "...",
    "modified_at": "..."
  },
  "output": {
    "type": "json",
    "content": { /* matches output_schema */ },
    "basis": [
      {
        "field": "ceo_name",
        "citations": [{"title":"...","url":"https://...","excerpts":["..."]}],
        "reasoning": "Confirmed via filings and press release",
        "confidence": "high"
      }
    ]
  }
}
```

`basis[]` is the **per-field citation array** — the killer feature vs Exa.

Status enums: `queued`, `action_required`, `running`, `completed`, `failed`, `cancelling`, `cancelled`.

### Examples

```bash
# Free-form deep research
curl -X POST https://api.parallel.ai/v1/tasks/runs \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"Compare top 3 DTC mattress companies in 2026 by revenue, return policy, NPS.",
       "processor":"core"}'
# returns { run: { run_id, status: "queued" } } — then poll:
curl https://api.parallel.ai/v1/tasks/runs/$RUN_ID/result \
  -H "x-api-key: $PARALLEL_API_KEY"

# Structured with json_schema and per-field citations
curl -X POST https://api.parallel.ai/v1/tasks/runs \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"Restaurant: Le Bernardin, NYC","processor":"base",
       "task_spec":{"output_schema":{"type":"json","json_schema":{
         "type":"object",
         "properties":{
           "head_chef":{"type":"string"},
           "michelin_stars":{"type":"integer"},
           "reservation_url":{"type":"string"},
           "cuisine_type":{"type":"string"},
           "average_dinner_price_usd":{"type":"number"}},
         "required":["head_chef","michelin_stars"]}}}}'

# Ultra task with webhook (script does NOT support this — handle it yourself)
curl -X POST https://api.parallel.ai/v1/tasks/runs \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"Profile every commercial flight route between SFO and NRT in May 2026.",
       "processor":"ultra",
       "webhook":{"url":"https://my.app/parallel-callback",
                  "event_types":["task_run.completed","task_run.failed"]}}'
```

Webhook signature: HMAC-SHA256 of `${webhook_id}.${webhook_timestamp}.${raw_body}` with account secret. Header: `webhook-signature: v1,<base64>`.

## `/v1/extract`

Use after Search narrows results, when you need full clean content of a known URL (handles JS-rendered pages and PDFs).

### Body

| Field | Type | Required | Notes |
|---|---|---|---|
| `urls` | string[] | yes | Up to 20 URLs |
| `objective` | string | optional | Max 5000 chars; biases excerpt selection |
| `search_queries` | string[] | optional | 2–3 recommended, max 5 |
| `max_chars_total` | int | optional | Upper bound on returned chars |
| `client_model` | string | optional | e.g. `claude-opus-4-7` — informs excerpt sizing |
| `session_id` | string | optional | Groups related calls |
| `advanced_settings` | object | optional | `fetch_policy`, excerpt sizing, `full_content` toggle |

```bash
curl -X POST https://api.parallel.ai/v1/extract \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"urls":["https://www.lebernardin.com/menu","https://example.com/wine-list.pdf"],
       "objective":"Tasting menu courses, wine pairings, and prices",
       "client_model":"claude-opus-4-7"}'
```

## `/v1beta/findall/runs`

For discovering **lists of matching entities** (e.g., "all Series-B AI infra companies in EU founded 2023+").

| Generator | Use |
|---|---|
| `preview` | Testing |
| `base` | Broad lists |
| `core` | Specific criteria |
| `pro` | Rare/thorough discovery |

Body: `objective`, `entity_type`, `match_conditions`, `match_limit` (5–1000). Recommended: SSE via `GET /v1beta/findall/runs/{id}/events` rather than polling.

May require `parallel-beta: findall-YYYY-MM-DD` header — check the docs for current value.

## `/chat/completions`

Drop-in OpenAI shape; models `speed` (~3s), `lite`, `base`, `core`. Research models (`lite`/`base`/`core`) include a `basis` field with citations in the response. Default rate limit: **300 RPM**. No multimodal, no prompt caching.

```bash
curl https://api.parallel.ai/chat/completions \
  -H "Authorization: Bearer $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"core",
       "messages":[{"role":"user","content":"Who currently leads the AI safety team at Anthropic?"}]}'
```

## Pricing snapshot (per request)

| API | Tier | Price | Latency |
|---|---|---|---|
| Search | base | $0.004 | 1–3s |
| Search | pro | $0.009 | 15–70s |
| Task | lite | $0.005 | 10–60s |
| Task | base | $0.010 | 15–100s |
| Task | core | $0.025 | 1–5 min |
| Task | pro | $0.100 | ~10 min |
| Task | ultra | $0.300 | up to 2h |
| Task | ultra2x/4x/8x | $0.60 / $1.20 / $2.40 | up to 2h |
| Chat | speed | $0.005 | ~3s |

Free tier: 20k requests across all APIs. Rate limits: not publicly published except Chat (300 RPM).

## Decision matrix (Exa-fallback)

| Scenario | Parallel endpoint | Why over Exa |
|---|---|---|
| Quick fact about an entity | **Search `base`** | LLM-sized excerpts, one call usually enough |
| Fresh / breaking info | **Search `pro`** | Built for freshness |
| Need JSON object **with per-field citations** | **Task `base`/`core`** | Exa has no equivalent (`basis[]`) |
| Multi-source synthesis ("compare 3 X by Y, Z, W") | **Task `core`** | Agentic research |
| Long-horizon investigation (full market scan) | **Task `pro` / `ultra*`** w/ webhook | Minutes-to-hours of compute |
| Specific URLs, JS/PDF heavy | **Extract** | Better than Exa contents |
| List of entities matching criteria | **FindAll (beta)** | Discovery-shaped |
| Continuous monitoring | **Monitor** | Native cron + diff |

Rule of thumb:
1. Try Exa first.
2. If thin/stale → Parallel `Search base` → still poor → `Search pro`.
3. If structured fields with citations → skip Search, go straight to `Task base`/`core`.
4. If multi-source synthesis → `Task core` (text) or `Task pro` (deep).

## SDKs

- Python: `pip install "parallel-web>=0.5.0"` → `from parallel import Parallel; client = Parallel()`
- TypeScript: `npm install parallel-web` → `import Parallel from "parallel-web"`
- Field naming: snake_case in HTTP. Python = snake_case methods, TS = camelCase methods (`task_run.create` vs `taskRun.create`).

## Useful URLs

- Docs index: https://docs.parallel.ai/llms.txt
- Full docs (machine-readable): https://docs.parallel.ai/llms-full.txt
- OpenAPI: https://docs.parallel.ai/public-openapi.json
- Cookbook: https://github.com/parallel-web/parallel-cookbook
- Pricing: https://parallel.ai/pricing
