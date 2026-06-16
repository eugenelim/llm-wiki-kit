---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# Efforts — map of content

Bounded containers: trips, cases, projects — each with its own identity
and a start and an end. Nested under a per-type registry
(`efforts/<type>/`). This map lists efforts across types by status.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/efforts")'
    - 'file.name != "_index"'
views:
  - type: table
    name: By type and status
    order:
      - file.folder
      - file.name
      - status
      - modified
```

> Bases lens above (Obsidian ≥ 1.9.10). Dataview equivalent:
> `TABLE status, modified FROM "wiki/efforts" WHERE file.name != "_index"`.
> Each `efforts/<type>/` registry also ships its own `_index.md`. This map
> is hand-seeded by the kit and yours to edit.
