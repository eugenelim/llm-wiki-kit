---
type: index
folder: tooling
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, tooling, inventory]
---

## Synopsis

Tooling inventory — software / tools I use, organized by role (frontend, backend, data, agentic, writing, design, productivity, research). Each entry is a small file with `type: tooling-entry` frontmatter; the live filtered view is `tooling.base`.

## How this folder works

Each tool is a `.md` file with the schema declared by `_templates/tooling-entry.md` (role, cost, how-used, adoption-date, last-evaluated). Add entries by copying the template; browse via `tooling.base`.

## Common access patterns

- "What do I use for {role}?" → filter by role
- "Daily drivers vs. occasional" → filter by how_used
- "What am I currently evaluating?" → filter by status: evaluating
- "Tools I haven't re-evaluated in a year" → sort by last_evaluated

## Related

- [[skill-gap-analysis]] consults this when recommending learning priorities (the tool you don't have surfaces a skill gap)
- [[reading-queue]] sometimes recommends tool-related books / courses
- [[career-narrative-refresh]] reads tooling for "what I'm fluent with" claims
- This complements [[career/skills/]] — skills are *capabilities*; tooling is *what enables them*

## Why a separate inventory

The kit's existing `tool` page-type (work variant) is for *team* tool evaluations. This `tooling-entry` is *personal* — your individual setup, what you'd carry to a new role, what you'd reach for on a side project.
