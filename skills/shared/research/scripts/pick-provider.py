#!/usr/bin/env python3
"""
pick-provider.py — Deterministic research provider selection.

Implements the 6-signal provider selection algorithm from research/SKILL.md
as a lookup table. Replaces LLM re-evaluation of the same decision tree on
every research call.

Setup:
  pip install pyyaml

Usage:
  python pick-provider.py \\
    --question-type current-state \\
    --verdict-shape matrix \\
    --pillar-gaps attributes,mental-model \\
    --load-bearing false

  python pick-provider.py --question-type literature --config .claude/research-providers.yaml

Output:
  One line: the selected provider name(s), comma-separated if two-source.
  Exit code 1 if no providers are enabled.
"""

import argparse
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("Error: pyyaml required. Run: pip install pyyaml")


CONFIG_PATH = ".claude/research-providers.yaml"

# Provider cost signals (overridden by YAML config if present)
DEFAULT_COST = {
    "perplexity": "medium",
    "semantic_scholar": "low",
    "gemini": "high",
}

# question-type → ranked provider preference
QUESTION_TYPE_RANKING = {
    "current-state": ["perplexity", "semantic_scholar", "gemini"],
    "literature":    ["semantic_scholar", "perplexity", "gemini"],
    "synthesis":     ["gemini", "semantic_scholar", "perplexity"],
    "ingest-url":    [],  # not a research call
}

# verdict-shape → provider weights (higher = more preferred)
VERDICT_SHAPE_WEIGHTS = {
    "matrix":    {"perplexity": 2, "semantic_scholar": 1, "gemini": 0},
    "shortlist": {"perplexity": 2, "semantic_scholar": 0, "gemini": 0},
    "blueprint": {"semantic_scholar": 2, "perplexity": 1, "gemini": 0},
    None:        {"perplexity": 1, "semantic_scholar": 1, "gemini": 1},
}

# pillar-gap → additional provider boost
PILLAR_GAP_BOOST = {
    "attributes":    {"perplexity": 1, "semantic_scholar": 1},
    "mental-model":  {"semantic_scholar": 1, "gemini": 1},
    "entities":      {"perplexity": 1},
    "verdict":       {"gemini": 1, "perplexity": 1},
}


def load_enabled_providers(config_path):
    """Return {name: config} for enabled providers. Empty dict if config missing."""
    if not os.path.exists(config_path):
        return {}
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    providers = config.get("research_providers", {})
    return {k: v for k, v in providers.items() if v.get("enabled", False)}


def score_providers(enabled, question_type, verdict_shape, pillar_gaps, load_bearing):
    """Return {provider: score} for enabled providers."""
    scores = {p: 0 for p in enabled}

    # 1. Question type ranking (primary signal)
    ranking = QUESTION_TYPE_RANKING.get(question_type, [])
    for i, provider in enumerate(ranking):
        if provider in scores:
            scores[provider] += (len(ranking) - i) * 3

    # 2. Verdict shape weights
    shape_weights = VERDICT_SHAPE_WEIGHTS.get(verdict_shape, VERDICT_SHAPE_WEIGHTS[None])
    for provider, weight in shape_weights.items():
        if provider in scores:
            scores[provider] += weight

    # 3. Pillar gap boosts
    for gap in (pillar_gaps or []):
        boosts = PILLAR_GAP_BOOST.get(gap, {})
        for provider, boost in boosts.items():
            if provider in scores:
                scores[provider] += boost

    # 4. Cost signal: penalize high-cost providers unless load_bearing or synthesis
    for provider, cfg in enabled.items():
        cost = cfg.get("cost_signal", DEFAULT_COST.get(provider, "medium"))
        if cost == "high" and not load_bearing and question_type != "synthesis":
            scores[provider] -= 5

    return scores


def pick(scores, load_bearing):
    """Return list of selected providers (1 or 2 for load-bearing)."""
    ranked = sorted(scores.keys(), key=lambda p: -scores[p])
    if not ranked:
        return []
    if load_bearing and len(ranked) >= 2:
        return ranked[:2]
    return [ranked[0]]


def main():
    parser = argparse.ArgumentParser(
        description="Select the best research provider(s) for a given query context."
    )
    parser.add_argument(
        "--question-type",
        choices=["current-state", "literature", "synthesis", "ingest-url"],
        default="current-state",
        help="Semantic shape of the research question (default: current-state)",
    )
    parser.add_argument(
        "--verdict-shape",
        choices=["matrix", "shortlist", "blueprint"],
        default=None,
        help="Active project verdict shape",
    )
    parser.add_argument(
        "--pillar-gaps",
        default="",
        help="Comma-separated pillar gaps: entities,attributes,mental-model,verdict",
    )
    parser.add_argument(
        "--load-bearing",
        choices=["true", "false"],
        default="false",
        help="True if the query targets a load-bearing claim (triggers two-source dispatch)",
    )
    parser.add_argument(
        "--config",
        default=CONFIG_PATH,
        help=f"Path to research-providers.yaml (default: {CONFIG_PATH})",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print scoring breakdown to stderr",
    )
    args = parser.parse_args()

    if args.question_type == "ingest-url":
        print("ingest-url: route to ingest-website skill, not research", file=sys.stderr)
        sys.exit(1)

    enabled = load_enabled_providers(args.config)
    if not enabled:
        print(
            f"Error: no providers enabled in {args.config}.\n"
            "Set enabled: true for at least one provider.",
            file=sys.stderr,
        )
        sys.exit(1)

    pillar_gaps = [g.strip() for g in args.pillar_gaps.split(",") if g.strip()]
    load_bearing = args.load_bearing == "true"

    scores = score_providers(enabled, args.question_type, args.verdict_shape, pillar_gaps, load_bearing)

    if args.explain:
        print("Scores:", file=sys.stderr)
        for p, s in sorted(scores.items(), key=lambda x: -x[1]):
            print(f"  {p}: {s}", file=sys.stderr)

    selected = pick(scores, load_bearing)
    if not selected:
        print("Error: no provider could be selected", file=sys.stderr)
        sys.exit(1)

    print(",".join(selected))


if __name__ == "__main__":
    main()
