---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# Cases — map of content

Folder-mode containers: one folder per case under `efforts/cases/` — a
bounded thread of work or care. Grouped by status so open cases surface
above archived ones.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/efforts/cases")'
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
> `TABLE status, modified FROM "wiki/efforts/cases" WHERE file.name != "_index" SORT status`.
> Hand-seeded by the kit and yours to edit.
