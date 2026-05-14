#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
deep-research: web research via Exa (primary) and Parallel (fallback).

Subcommands:
  search     Exa /search                   — find & retrieve pages (most common)
  answer     Exa /answer                   — direct answer + citations
  contents   Exa /contents                 — extract clean text from URLs
  similar    Exa /findSimilar              — "more like this URL"
  task       Exa /research/v0/tasks        — async multi-step research
  p-search   Parallel /v1/search           — fallback search (fresh, deep excerpts)
  p-task     Parallel /v1/tasks/runs       — structured output w/ per-field citations
  p-extract  Parallel /v1/extract          — clean URL extraction (handles JS/PDF)
  p-chat     Parallel /chat/completions    — OpenAI-compatible chat with citations

Required env: EXA_API_KEY for Exa commands, PARALLEL_API_KEY for `p-*` commands.

Output is JSON to stdout. Pipe to `jq` for filtering. Use `--pretty` for indented JSON.
"""

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

EXA_BASE = "https://api.exa.ai"
PARALLEL_BASE = "https://api.parallel.ai"
DEFAULT_TIMEOUT = 180  # seconds; deep research can be slow
USER_AGENT = "deep-research-skill/1.0 (+claude-code)"


def _key(env: str) -> str:
    val = os.environ.get(env, "").strip()
    if not val:
        sys.stderr.write(f"error: ${env} is not set\n")
        sys.exit(2)
    return val


def _http(method: str, url: str, key: str, body: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> Any:
    headers = {
        "x-api-key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if not raw:
                return {}
            return json.loads(raw)
    except urlerror.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        sys.stderr.write(f"HTTP {e.code} {e.reason} for {method} {url}\n{err_body}\n")
        sys.exit(1)
    except urlerror.URLError as e:
        sys.stderr.write(f"network error: {e.reason}\n")
        sys.exit(1)


def _emit(obj: Any, pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(obj, ensure_ascii=False))


def _load_schema(path: str | None) -> dict | None:
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_contents(text: bool, highlights: bool, summary: str | None,
                    max_chars: int | None, livecrawl_hours: int | None) -> dict | None:
    contents: dict[str, Any] = {}
    if text:
        if max_chars is not None:
            contents["text"] = {"maxCharacters": max_chars}
        else:
            contents["text"] = True
    if highlights:
        contents["highlights"] = True
    if summary:
        contents["summary"] = {"query": summary}
    if livecrawl_hours is not None:
        contents["maxAgeHours"] = livecrawl_hours
    return contents or None


# ---------------- Exa commands ----------------

def cmd_search(args: argparse.Namespace) -> None:
    key = _key("EXA_API_KEY")
    body: dict[str, Any] = {"query": args.query, "numResults": args.num}
    if args.type:
        body["type"] = args.type
    if args.category:
        body["category"] = args.category
    if args.include_domains:
        body["includeDomains"] = args.include_domains
    if args.exclude_domains:
        body["excludeDomains"] = args.exclude_domains
    if args.start_date:
        body["startPublishedDate"] = args.start_date
    if args.end_date:
        body["endPublishedDate"] = args.end_date
    if args.country:
        body["userLocation"] = args.country
    contents = _build_contents(args.text, args.highlights, args.summary,
                               args.max_chars, args.livecrawl_hours)
    if contents:
        body["contents"] = contents
    schema = _load_schema(args.schema)
    if schema:
        body["outputSchema"] = schema
    if args.system_prompt:
        body["systemPrompt"] = args.system_prompt
    if args.additional_queries:
        body["additionalQueries"] = args.additional_queries
    _emit(_http("POST", f"{EXA_BASE}/search", key, body), args.pretty)


def cmd_answer(args: argparse.Namespace) -> None:
    key = _key("EXA_API_KEY")
    body: dict[str, Any] = {"query": args.query}
    if args.text:
        body["text"] = True
    schema = _load_schema(args.schema)
    if schema:
        body["outputSchema"] = schema
    _emit(_http("POST", f"{EXA_BASE}/answer", key, body), args.pretty)


def cmd_contents(args: argparse.Namespace) -> None:
    key = _key("EXA_API_KEY")
    body: dict[str, Any] = {"urls": args.urls}
    contents = _build_contents(args.text, args.highlights, args.summary,
                               args.max_chars, args.livecrawl_hours)
    if contents:
        body.update(contents)
    if args.subpages:
        body["subpages"] = args.subpages
    if args.subpage_target:
        body["subpageTarget"] = args.subpage_target
    _emit(_http("POST", f"{EXA_BASE}/contents", key, body), args.pretty)


def cmd_similar(args: argparse.Namespace) -> None:
    key = _key("EXA_API_KEY")
    body: dict[str, Any] = {"url": args.url, "numResults": args.num}
    if args.exclude_source_domain:
        body["excludeSourceDomain"] = True
    if args.category:
        body["category"] = args.category
    contents = _build_contents(args.text, args.highlights, args.summary,
                               args.max_chars, args.livecrawl_hours)
    if contents:
        body["contents"] = contents
    _emit(_http("POST", f"{EXA_BASE}/findSimilar", key, body), args.pretty)


def cmd_task(args: argparse.Namespace) -> None:
    """Exa /research/v0/tasks — create + (optionally) poll until done."""
    key = _key("EXA_API_KEY")
    body: dict[str, Any] = {"instructions": args.instructions, "model": args.model}
    schema = _load_schema(args.schema)
    if schema:
        body["output"] = {"schema": schema}
    elif args.infer_schema:
        body["output"] = {"inferSchema": True}
    create = _http("POST", f"{EXA_BASE}/research/v0/tasks", key, body)
    # Exa returns `id`; older docs say `researchId`. Accept either.
    research_id = create.get("id") or create.get("researchId")
    if not research_id or not args.wait:
        _emit(create, args.pretty)
        return
    deadline = time.time() + args.wait_timeout
    last_status = ""
    while time.time() < deadline:
        time.sleep(args.poll_interval)
        result = _http("GET", f"{EXA_BASE}/research/v0/tasks/{research_id}", key)
        status = result.get("status", "")
        if status != last_status:
            sys.stderr.write(f"[exa-task {research_id}] status={status}\n")
            last_status = status
        if status in ("completed", "failed", "canceled"):
            _emit(result, args.pretty)
            return
    sys.stderr.write(f"timeout after {args.wait_timeout}s; task still running. id={research_id}\n")
    sys.exit(3)


# ---------------- Parallel commands ----------------

def cmd_p_search(args: argparse.Namespace) -> None:
    key = _key("PARALLEL_API_KEY")
    body: dict[str, Any] = {}
    if args.objective:
        body["objective"] = args.objective
    if args.queries:
        body["search_queries"] = args.queries
    if not body:
        sys.stderr.write("error: provide --objective and/or --queries\n")
        sys.exit(2)
    body["mode"] = args.mode
    if args.max_chars_total is not None:
        body["max_chars_total"] = args.max_chars_total
    advanced: dict[str, Any] = {}
    if args.num is not None:
        advanced["max_results"] = args.num
    if args.max_chars_per_result is not None:
        advanced["excerpt_settings"] = {"max_chars_per_result": args.max_chars_per_result}
    if args.include_domains or args.exclude_domains:
        sp: dict[str, Any] = {}
        if args.include_domains:
            sp["include_domains"] = args.include_domains
        if args.exclude_domains:
            sp["exclude_domains"] = args.exclude_domains
        advanced["source_policy"] = sp
    if advanced:
        body["advanced_settings"] = advanced
    _emit(_http("POST", f"{PARALLEL_BASE}/v1/search", key, body), args.pretty)


def cmd_p_task(args: argparse.Namespace) -> None:
    """Parallel /v1/tasks/runs — create + poll for `lite`..`pro`. ultra* requires webhooks (not supported here)."""
    key = _key("PARALLEL_API_KEY")
    if args.processor.startswith("ultra"):
        sys.stderr.write("error: ultra* processors require webhook delivery; not supported in CLI mode. "
                         "Use processor lite|base|core|pro.\n")
        sys.exit(2)
    body: dict[str, Any] = {"input": args.input, "processor": args.processor}
    schema = _load_schema(args.schema)
    if schema:
        body["task_spec"] = {"output_schema": {"type": "json", "json_schema": schema}}
    elif args.text_output:
        body["task_spec"] = {"output_schema": {"type": "text"}}
    if args.include_domains or args.exclude_domains:
        sp: dict[str, Any] = {}
        if args.include_domains:
            sp["include_domains"] = args.include_domains
        if args.exclude_domains:
            sp["exclude_domains"] = args.exclude_domains
        body["source_policy"] = sp
    create = _http("POST", f"{PARALLEL_BASE}/v1/tasks/runs", key, body)
    run_id = (create.get("run") or {}).get("run_id") or create.get("run_id")
    if not run_id or not args.wait:
        _emit(create, args.pretty)
        return
    deadline = time.time() + args.wait_timeout
    last_status = ""
    while time.time() < deadline:
        time.sleep(args.poll_interval)
        status_resp = _http("GET", f"{PARALLEL_BASE}/v1/tasks/runs/{run_id}", key)
        run_obj = status_resp.get("run") or status_resp
        status = run_obj.get("status", "")
        if status != last_status:
            sys.stderr.write(f"[parallel-task {run_id}] status={status}\n")
            last_status = status
        if status in ("completed", "failed", "cancelled"):
            result = _http("GET", f"{PARALLEL_BASE}/v1/tasks/runs/{run_id}/result", key)
            _emit(result, args.pretty)
            return
    sys.stderr.write(f"timeout after {args.wait_timeout}s; run still active. run_id={run_id}\n")
    sys.exit(3)


def cmd_p_extract(args: argparse.Namespace) -> None:
    key = _key("PARALLEL_API_KEY")
    body: dict[str, Any] = {"urls": args.urls}
    if args.objective:
        body["objective"] = args.objective
    if args.queries:
        body["search_queries"] = args.queries
    if args.max_chars is not None:
        body["max_chars_total"] = args.max_chars
    if args.client_model:
        body["client_model"] = args.client_model
    _emit(_http("POST", f"{PARALLEL_BASE}/v1/extract", key, body), args.pretty)


def cmd_p_chat(args: argparse.Namespace) -> None:
    key = _key("PARALLEL_API_KEY")
    body: dict[str, Any] = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
    }
    if args.system:
        body["messages"].insert(0, {"role": "system", "content": args.system})
    _emit(_http("POST", f"{PARALLEL_BASE}/chat/completions", key, body), args.pretty)


# ---------------- argparse wiring ----------------

def _add_common_io(p: argparse.ArgumentParser) -> None:
    p.add_argument("--pretty", action="store_true", help="Indent JSON output")


def _add_contents_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--text", action="store_true",
                   help="Include full extracted page text. Verbose — prefer --highlights or --summary for agent loops.")
    p.add_argument("--highlights", action="store_true",
                   help="Include 3-5 most-relevant sentences per result. Token-efficient; the recommended default for agent extraction.")
    p.add_argument("--summary", help="LLM-generated short summary per result; arg is the summary query (e.g., 'What does this company do?').")
    p.add_argument("--max-chars", type=int,
                   help="Cap text length per page when --text is set (only used with --text).")
    p.add_argument("--livecrawl-hours", type=int, dest="livecrawl_hours",
                   help="0 = always live, -1 = never live, N = cache if newer than N hours")


def _add_domain_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument("--include-domains", nargs="+", dest="include_domains")
    p.add_argument("--exclude-domains", nargs="+", dest="exclude_domains")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research.py",
        description="Web research via Exa (primary) + Parallel (fallback).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # exa search
    p = sub.add_parser("search", help="Exa /search — find pages")
    p.add_argument("query")
    p.add_argument("--num", type=int, default=10, help="Max results (1–100; >25 wasteful)")
    p.add_argument("--type", choices=["auto", "neural", "keyword", "fast", "deep", "deep-reasoning", "instant"])
    p.add_argument("--category",
                   choices=["company", "research paper", "news", "pdf", "github",
                            "personal site", "people", "financial report"])
    p.add_argument("--start-date", help="ISO 8601 (incompatible with category=company|people)")
    p.add_argument("--end-date")
    p.add_argument("--country", help="Two-letter ISO country code, e.g. US")
    p.add_argument("--system-prompt", help="Used by deep / deep-reasoning")
    p.add_argument("--additional-queries", nargs="+", help="deep / deep-reasoning only")
    p.add_argument("--schema", help="Path to JSON Schema file (deep search structured output)")
    _add_contents_args(p)
    _add_domain_filters(p)
    _add_common_io(p)
    p.set_defaults(func=cmd_search)

    # exa answer
    p = sub.add_parser("answer", help="Exa /answer — direct answer + citations")
    p.add_argument("query")
    p.add_argument("--text", action="store_true", help="Include full text in citations")
    p.add_argument("--schema", help="JSON Schema file for structured answer")
    _add_common_io(p)
    p.set_defaults(func=cmd_answer)

    # exa contents
    p = sub.add_parser("contents", help="Exa /contents — extract from URLs")
    p.add_argument("urls", nargs="+")
    p.add_argument("--subpages", type=int, help="Crawl N linked subpages per URL")
    p.add_argument("--subpage-target", help="Keyword(s) for subpages (e.g. 'references')")
    _add_contents_args(p)
    _add_common_io(p)
    p.set_defaults(func=cmd_contents)

    # exa findSimilar
    p = sub.add_parser("similar", help="Exa /findSimilar — semantic neighbors of a URL")
    p.add_argument("url")
    p.add_argument("--num", type=int, default=10)
    p.add_argument("--exclude-source-domain", action="store_true")
    p.add_argument("--category",
                   choices=["company", "research paper", "news", "pdf", "github",
                            "personal site", "people", "financial report"])
    _add_contents_args(p)
    _add_common_io(p)
    p.set_defaults(func=cmd_similar)

    # exa research task
    p = sub.add_parser("task", help="Exa /research/v0/tasks — async deep research")
    p.add_argument("instructions", help="Up to 4096 chars")
    p.add_argument("--model", default="exa-research",
                   choices=["exa-research", "exa-research-pro"])
    p.add_argument("--schema", help="JSON Schema file for structured output")
    p.add_argument("--infer-schema", action="store_true",
                   help="Have Exa infer an output schema (when --schema not given)")
    p.add_argument("--wait", action="store_true", help="Poll until completed")
    p.add_argument("--poll-interval", type=float, default=5.0)
    p.add_argument("--wait-timeout", type=int, default=600,
                   help="Max seconds to wait when --wait (default 600)")
    _add_common_io(p)
    p.set_defaults(func=cmd_task)

    # parallel search
    p = sub.add_parser("p-search", help="Parallel /v1/search — fallback search w/ long excerpts")
    p.add_argument("--objective", help="Natural-language research goal (max ~5000 chars). Used together with --queries to focus excerpts.")
    p.add_argument("--queries", nargs="+",
                   help="2–3 short diverse keyword queries (3–6 words each). At least one is required if --objective is omitted.")
    p.add_argument("--mode", default="basic", choices=["basic", "advanced"],
                   help="basic = lowest latency, best with 2-3 high-quality queries (~$0.004). "
                        "advanced = freshness-prioritized, deeper excerpts (~$0.009).")
    p.add_argument("--num", type=int, dest="num",
                   help="max_results cap (lives under advanced_settings).")
    p.add_argument("--max-chars-total", type=int, dest="max_chars_total",
                   help="Cap total characters across excerpts from all results (top-level field).")
    p.add_argument("--max-chars-per-result", type=int, dest="max_chars_per_result",
                   help="Cap chars per result (lives under advanced_settings.excerpt_settings).")
    _add_domain_filters(p)
    _add_common_io(p)
    p.set_defaults(func=cmd_p_search)

    # parallel task
    p = sub.add_parser("p-task", help="Parallel /v1/tasks/runs — structured research w/ per-field citations")
    p.add_argument("input", help="Question (str) or JSON-encoded entity (string)")
    p.add_argument("--processor", default="base",
                   choices=["lite", "base", "core", "pro"],
                   help="lite=$0.005, base=$0.01, core=$0.025, pro=$0.10. ultra* needs webhooks (not supported in CLI).")
    p.add_argument("--schema", help="JSON Schema file for structured (json) output")
    p.add_argument("--text-output", action="store_true",
                   help="Force text output_schema (default lets the model pick)")
    p.add_argument("--wait", action="store_true", help="Poll until completed")
    p.add_argument("--poll-interval", type=float, default=8.0)
    p.add_argument("--wait-timeout", type=int, default=900,
                   help="Max seconds to wait when --wait (default 900)")
    _add_domain_filters(p)
    _add_common_io(p)
    p.set_defaults(func=cmd_p_task)

    # parallel extract
    p = sub.add_parser("p-extract", help="Parallel /v1/extract — clean extraction (handles JS/PDF)")
    p.add_argument("urls", nargs="+", help="Up to 20 URLs")
    p.add_argument("--objective", help="Biases excerpt selection")
    p.add_argument("--queries", nargs="+")
    p.add_argument("--max-chars", type=int, help="max_chars_total")
    p.add_argument("--client-model", help="e.g. claude-opus-4-7 — informs excerpt sizing")
    _add_common_io(p)
    p.set_defaults(func=cmd_p_extract)

    # parallel chat
    p = sub.add_parser("p-chat", help="Parallel /chat/completions — OpenAI-compat (`base`/`core` include citations)")
    p.add_argument("prompt")
    p.add_argument("--model", default="core", choices=["speed", "lite", "base", "core"])
    p.add_argument("--system", help="System message")
    _add_common_io(p)
    p.set_defaults(func=cmd_p_chat)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
