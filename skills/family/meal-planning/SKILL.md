---
name: meal-planning
description: "Produce a weekly family meal plan with shopping list, reading the recipe library, dietary notes, last week's plan, and the family calendar. Use Sunday afternoon before grocery shopping, after a major dietary shift, or on request: \"plan meals for this week\". For ad-hoc \"what should we cook tonight?\" use recipe-recommender instead."
license: MIT
metadata:
  variant: family
---

# Meal Planning Skill (Family Variant)

The canonical family-OS operation. Read the recipe library + dietary notes + last week's plan + family calendar → produce a weekly meal plan with shopping list. The gateway operation that keeps the family vault alive.

## When to Use

- Sunday afternoon (before grocery shopping)
- After a major dietary shift (new restriction, new family member)
- On request: "Plan meals for this week"

This is the family-variant analogue of *sprint-planning* (work) and *weekly-review* (personal) — same role, different domain. Visible weekly payoff that keeps the capture loop alive.

## Inputs

User provides:
- Optional: theme for the week ("we're trying a new cuisine," "easy week — kids' sports")
- Optional: explicit week if not the upcoming one

Reads:
- All recipe pages in `wiki/food/family-favorites/` and `wiki/food/weeknight/`
- `wiki/food/dietary-notes.md` — current restrictions per family member
- The most recent meal plan in `wiki/food/meal-plans/` — last week's; for repetition avoidance and leftover continuity
- Family calendar context (if available — sports nights, late returns)
- Optional: pantry / fridge inventory if the household tracks it
- Recipe template at `_templates/recipe.md` (for understanding schema)

## Algorithm

1. **Honor hard constraints.** Filter recipe candidates to those compatible with current dietary restrictions (no gluten in any meal Jake eats, no shellfish, etc.).
2. **Spread cuisines.** Don't have Italian three nights in a row.
3. **Match prep time to calendar.** ≤30 min on busy nights (sports, late returns); more ambitious on flexible nights.
4. **Avoid recent repetition.** Skip recipes cooked in the last 2 weeks unless they're top family favorites.
5. **One stretch recipe per week.** Ideally Saturday — something the family hasn't made before, or a seasonal fit.
6. **Aggregate shopping list.** Combine ingredients across the week, minus pantry staples.

## Output

Write `wiki/food/meal-plans/{YYYY-MM-DD}-week.md` (date is the Sunday or Monday of the week):

```yaml
---
type: meal-plan
week: {YYYY-MM-DD}
created: {today}
modified: {today}
tags: [meal-plan]
status: current
---
```

Body sections:
- `## Synopsis` — 2-3 sentences (count of planned meals, average prep, dietary fit)
- `## Schedule` — per-day entries with recipe wikilink + prep time + a one-line "why"
- `## Shopping list` — aggregated ingredients (minus pantry staples — see [[food/pantry-staples]])
- `## Notes for next week's planner` — what to capture (new recipes tried, family reactions)

## Side-effects

1. **Update `wiki/food/meal-plans/index.md`** with the new week's link.
2. **Optionally push shopping list** to a grocery app (downstream skill, not built-in).
3. **Append to `log/changelog.md`**: "Meal plan: [[food/meal-plans/{YYYY-MM-DD}-week]]."
4. **Capture family reactions next week** — surface for capture during the next planner: "did the marrakesh chicken work?"

## Interactive Review

```
Proposed meal plan for week of 2026-04-26:

Sun: Sheet-Pan Chicken Tacos (40 min) · Jake-safe, batch-friendly leftovers
Mon: Lemon Pasta (25 min) · gluten-free pasta swap noted
Tue: Chicken Rice Bowl (30 min) · Jake at soccer 5-7pm — quick, holds well
Wed: Leftover sheet-pan tacos
Thu: Garlic Shrimp Broccoli (35 min) · Sarah away — shellfish OK for Jake/Mia
Fri: Pizza night (regular)
Sat: Marrakesh Chicken (60 min) · stretch recipe, North African — new for the family

Shopping list (after pantry-staple subtraction): {N} items.

Save the plan and shopping list?
```

The user can swap meals, mark items as already-have, or move to take-out.

## Failure Modes

- **Recipe library too thin (<10 recipes).** Surface: "Recipe library has only {N} recipes — too few for week-over-week rotation. Capture more (see [[ingest-recipe]])."
- **All week's candidates recently cooked.** Surface and ask: "every match was cooked in the last 2 weeks; relax repetition rule, or add new recipes first?"
- **Calendar context absent.** Default to even prep distribution; surface: "no calendar context available; consider adding it for better night-by-night fit."
- **Dietary-notes absent or stale.** Refuse with note: "dietary-notes.md is missing or >6 months old; refresh first to ensure allergen safety."

## Cadence

- **Manual:** Sunday afternoon, fixed time.
- **Scheduled:** Cowork weekly task on Sunday at 3pm could prompt the meal-planner; the household reviews and shops.
