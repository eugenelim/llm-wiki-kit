---
name: recipe-recommender
description: "Rank recipes from the family library for tonight's dinner given context (what's in the fridge, time available, who's eating). Inline ranked recommendation; does NOT write a wiki page. Use for \"tonight's-dinner\" questions, \"what can we make with what's in the fridge?\", or quick recommendations when meal-planning feels heavy. For weekly meal plans use meal-planning instead."
license: MIT
metadata:
  variant: family
---

# Recipe Recommender Skill (Family Variant)

Recommending operation. Given context (what's in the fridge, season, time available, who's eating), rank recipes from the family library. Inline report — does NOT write a wiki page. Pairs with [[meal-planning]] but is faster and ad-hoc.

## When to Use

- Tonight's-dinner question
- "What can we make with what's in the fridge?"
- Picking a recipe for a guest dinner with specific dietary constraints
- Quick recommendation when meal-planning feels heavy
- On request: "What should we cook tonight?"

## Inputs

User provides:
- Time available (default: ~30 min)
- Optional: ingredients on hand or "what's in the fridge"
- Optional: who's eating tonight (defaults to whole family)
- Optional: cuisine direction or "feeling like" hint

Reads:
- All recipe pages in `wiki/food/family-favorites/`, `wiki/food/weeknight/`, and any other recipe folders
- `wiki/food/dietary-notes.md` — restrictions per family member
- The most recent meal plan — for repetition avoidance
- Optional: a pantry / fridge inventory page if maintained

## Algorithm

1. **Filter by hard constraints.**
   - Dietary restrictions for everyone eating tonight (gluten-free for Jake if Jake's eating; no shellfish for Sarah if Sarah's eating)
   - Available ingredients (if "what's in the fridge" was provided)
2. **Filter by time budget.** Prep + cook ≤ user's time; pad 10% for unknowns.
3. **Score remaining candidates.**
   - Time fit (closer to time-budget = better; well under = better than over)
   - Recency penalty (cooked in the last 14 days = -2 points; last 7 = -3)
   - Family-favorite bonus (+1 if from family-favorites folder)
   - Season fit (+1 if seasonal tags align — winter stew in February)
   - Ingredient match (+1 per matching pantry / fridge item if inventory provided)
4. **Return top 3-5** ranked, with reasoning per recipe.

## Output

Inline markdown report (does NOT write a wiki page):

```
Recipe recommendations — tonight, ~30 min, family of 4 (no Sarah, no shellfish):

1. [[food/weeknight/sheet-pan-chicken-tacos]] — 25 min total
   Why: top family-favorite with Jake's gluten-free swap (use corn tortillas;
        replace soy in marinade with tamari)
   Ingredient match: chicken thighs ✓, peppers ✓, cilantro ✓
   Last cooked: 2026-04-08 (3 weeks ago — fresh enough)

2. [[food/weeknight/lemon-pasta]] — 20 min total
   Why: quick + Sarah's pick (fine without her); use gluten-free pasta for Jake
   Ingredient match: pasta ✓, lemon ✓, parmesan ✓
   Last cooked: 2026-03-15

3. [[food/weeknight/chicken-rice-bowl]] — 30 min total
   Why: kid-friendly; holds well if dinner gets pushed
   Ingredient match: chicken thighs ✓, rice ✓
   Last cooked: 2026-04-22 (this week — reduced score)

Adjust with more inventory info or different time budget?
```

## Side-effects

- **None by default.** This is a recommendation; it doesn't change the wiki.
- *Optionally*, when the user picks: update the recipe's `last_cooked:` field and add a brief note. (Or trigger that as a follow-on.)

## Interactive Review

The output IS the review — concise, sorted, with reasoning. The user picks one or asks for re-ranking with different inputs.

## Failure Modes

- **No recipes match the hard constraints.** Surface: "no recipes match {constraints}. Suggest: relax a constraint, or capture a new recipe?"
- **Recipe library too thin.** Surface: "library has {N} recipes — too few for meaningful ranking. Build the library via [[ingest-recipe]] first."
- **All matches recently cooked.** Surface: "every match was cooked in the last 2 weeks. Continue with a repeat, or expand search to other folders?"
- **Inventory provided but doesn't match any recipe.** Surface: "fridge inventory doesn't match the library; consider what to make with these ingredients (open-ended cooking) or save them for tomorrow."

## Cadence

- **On demand:** Run when picking what to cook.
- **No scheduled runs:** Pull-based.
- **Pairs with [[meal-planning]]:** weekly meal-planning produces the schedule; recipe-recommender handles ad-hoc deviations and last-minute decisions.
