---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# Atlas — map of content

The synthesis layer: durable maps and overviews that sit above raw
capture. Human-gated — pages arrive by review, not by ingest. This map
lists the syntheses and area MOCs you've promoted.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/atlas")'
    - 'file.name != "_index"'
views:
  - type: table
    name: Syntheses & area maps
    order:
      - genre
      - file.name
      - status
      - modified
```

> Bases lens above (Obsidian ≥ 1.9.10). Dataview equivalent:
> `TABLE genre, status FROM "wiki/atlas" SORT modified DESC`. Seeded empty
> but for this map; add area MOCs and syntheses as you promote them.
