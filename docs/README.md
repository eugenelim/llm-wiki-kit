# Documentation

Reference docs for the LLM Wiki Kit. Start with the [README](../README.md) at the repo root for the high-level overview; come here for deeper material.

## Design

Architecture narratives — what each variant is, why it's shaped this way, where it scales and where it doesn't.

- [Work variant](design/work.md) — architecture & engineering team knowledge base. Spec-driven development, ADRs, PM sync, multi-project ontology.
- [Family variant](design/family.md) — household knowledge base + active operating system. Person-first ontology, structured ingestion (recipes, medical records, receipts), and an operations layer (meal planning, follow-up tracking, trip prep).
- [Personal variant](design/personal.md) — solo knowledge & career OS. Zettelkasten-style atomic notes, structured career artifacts (portfolio, applications, resume, narrative), planning rhythm (weekly / quarterly / annual reviews), career-progression operations (narrative refresh, job-search prep, knowledge consolidation).
- [Research layer](design/research-layer.md) — cross-variant pattern for multi-source investigations. 4-pillar ontology (Entities, Attributes, Mental Model, Verdict), 4-phase workflow (Capture, Sieve, Synthesize, Feedback), Two-Source Rule verification, declared verdict shape (matrix / shortlist / blueprint).

## Guides

Operational walkthroughs.

- [Setup](guides/setup.md) — installation, dependencies, customization, the test loop
- [Sync options](guides/sync-options.md) — shared drive vs. Git tradeoffs, when to switch, project isolation
- [File formats](guides/file-formats.md) — format support matrix, companion-page convention, when to use markdown vs. Office
- [Customizing](guides/customizing.md) — building a custom variant beyond `work`, `family`, and `personal`
- [Inventories](guides/inventories.md) — tracking typed entity collections (restaurants, subscriptions, cloud tooling, advisors, etc.) with small-item files + Obsidian Bases for live filtered views
- [Web Clipper](guides/web-clipper.md) — Obsidian Web Clipper setup: recommended `raw/web-clips/` template, fallback `Clippings/` inbox flow, and how the orchestrator handles relocation after processing

## Reference

- [Repo structure](repo-structure.md) — directory layout (top-level + per-vault-template) and naming conventions
- [Variants comparison](comparison.md) — side-by-side of work / family / personal across organizing unit, page types, operations, tone, inventories
