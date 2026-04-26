---
name: ingest-recipe
description: "Capture a recipe from a URL, photo, scan, or pasted text into a structured wiki/food/{folder}/{slug}.md page cross-linked to dietary notes for per-person allergen flags. Use when the user says \"ingest / save this recipe\", or the source matches a recipe-host pattern (food blog, NYT Cooking, Bon Appetit, AllRecipes, Serious Eats)."
license: MIT
metadata:
  variant: family
---

# Ingest Recipe Skill

Specialized content-type ingester for recipes. Composes a source-type ingester (`ingest-website` for URLs, `ingest-document` for photos / scans, paste handling for conversations) with recipe-schema extraction. Output: a structured `wiki/food/{folder}/{slug}.md` page using the `_templates/recipe.md` schema, cross-linked to dietary notes for per-person allergen flags.

## When to Use

The orchestrator (`skills/shared/ingest.md`) routes here when:

- The user says "ingest / save this recipe" with a URL, file, or pasted text
- The source URL matches a recipe-host pattern (food blog, NYT Cooking, Bon Appétit, AllRecipes, Serious Eats, etc.)
- A photo / scan of a handwritten or printed card is provided

## Composition (two-axis routing)

This is a content-type ingester. It composes a source-type ingester for cleanup, then applies recipe schema. Common compositions:

| Source | Source-type cleanup | Result |
|---|---|---|
| Recipe URL (food blog, NYT Cooking, etc.) | [[ingest-website]] (defuddle default; pure.md fallback for JS-heavy sites) | clean markdown of the recipe page |
| Photo of handwritten / printed card | [[ingest-document]] (Docling with OCR) | clean markdown of the card text |
| Pasted text (recipe shared in chat / DM) | none — handle directly | raw text |

After cleanup, this skill applies the recipe schema regardless of source.

## Inputs

After source-type cleanup, the skill works from clean markdown. It reads:

1. **The cleaned-up recipe text** — title, ingredients, instructions, servings, prep / cook time, source URL or attribution.
2. **`wiki/food/dietary-notes.md`** — per-person allergen and preference info (e.g., Jake gluten-free, Sarah no shellfish, Mia hates mushrooms).
3. **The existing recipe library** — `wiki/food/family-favorites/` and `wiki/food/weeknight/` — to detect duplicates by name or URL.
4. **The recipe template** — `_templates/recipe.md` for the target schema.

## Algorithm

1. **Extract recipe schema.** Most recipe sites embed schema.org/Recipe microdata; check the source HTML if available, or heuristically parse the cleaned markdown:
   - Title (article H1 or first prominent heading)
   - Description / introduction (first paragraph after the title)
   - Ingredients list — typically an unordered list of "{quantity} {ingredient}" entries
   - Instructions — typically a numbered or stepped list
   - Servings, prep time, cook time, total time — often in a metadata block near the title
   - Source URL and author attribution
2. **Identify allergens.** Cross-reference each ingredient against `dietary-notes.md` per family member. Flag matches: gluten in soy sauce → Jake; shellfish in shrimp → Sarah.
3. **Identify dietary tags.** Detect categories: vegetarian / vegan / dairy-free / gluten-free / one-pan / sheet-pan / instant-pot / weeknight / make-ahead.
4. **Decide target folder.** `family-favorites/` if the family confirms (during interactive review) they make it regularly; `weeknight/` if prep + cook ≤ 30 min; otherwise just `food/{slug}.md`.
5. **Detect duplicates.** Search the recipe library by title and source URL. If a similar recipe exists, surface as a contradiction-style flag — don't silently overwrite.

## Output

Write `wiki/food/{folder}/{slug}.md` using the `_templates/recipe.md` schema:

```yaml
---
title: "{Recipe Name}"
type: recipe
status: current
provenance: extracted   # extracted from a source; switch to mixed if family modifications added later
created: {today}
modified: {today}
tags: [recipe, {meal-type}, {cuisine}]
servings: "{N}"
prep_time: "{minutes}"
cook_time: "{minutes}"
total_time: "{minutes}"
source: "{URL or attribution}"
dietary: [{tags}]
---
```

Body sections (per the recipe template):

- `## Synopsis` — one sentence: what it is, when to make it, key flavor or occasion
- `## Ingredients` — each as a bullet
- `## Instructions` — numbered list
- `## Notes` — allergen flags as callouts; family modifications; attribution context. Allergen flags:

  ```markdown
  > [!warning] Contains gluten — Jake
  > Soy sauce in the marinade is wheat-derived. Substitute tamari or coconut aminos.
  ```
- `## Variations` — placeholder for family modifications, populated over time
- `## Cross-References` — `[[food/dietary-notes]]`, `[[food/meal-plans/{recent}]]`

## Side-effects

1. **Update `wiki/food/family-favorites/index.md` or `wiki/food/weeknight/index.md`** with the new entry.
2. **Append to `log/changelog.md`**: "Recipe ingested: [[food/{folder}/{slug}]]."
3. **If new dietary categories appear** (e.g., the recipe is keto and the family hasn't tagged anything keto before), surface during interactive review for explicit acknowledgment.

## Interactive Review

Before saving, present the extraction to the user:

```
Recipe extracted: Sheet-Pan Chicken Tacos
Servings: 4 · Prep: 15 min · Cook: 25 min
Source: https://example.com/sheet-pan-chicken-tacos

Allergen flags:
- ⚠ Gluten — Jake (soy sauce in marinade)
- (no other family-specific flags)

Dietary tags: weeknight, mexican, sheet-pan

Save to: wiki/food/weeknight/sheet-pan-chicken-tacos.md
Or move to family-favorites/ if the family already cooks this regularly.

Save?
```

The user can confirm, redirect the destination folder, or adjust the dietary flags.

## Failure Modes

- **No recipe schema detected.** The page may not be a recipe (or is poorly structured). Surface this; ask the user to confirm or paste the recipe text directly.
- **Schema.org/Recipe microdata absent and heuristic parsing fails.** Fall back to asking the user to confirm the extracted ingredients and steps; don't write a half-extracted recipe.
- **Duplicate detected.** Surface both, ask the user whether to overwrite, version, or merge variations.
- **Source URL is paywalled.** Use `ingest-website` with `--cookies` from an authenticated browser, or paste the recipe text directly.
- **Photo of card has poor OCR.** Surface the OCR output; ask the user to confirm before writing the recipe page.

## Cadence

- **On demand:** Run when the family encounters a recipe worth saving.
- **No scheduling needed:** This is reactive, not proactive. Pairs with `meal-planning` (which reads the recipe library) — every recipe ingested is a future meal-planning candidate.
