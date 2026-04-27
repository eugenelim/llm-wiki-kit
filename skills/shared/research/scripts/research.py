#!/usr/bin/env python3
"""
research.py — Dispatch research queries to configured providers.

Reads `.claude/research-providers.yaml` (relative to the current working dir,
typically the vault root) to find provider settings, then makes the API call
and returns markdown with research-source frontmatter.

Setup:
  pip install pyyaml requests

Usage:
  python research.py --provider perplexity --query "Cursor context window 2026"
  python research.py --provider semantic_scholar --query "context-window utilization in code LLMs" --top 10
  python research.py --provider gemini --query "landscape of agentic AI tooling 2026"

Output:
  Markdown to stdout with research-source frontmatter populated. Pipe to a file:
    python research.py --provider perplexity --query "..." \\
      > wiki/research/{slug}/sources/perplexity-{date}-{slug}.md
"""

import argparse
import os
import re
import sys
from datetime import date

try:
    import yaml
except ImportError:
    sys.exit("Error: pyyaml required. Run: pip install pyyaml")

try:
    import requests
except ImportError:
    sys.exit("Error: requests required. Run: pip install requests")


CONFIG_PATH = ".claude/research-providers.yaml"


def load_config(config_path: str = CONFIG_PATH) -> dict:
    """Load research-providers.yaml from the current vault root."""
    if not os.path.exists(config_path):
        sys.exit(
            f"Error: {config_path} not found. Run from the vault root.\n"
            f"Expected: <vault>/.claude/research-providers.yaml"
        )
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    return config.get("research_providers", {})


def get_api_key(provider_config: dict, required: bool = True) -> str:
    """Get API key from the env var named in provider config."""
    env_var = provider_config.get("api_key_env", "")
    if not env_var:
        return ""
    key = os.environ.get(env_var, "")
    if not key and required:
        sys.exit(
            f"Error: env var {env_var} not set. "
            f"Set it before running: export {env_var}=..."
        )
    return key


def slugify(text: str, max_length: int = 50) -> str:
    """Make a kebab-case slug from text."""
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s[:max_length] or "untitled"


# -----------------------------------------------------------------------------
# Provider dispatchers
# -----------------------------------------------------------------------------


def dispatch_perplexity(query: str, config: dict) -> dict:
    """Call Perplexity Sonar API. Returns parsed result."""
    api_key = get_api_key(config)
    endpoint = config.get("endpoint", "https://api.perplexity.ai/chat/completions")
    model = config.get("model", "sonar-pro")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "return_citations": True,
    }

    print(f"Dispatching to Perplexity ({model})...", file=sys.stderr)
    response = requests.post(endpoint, headers=headers, json=body, timeout=60)
    response.raise_for_status()
    data = response.json()

    answer = data["choices"][0]["message"]["content"]
    # Citations may live at top level or inside the message depending on tier
    citations = data.get("citations") or data["choices"][0].get("citations") or []

    return {
        "provider": "perplexity",
        "model": model,
        "query": query,
        "answer": answer,
        "citations": citations,
        "verification_strength": "secondary",
    }


def dispatch_semantic_scholar(query: str, config: dict, top: int = 10) -> dict:
    """Call Semantic Scholar paper search API. Returns parsed result."""
    # API key is optional but raises rate limits significantly
    api_key = get_api_key(config, required=False)
    endpoint = config.get(
        "endpoint", "https://api.semanticscholar.org/graph/v1"
    ).rstrip("/")
    url = f"{endpoint}/paper/search"

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "limit": top,
        "fields": "paperId,title,abstract,authors,year,venue,citationCount,openAccessPdf",
    }

    print("Dispatching to Semantic Scholar...", file=sys.stderr)
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    return {
        "provider": "semantic_scholar",
        "query": query,
        "papers": data.get("data", []),
        "total": data.get("total", 0),
        "verification_strength": "primary",
    }


def dispatch_gemini(query: str, config: dict) -> dict:
    """Call Gemini API for long-form synthesis."""
    api_key = get_api_key(config)
    model = config.get("model", "gemini-2.5-pro")
    endpoint = config.get(
        "endpoint", "https://generativelanguage.googleapis.com/v1beta/models"
    ).rstrip("/")
    url = f"{endpoint}/{model}:generateContent?key={api_key}"

    prompt = (
        "Provide a comprehensive research synthesis on the following query, "
        "covering current state, key players, primary tensions, and emerging "
        "directions. Cite sources where possible.\n\n"
        f"Query: {query}"
    )

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.4},
    }

    print(f"Dispatching to Gemini ({model})... this may take a while.", file=sys.stderr)
    response = requests.post(url, json=body, timeout=300)
    response.raise_for_status()
    data = response.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return {
        "provider": "gemini",
        "model": model,
        "query": query,
        "answer": text,
        "verification_strength": "secondary",
    }


# -----------------------------------------------------------------------------
# Markdown emitters
# -----------------------------------------------------------------------------


def yaml_list(items: list) -> str:
    """Format a list as inline-or-block YAML."""
    if not items:
        return "  []"
    return "\n".join(f"  - {x}" for x in items)


