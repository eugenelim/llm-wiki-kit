# Variants — Comparison

The three variants are configurable instantiations of the same underlying architecture (LLM-Wiki + Active OS + Research Layer + Inventories). They differ in ontology, page types, operations, tone, and which inventories ship by default.

| Dimension | Work | Family | Personal |
|---|---|---|---|
| **Organizing unit** | Projects | People + domains | Notes + projects + career |
| **Knowledge lifecycle** | Discovery → deliver → archive | Ongoing, rarely "done" | Compounding (atomic → synthesized) |
| **Page types** | Design, proposal, spec, ADR, playbook | Medical, recipe, trip, home, financial | Note, topic, book, project, application, review, portfolio |
| **Decision records** | ADRs (formal, immutable) | Not needed | Personal decision log (lightweight) |
| **Research tools** | Perplexity + Gemini + S2 | Perplexity + S2 | Perplexity + S2 (Gemini for major life decisions) |
| **PM integration** | Linear / Jira / Plane | Calendar / task app | Personal task app or none |
| **Non-text files** | Architecture diagrams, approach docs | Medical scans, receipts, manuals | Resume PDFs, portfolio assets, scanned notes |
| **Active operations** | Sprint planning, weekly digest, cross-project synthesis, ADR review, onboarding pack | Meal planning, follow-up tracker, trip prep, weekly digest, recipe recommender | Weekly / quarterly / annual reviews, career narrative refresh, job-search prep, knowledge consolidation, networking digest |
| **Research projects** | Tool eval, architecture decisions, hire shortlists, market analysis | Major purchases, school choice, home location, medical research, home systems | Career decisions, learning paths, major life decisions |
| **Inventories shipped** | Cloud-tool / agentic-stack, SaaS / vendor registry | Restaurants, subscriptions, holdings, tax records, POIs | Advisors, role-tooling, holdings, tax records |
| **Claude tone** | Professional, technical | Friendly, age-appropriate | Reflective, growth-oriented, direct |

For full architectural detail per variant, see the design narratives:
- [Work](design/work.md) — engineering team operating system
- [Family](design/family.md) — household knowledge + active OS
- [Personal](design/personal.md) — solo knowledge + career OS
- [Research layer](design/research-layer.md) — cross-variant pattern for multi-source investigations
