---
genre: moc
subtype: moc
status: active
provenance: synthesized
created: 2026-06-16
modified: 2026-06-16
tags: [moc]
---

# People — map of content

Entity nodes: every person and organization you link to by name. Pages
are grouped by `subtype` (`person`, `org`, `vendor`, `customer`), never by
folder — a node's kind is a property, not a location.

```base
filters:
  and:
    - 'file.folder.startsWith("wiki/people")'
    - 'file.name != "_index"'
views:
  - type: table
    name: By subtype
    order:
      - subtype
      - file.name
      - status
      - modified
```

> Bases lens above (Obsidian ≥ 1.9.10). If you use Dataview instead, a
> `TABLE subtype, status FROM "wiki/people" SORT subtype` block gives the
> same grouping. This map is hand-seeded by the kit and yours to edit.
