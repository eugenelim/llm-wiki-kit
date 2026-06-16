---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# Trips — map of content

Folder-mode containers: one folder per trip under `efforts/trips/`.
Grouped by status so upcoming and active trips surface above archived
ones — without an `upcoming/`/`past/` folder.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/efforts/trips")'
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
> `TABLE status, modified FROM "wiki/efforts/trips" WHERE file.name != "_index" SORT status`.
> Hand-seeded by the kit and yours to edit.
