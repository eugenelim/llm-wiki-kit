---
name: weekly-digest
description: "Synthesize what changed across the household in the last 7 days — the family-variant \"what happened this week\" digest read by other family members. Lighter on reflection than the personal weekly-review. Use Sunday evening (after meal-planning) or Friday afternoon, before household-coordination conversations, or on request: \"what happened this week?\"."
license: MIT
metadata:
  variant: family
---

# Weekly Digest Skill (Family Variant)

Synthesizing operation. What changed across the household in the last 7 days. Output is a "what happened" reference for the family — a low-friction artifact that other family members consume even if they don't capture themselves.

## When to Use

- Sunday evening (after meal planning) or Friday afternoon
- Before household-coordination conversations
- On request: "What happened this week?"

This is the family-variant analogue of work's *weekly-digest* and personal's *weekly-review* — but lighter on reflection (households don't need synthesis-grade reflection weekly).

## Inputs

User provides:
- Optional: focus area ("just medical," "just food + travel")
- Optional: explicit week

Reads:
- `log/changelog.md` entries from the last 7 days
- All wiki pages with `modified:` in the last 7 days
- This week's `wiki/food/meal-plans/{week}.md`
- Recent appointments / visits — `wiki/health/{person}-medical.md` modifications
- Recent home maintenance — `wiki/home/maintenance/`
- Active travel plans

## Algorithm

1. **Aggregate changes** across the household domains: people, health, home, food, travel, finances, education.
2. **Group by domain.** Each domain gets a sub-section.
3. **Surface follow-ups.** Anything logged this week that has a future action.
4. **Surface the week's signature events.** Visits, appointments, ingestions, decisions.
5. **Quantify lightly.** Counts per domain (e.g., "3 medical visits, 2 recipes added, 1 trip planned").

## Output

Write `wiki/log/digest-{YYYY-WW}.md`:

```yaml
---
type: weekly-digest
week: {YYYY-WW}
created: {today}
modified: {today}
tags: [digest, weekly]
status: current
---
```

Body sections:
- `## Synopsis` — 2-3 sentences capturing the week's character
- `## Health` — visits / changes / new prescriptions / follow-ups logged
- `## Home` — maintenance done / vendors used / appliance issues
- `## Food` — meals planned / recipes added / dietary changes
- `## Travel` — trips planned / booked / past-trip reflection
- `## Education` — school doc additions / activities
- `## Finances` — receipts / expenses / financial decisions
- `## Memory` — milestones / events worth capturing

Each domain section is brief — a few bullets, with wikilinks to the source pages.

## Side-effects

1. **Update `wiki/log/digest-index.md`** with the new week's link.
2. **Append to `log/changelog.md`**: "Weekly digest: [[log/digest-{YYYY-WW}]]."
3. **Optionally** post the synopsis to a household text thread or shared note.

## Interactive Review

```
Weekly digest for {YYYY-WW}:

Synopsis: Quiet week — Jake's allergy panel results came in (negative for new
allergens), home HVAC filter replaced, meal plan held to schedule, Vermont
trip booked, Mia started new piano lessons.

Health (3 events): Jake allergy panel results, Sarah annual physical scheduled
for next month, medications refilled.
Home (1): HVAC filter replaced (next due 2026-08-01).
Food (2): meal plan executed; one recipe ingested (sheet-pan chicken tacos).
Travel (1): Vermont 2026-06-12 booked.
Education (1): Mia's first piano lesson; teacher contact added.
Finances (4 receipts ingested).

Save digest?
```

## Failure Modes

- **Quiet week (almost no activity).** Produce a brief digest acknowledging the gap. Don't fabricate.
- **Activity confined to one domain.** Surface the imbalance — likely fine, but worth noting for trends ("third week with no Travel updates" might or might not be a concern).

## Cadence

- **Manual:** Run Sunday evening or Friday afternoon.
- **Scheduled:** Cowork weekly task; output goes to the digest page.