def emit_perplexity_markdown(result: dict, project: str) -> str:
    today = date.today().isoformat()
    citations = result["citations"]

    return f"""---
title: "Perplexity: {result['query']}"
type: research-source
status: current
provenance: extracted
created: {today}
modified: {today}
tags: [research-source, perplexity]
project: "[[research/{project}/overview]]"
source_url: ""
source_kind: web
fetched_via: perplexity
fetched_at: {today}
pillar_contributions: []
verification_strength: {result['verification_strength']}
citations:
{yaml_list(citations)}
published_at: ""
events_described: ""
---

## Synopsis

{{One sentence: what this query contributed to the project. Fill in after review.}}

## Provenance

- **Provider:** Perplexity ({result.get('model', 'sonar-pro')})
- **Query:** {result['query']}
- **Fetched:** {today}

## Answer

{result['answer']}

## Citations

""" + (
        "\n".join(f"- {c}" for c in citations) if citations else "(none returned)"
    ) + """

## Adversarial Read

- {What's missing or biased?}
- {Counter-source needed: ...}

## Chronology

- **Source published:** {date — typically the cited articles' publication}
- **Events described:** {}
- **Currency:** {still valid? superseded?}
"""


def emit_semantic_scholar_markdown(result: dict, project: str) -> str:
    today = date.today().isoformat()
    papers = result["papers"]
    citations = []
    paper_blocks = []
    for p in papers:
        authors_full = p.get("authors", []) or []
        authors = ", ".join((a.get("name") or "") for a in authors_full[:3])
        if len(authors_full) > 3:
            authors += " et al."
        year = p.get("year", "?")
        venue = p.get("venue", "") or ""
        title = p.get("title", "Untitled")
        abstract = p.get("abstract") or "(abstract not available)"
        cites = p.get("citationCount", 0)
        pid = p.get("paperId", "")
        if pid:
            citations.append(pid)
        paper_blocks.append(
            f"### {title} ({year})\n\n"
            f"**Authors:** {authors}  \n"
            f"**Venue:** {venue}  \n"
            f"**Cited by:** {cites}  \n"
            f"**Paper ID:** `{pid}`\n\n"
            f"**Abstract:** {abstract}\n"
        )

    papers_md = "\n\n".join(paper_blocks) if paper_blocks else "(no papers returned)"

    return f"""---
title: "Semantic Scholar: {result['query']}"
type: research-source
status: current
provenance: extracted
created: {today}
modified: {today}
tags: [research-source, semantic-scholar]
project: "[[research/{project}/overview]]"
source_url: ""
source_kind: paper
fetched_via: semantic-scholar
fetched_at: {today}
pillar_contributions: []
verification_strength: {result['verification_strength']}
citations:
{yaml_list(citations)}
published_at: ""
events_described: ""
---

## Synopsis

{{One sentence: what this query contributed to the project. Fill in after review.}}

## Provenance

- **Provider:** Semantic Scholar
- **Query:** {result['query']}
- **Total results:** {result['total']}
- **Fetched:** {today}

## Papers

{papers_md}

## Adversarial Read

- {{What's missing? Are key seminal papers absent?}}
- {{Field shifts since these papers' publication?}}

## Chronology

- **Papers span:** {{year range}}
- **Currency:** {{methodology shifts? still-current vs. superseded?}}
"""


def emit_gemini_markdown(result: dict, project: str) -> str:
    today = date.today().isoformat()
    return f"""---
title: "Gemini: {result['query']}"
type: research-source
status: current
provenance: synthesized
created: {today}
modified: {today}
tags: [research-source, gemini, deep-research]
project: "[[research/{project}/overview]]"
source_url: ""
source_kind: report
fetched_via: gemini
fetched_at: {today}
pillar_contributions: []
verification_strength: {result['verification_strength']}
citations: []
published_at: ""
events_described: ""
---

## Synopsis

{{One sentence: what this synthesis contributed to the project. Fill in after review.}}

## Provenance

- **Provider:** Gemini ({result.get('model', 'gemini-2.5-pro')})
- **Query:** {result['query']}
- **Fetched:** {today}

## Synthesis

{result['answer']}

## Adversarial Read

- {{Where might Gemini have synthesized claims it didn't actually find?}}
- {{What primary sources should corroborate the load-bearing claims?}}

## Chronology

- **Synthesis snapshot:** {today}
- **Underlying sources span:** {{verify by spot-checking citations}}
"""


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dispatch research queries to configured providers."
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=["perplexity", "semantic_scholar", "gemini"],
        help="Which provider to dispatch to",
    )
    parser.add_argument("--query", required=True, help="Research query")
    parser.add_argument(
        "--project",
        default="TBD",
        help="Active research project slug (for cross-linking; optional)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of results (Semantic Scholar; default 10)",
    )
    parser.add_argument(
        "--config",
        default=CONFIG_PATH,
        help=f"Path to research-providers.yaml (default: {CONFIG_PATH})",
    )
    args = parser.parse_args()

    providers = load_config(args.config)
    provider_config = providers.get(args.provider, {})

    if not provider_config.get("enabled", False):
        sys.exit(
            f"Error: provider '{args.provider}' is not enabled in {args.config}.\n"
            f"Set enabled: true and ensure the API key env var is set."
        )

    if args.provider == "perplexity":
        result = dispatch_perplexity(args.query, provider_config)
        markdown = emit_perplexity_markdown(result, args.project)
    elif args.provider == "semantic_scholar":
        result = dispatch_semantic_scholar(args.query, provider_config, top=args.top)
        markdown = emit_semantic_scholar_markdown(result, args.project)
    elif args.provider == "gemini":
        result = dispatch_gemini(args.query, provider_config)
        markdown = emit_gemini_markdown(result, args.project)
    else:
        sys.exit(f"Unknown provider: {args.provider}")

    print(markdown)


if __name__ == "__main__":
    main()
