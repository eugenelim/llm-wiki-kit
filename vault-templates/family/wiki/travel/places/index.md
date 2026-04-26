---
type: index
folder: places
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, places, poi, inventory, travel]
---

## Synopsis

POI (point of interest) catalog — destinations, restaurants, museums, hikes, and activities worth visiting, organized by location. Each POI is a structured page; the live filtered view is `places.base`.

## Folder structure

```
places/
├── tokyo/                # POIs in Tokyo
│   ├── teamlab-borderless.md
│   ├── tsukiji-outer-market.md
│   └── ...
├── vermont/
├── patagonia/
└── ...
```

## How this folder works

Each POI is a `.md` file with `type: poi` frontmatter (location, kind, duration, interests, rating sources). Add via [[trip-planner]] (research-driven discovery) or by copying `_templates/poi.md` directly when you find something noteworthy.

POIs persist across trips. A place you visited in 2024 might be referenced again in 2027's trip — the POI page accumulates visit notes.

## Common access patterns

- "What's worth doing in Tokyo?" → folder browse or filter by location
- "Restaurants in {location}" → filter by location + kind: restaurant
- "Kid-friendly spots in {location}" → filter by location + interests: kid-friendly
- "Wishlist (not yet visited)" → filter by visited: false
- "What did we do on the {trip}?" → trip page references POIs

## Related

- [[trip-planner]] populates POI pages during trip planning
- [[ingest-trip]] creates trip pages that reference POIs
- [[trip-prep]] uses POIs when assembling itineraries
- Restaurant inventory at `wiki/food/restaurants/` is the local-living equivalent (POIs are travel-flavored; restaurants are home-flavored)

## After a trip

Update visited POIs:
- Set `visited: true`
- Set `visit_date:`
- Add an entry under `## Visit Notes` with what you actually did and whether you'd return
- Cross-link the past trip page

This makes future trip planning richer — the POI catalog grows in fidelity over time.
