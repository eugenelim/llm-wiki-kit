---
type: index
folder: restaurants
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, restaurants, inventory]
---

## Synopsis

Restaurant inventory — places we've eaten, plan to try, or skipped after one visit. Each entry is a small file with `type: restaurant` frontmatter; the live filtered view is `restaurants.base`.

## How this folder works

Each restaurant is a `.md` file with the schema declared by `_templates/restaurant.md` (cuisine, location, price tier, family rating, notes keywords). Add entries by copying the template; browse via `restaurants.base` in Obsidian.

## Common access patterns

- "What's our go-to Thai place?" → filter by cuisine
- "Where haven't we been recently?" → sort by last_visited
- "Wishlist" → filter by status: wishlist
- "Kid-friendly options nearby" → filter by notes_keywords + location

## Related

- [[recipe-recommender]] for at-home dining; restaurant inventory is the eat-out alternative
- [[meal-planning]] decisions sometimes consult this list (when planning a dine-out night)
- [[wiki/food/dietary-notes]] for cross-checking a restaurant against family dietary constraints
