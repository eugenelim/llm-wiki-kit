---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# Library — map of content

Capture & reference. Everything ingested or kept for reference that isn't
an entity node, an effort, or a synthesis. Grouped by `genre` so you
browse by kind without a folder per kind.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/library")'
    - 'file.name != "_index"'
views:
  - type: table
    name: By genre
    order:
      - genre
      - subtype
      - file.name
      - status
      - modified
```

> Bases lens above (Obsidian ≥ 1.9.10). Dataview equivalent:
> `TABLE genre, subtype, status FROM "wiki/library" SORT genre`. This map
> is hand-seeded by the kit and yours to edit.
