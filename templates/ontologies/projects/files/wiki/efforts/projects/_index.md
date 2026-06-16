---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# Projects — map of content

Hub-mode containers: one page per project under `efforts/projects/`.
Member pages (decisions, updates) live in `library/` and join by
`parent:`. Grouped by status so active projects surface above archived.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/efforts/projects")'
    - 'file.name != "_index"'
views:
  - type: table
    name: By status
    order:
      - status
      - file.name
      - modified
```

> Bases lens above (Obsidian ≥ 1.9.10). Dataview equivalent:
> `TABLE status, modified FROM "wiki/efforts/projects" WHERE file.name != "_index" SORT status`.
> Hand-seeded by the kit and yours to edit.
