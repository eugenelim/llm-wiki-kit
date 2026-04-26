---
name: research-start
description: "Phase-1 research operation. Scaffold a NEW research project folder with the 4-pillar structure (entities, attributes, mental-model, verdict), given a central claim and a declared verdict shape (matrix / shortlist / blueprint). Use when the user asks to \"start a research project\" or \"investigate {topic}\" with a claim. BEFORE running the research orchestrator. Refuses to scaffold without a central claim — research without a claim is browsing."
license: MIT
metadata:
  variant: shared
---

# Research Start Skill

Phase-1 entry-point operation for the research layer. Given a central claim and a declared verdict shape, scaffold a research project folder with the 4-pillar structure ready for capture.

## When to Use

- A user asks to "start a research project" with a claim
- The orchestrator detects an active research-flavored question that warrants multi-source investigation
- Before running [[research]] (the orchestrator) — research sources need a project to land in

## Inputs

User provides:

1. **Central claim** — one sentence stating what you expect to be true. **Required.** Without this, the operation refuses to scaffold (research without a claim is browsing).
2. **Verdict shape** — `matrix` | `shortlist` | `blueprint`. **Required.** Declared upfront so capture and sieve know what to optimize for.
3. **Topic / title** — used to derive the slug and the project title.
4. **Variant context** — work or family vault (auto-detected from `_variant/CLAUDE.variant.md`).

Reads:

- `_templates/research-project.md` — for the overview page schema
- `wiki/research/index.md` — for the research index (created if absent)
- `purpose.md` — to scope-check the research effort

## Algorithm

1. **Validate inputs.**
   - Refuse if central claim is missing.
   - Refuse if `verdict_shape` is not one of `matrix`, `shortlist`, `blueprint`.
   - Scope-check against `purpose.md`. If the topic is out-of-scope, surface and ask for confirmation before proceeding.

2. **Derive identifiers.**
   - Slug: kebab-case from the topic (e.g., "AI Code Assistants" → `ai-code-assistants`)
   - Date: today in `YYYY-MM-DD`
   - Folder: `wiki/research/{date}-{slug}/`

3. **Detect duplicates.** If a folder with the same slug already exists, surface and ask whether to *resume* it (set as active project) or use a different slug.

4. **Create the folder structure.**

   ```
   wiki/research/{date}-{slug}/
   ├── overview.md          # From _templates/research-project.md, populated
   ├── entities.md          # Empty pillar page with frontmatter
   ├── attributes.md        # Empty pillar page with frontmatter
   ├── mental-model.md      # Empty pillar page with frontmatter
   ├── verdict.md           # Empty pillar page with frontmatter
   └── sources/
       └── .gitkeep
   ```

   Each pillar page has minimal frontmatter (`type: research-pillar`, `pillar: entities|attributes|mental-model|verdict`, `project: "[[overview]]"`) and a `## Synopsis` section noting the page is empty pending Capture.

5. **Populate `overview.md`.** Substitute `central_claim`, `verdict_shape`, slug, dates into the template. Set:
   - `phase: capture`
   - `verdict_status: open`
   - `verification_count: 0`
   - First entry in `## Phase Log`: `{date}: research-start (phase = capture; central claim defined; verdict_shape = {shape})`

6. **Update `wiki/research/index.md`.** Add an entry for the new project: link, central claim, verdict shape, status. Create the index if absent.

## Output

A confirmation message:

```
Research project scaffolded:
  Path: wiki/research/2026-04-25-ai-code-assistants/
  Central claim: "Claude Code's speed advantages outweigh GPT-4's plugin
    ecosystem for our team's workflow."
  Verdict shape: matrix
  Phase: capture

Next:
  - Capture sources via [[research]] (API providers) or [[ingest-website]] /
    [[ingest-document]] (URLs and files).
  - Run [[research-verdict-check]] periodically to get a stop-signal recommendation.
  - When capture is done: [[research-sieve]] → [[research-synthesize]].
```

## Side-effects

1. **Set the project as active.** The most-recently-modified `overview.md` in `wiki/research/*/` is treated as active by default; explicit override via user prompt.
2. **Update `wiki/research/index.md`** with the new project entry.
3. **Append to `log/changelog.md`**: "Research project started: [[research/{date}-{slug}/overview]]."

## Interactive Confirmation

Always confirm before scaffolding:

```
Proposed research project:

Central claim: {claim}
Verdict shape: {shape}
Folder: wiki/research/{date}-{slug}/
Scope check (against purpose.md): {in-scope | partial | out-of-scope}

Scaffold?
```

The user confirms or adjusts (refines the claim, picks a different shape).

## Failure Modes

- **Central claim missing.** Refuse: "Research requires a central claim — what do you expect to be true? Without it, research is just browsing."
- **Verdict shape ambiguous or invalid.** Refuse: "Pick a verdict shape upfront: `matrix` for vendor / option comparison, `shortlist` for ranked candidates, `blueprint` for spatial / structural arrangement."
- **Out of scope per purpose.md.** Surface and ask for explicit confirmation.
- **Duplicate slug.** Ask whether to resume or use a different slug.

## Cadence

- **On demand:** When the user explicitly starts a research effort.
- **No automation:** Research projects are deliberate; never auto-scaffold from ambient activity.
