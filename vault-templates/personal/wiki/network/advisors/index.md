---
type: index
folder: advisors
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, advisor, network, inventory]
---

## Synopsis

Mentor / advisor / sponsor inventory. The people you go to for career, technical, leadership, or business questions. Each entry is a small file with `type: advisor` frontmatter; the live filtered view is `advisors.base`.

## How this folder works

Each advisor relationship is a `.md` file with the schema declared by `_templates/advisor.md` (relationship, expertise areas, last_contact, contact_cadence). Add entries by copying the template; browse via `advisors.base`.

## Common access patterns

- "Who could help me think through {topic}?" → filter by expertise_areas
- "Who haven't I talked to in 3+ months?" → sort by last_contact (ascending)
- "Active mentorship vs. occasional advisory" → filter by relationship
- "What's the implicit contract with each?" → review the cadence + What-they-help-with sections

## Related

- This complements `wiki/network/relationships/` (general contacts). Advisors are a curated subset — relationships where you've made a deliberate ask for guidance
- [[networking-digest]] reads `last_contact` to surface stale advisor relationships
- [[career-narrative-refresh]] consults advisor pages for "who shaped my thinking on X"
- [[skill-gap-analysis]] suggests reaching out to advisors when surfacing skill priorities
