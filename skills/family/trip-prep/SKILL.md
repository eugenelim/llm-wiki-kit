---
name: trip-prep
description: "Assemble a packing list per family member and a pre-trip task list for an upcoming trip, reading trip details, family member docs, and past trip pages for what worked. Use 2-3 weeks before major travel, 1 week before shorter trips, or on request: \"prep for the {trip} trip\" / \"what should we pack?\". For itinerary and POI discovery use trip-planner."
license: MIT
metadata:
  variant: family
---

# Trip Prep Skill (Family Variant)

Planning operation. For an upcoming trip, assemble a packing list per family member and a pre-trip task list. Read trip details + family member docs + past trip pages for what worked.

## When to Use

- 2-3 weeks before a trip (for major travel)
- 1 week before for shorter trips
- On request: "Prep for the {trip} trip"

## Inputs

User provides:
- Trip page reference (`wiki/travel/upcoming/{trip-slug}.md`)
- Optional: theme tweaks ("light packing," "extra-cold weather," "kid-friendly only")

Reads:
- The trip page — destination, dates, accommodations, planned activities
- Family member docs — `wiki/people/{name}.md` for sizes, allergies, special needs
- `wiki/health/medications.md` — what to bring
- `wiki/travel/past/` — past trip pages with "what we wish we'd brought" notes
- Reference pages — passport / ID expiration, immunizations

## Algorithm

1. **Read trip context.** Destination, season, weather, duration, planned activities.
2. **Per-person packing list.** For each family member traveling, generate clothing + toiletries + medical needs (medications, EpiPens, etc.) + activity-specific items.
3. **Shared / household items.** Chargers, adapters, snacks, first aid, beach gear, etc. (depends on trip).
4. **Pre-trip task list.** Passport / ID expiration check, mail hold, pet care, house sitting, transportation booking, eSIM / international plan, currency.
5. **Surface lessons from past trips.** Cross-reference past trip pages for "what we wish we'd brought / what was useless." Suggest accordingly.

## Output

Append to the trip page (`wiki/travel/upcoming/{trip-slug}.md`) — don't create new file. Add or update sections:

- `## Packing List` — per-person sub-sections + Shared Household
- `## Pre-trip Tasks` — checklist with deadlines

If the trip page already has these sections, augment rather than overwrite.

## Side-effects

1. **Surface action items** for tasks that have specific deadlines (book pet boarding, request mail hold). Optionally add to a task list.
2. **Update related pages.** If a passport is expiring within 6 months of the trip date, surface as urgent in the family follow-up tracker.
3. **Append to `log/changelog.md`**: "Trip prep: [[travel/upcoming/{slug}]]."

## Interactive Review

```
Trip prep for: Vermont Family Trip, 2026-06-12 to 2026-06-19

Per-person packing list:
  Jake (8): rain jacket, sturdy shoes, swim trunks, EpiPen ×2, Albuterol, …
  Mia (12): hiking boots, layers (mountain weather), swim suit, retainer, …
  Sarah: hiking pack, light layers, prescription meds, contact lens supplies, …
  Eugene: hiking pack, camera, work laptop (?), …

Shared household:
  - First aid kit (refresh — last checked 2025-09)
  - Chargers + battery packs
  - Snacks + water bottles
  - Beach gear (lake swimming planned)

Pre-trip tasks (with deadlines):
  - Confirm pet boarding (book by 2026-05-29)
  - Mail hold request (submit 2026-06-09)
  - Request prescription refills 2 weeks out
  - Check tire pressure + oil before drive
  - Pack non-perishable snacks night before

Surfaced from past trips:
  - 2024 Acadia trip noted: "needed more rain gear; wish we'd brought trekking poles"
  - 2025 Beach trip noted: "kindle for car ride was great; print map worked when phone died"

Apply the packing list + tasks to the trip page?
```

## Failure Modes

- **Trip page minimal (just dates + destination).** Surface: "trip details are sparse — the more populated the trip page, the better the prep. Want to fill in accommodations / activities first?"
- **Past trips absent.** Skip lessons-learned section; flag: "no past trip pages — packing list is generic. Capture lessons after this trip to make future prep richer."
- **Family member docs minimal.** Use general clothing categories; surface: "consider adding sizing / special-needs to person pages."
- **Trip date already passed.** Refuse: "trip date is in the past. Was this for a past trip retrospective instead?"

## Cadence

- **Manual:** Run 2-3 weeks before each trip.
- **No scheduled runs:** Trips are episodic. Trigger from trip-page creation if integrated.
