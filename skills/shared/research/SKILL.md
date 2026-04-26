---
name: research
description: "Research orchestrator for the Capture phase of an ALREADY-ACTIVE research project. Picks the best provider (Perplexity / Gemini / Semantic Scholar) per question semantics and project pillar gaps, dispatches via scripts/research.py, and saves the result to the project's sources/ folder with research-source schema tagging. Use during the Capture phase, or on request: \"research {query}\" / \"find sources on {topic}\". To start a NEW research project, use research-start FIRST."
license: MIT
compatibility: "Requires Python 3.10+ and at least one provider configured in .claude/research-providers.yaml (Perplexity, Gemini, or Semantic Scholar API keys)."
metadata:
  variant: shared
---

# Research Skill

The research orchestrator. Given a research query (or autonomous invocation after [[research-start]]), the orchestrator picks the best provider(s), dispatches via `scripts/research.py`, and saves the result to the active research project's `sources/` folder with research-source schema tagging.

Provider choice is **LLM-driven**, based on question semantics, the active project's pillar gaps, the verdict shape, and the cost-signal budget across configured providers. The orchestrator reads `.claude/research-providers.yaml` to know what's enabled.

## When to Use

- During the Capture phase of an active research project
- On user request: "Research {query}" / "Find sources on {topic}"
- Autonomously by the agent after [[research-start]] when scoping the initial source pool

## Inputs

User provides:

- A research query (free-text question)
- Optionally: explicit provider preference ("use Perplexity for this") — the orchestrator honors but warns if the question semantics don't match the chosen provider's strengths
- Optionally: project slug — if absent, the orchestrator uses the most-recently-modified research project as active

Reads:

- `.claude/research-providers.yaml` — which providers are enabled, their strengths, cost signals
- The active research project's `overview.md` — central claim, verdict shape, current phase, pillar gaps
- The active project's pillar pages — what's already been captured (avoid redundant queries)

## Provider strategy

The orchestrator picks providers using these signals:

### 1. Question semantics

| Question shape | Preferred provider |
|---|---|
| "Current state of X" / "What's new with X" / "Compare A vs B today" | Perplexity |
| "What's the literature on X" / "Find papers on X" / "Citations for paper Y" | Semantic Scholar |
| "Comprehensive analysis of X" / "Strategic landscape of X" / "30-page synthesis of X" | Gemini Deep Research |
| "Article at URL Z" | Not research; route to [[ingest-website]] instead |

### 2. Project pillar gaps

If the active project's `attributes.md` is sparse, queries for measurable attributes prefer Perplexity (current data) and Semantic Scholar (peer-reviewed benchmarks). If `mental-model.md` is sparse, prefer Semantic Scholar (theoretical / academic frameworks) and Gemini (synthesis of multiple frameworks).

### 3. Verdict shape

- `matrix` — focused comparison queries → Perplexity heavy + Semantic Scholar for benchmarks
- `shortlist` — candidate evaluation queries → Perplexity for current state of each candidate
- `blueprint` — design / ergonomic queries → Semantic Scholar for evidence-based principles + Perplexity for case studies

### 4. Two-Source Rule for load-bearing claims

If the orchestrator detects the user is asking about a load-bearing claim (e.g., "is the verdict still right that X?"), it dispatches to **two providers in parallel** and surfaces both results for cross-corroboration. The resulting source pages each cite their respective provider; together they satisfy the Two-Source Rule for the verification trail.

### 5. Cost signal

`cost_signal: high` providers (Gemini Deep Research) are reserved for:

- Initial scope-setting at research-start
- Strategic-context questions for matrix / blueprint shapes
- Final-synthesis questions during phase: synthesize

Don't burn high-cost calls on routine attribute lookups.

### 6. Provider availability

Read `enabled: true` providers from the YAML config. If only Perplexity is enabled, all queries go there (with a note that Semantic Scholar / Gemini coverage is missing). If no providers are enabled, the orchestrator declines and asks the user to enable at least one in `.claude/research-providers.yaml`.

## Operation

1. **Read the active project's state.** Identify pillar gaps and verdict shape.
2. **Read the YAML config.** Filter to enabled providers; note their strengths and cost signals.
3. **Decide strategy.** Pick one or two providers based on the signals above.
4. **Dispatch via the script:**
   ```bash
   python scripts/research.py \
     --provider {provider} \
     --query {query} \
     --project {slug}
   ```
5. **Receive markdown output** from the script (research-source schema with frontmatter populated, `pillar_contributions:` left empty for human/agent post-fill).
6. **Save** to `wiki/research/{slug}/sources/{provider}-{date}-{query-slug}.md`.
7. **Tag pillar contributions** based on what came back (entities listed → entities; measurable values → attributes; explanations → mental-model; recommendations → verdict).
8. **Append to project overview's phase log:** `{date}: research (provider: {p}; query: {q})`.

## Output

The new source file path is reported to the user. The source page is now part of the project's source pool, ready for [[research-sieve]] when capture is done.

A multi-provider dispatch shows both results side-by-side with a corroboration note:

```
Two-source corroboration for query "Cursor context window 2026":
  Perplexity: 1M tokens (per Cursor changelog 2026-01)
  Semantic Scholar: no relevant peer-reviewed evidence (consumer-product domain)

Verification: single-source effectively (Perplexity citations are vendor-stated).
Saving as research-source with verification_strength: secondary.
```

## Side-effects

1. **Save the source page** at `wiki/research/{slug}/sources/{provider}-{date}-{slug}.md`.
2. **Update project overview** with phase log entry.
3. **Append to `log/changelog.md`**: "Research source captured via {provider}: [[research/{slug}/sources/{...}]]."

## Interactive Review

For a single-provider dispatch, the orchestrator typically just runs and reports. For high-cost providers (Gemini), confirm before dispatching:

```
About to dispatch to Gemini Deep Research:
  Query: "Comprehensive landscape analysis of agentic AI tooling"
  Cost signal: high
  Active project: ai-code-assistants

This is a high-cost call. Proceed?
```

For multi-provider dispatch, mention what's running and why.

## Failure Modes

- **No providers enabled.** Decline: "No research providers enabled in `.claude/research-providers.yaml`. Edit the file to enable at least one (Perplexity or Semantic Scholar work for free / low-cost; Gemini Deep Research for strategic depth)."
- **API call fails.** Retry once on transient errors; if persistent, surface the error and suggest checking the API key or rate limits.
- **No active project.** Ask: "Save as a one-off research brief, or start a new project (run [[research-start]])?"
- **Question is not research-shaped.** If the query is "ingest this URL," route to [[ingest-website]] instead.

## Cadence

- **On demand:** During Capture phase, run as queries arise.
- **No scheduled runs:** Research is deliberate; queries reflect the researcher's open questions.
- **Pairs with [[research-verdict-check]]:** Use verdict-check to know when capture is complete and queries should taper.

## What's next

- More research queries (continue capture)
- [[research-verdict-check]] to gauge progress
- [[research-sieve]] when capture is done
- [[research-synthesize]] to produce the artifact
