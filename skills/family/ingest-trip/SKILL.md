---
name: ingest-trip
description: "Capture a trip booking confirmation (hotel, flight, rental car, activity reservation) into a structured trip page in wiki/travel/upcoming/. Use when a booking confirmation arrives via email, PDF, or web page, or the user says \"save this trip booking\" / \"track this reservation\". For itinerary planning use trip-planner; for packing/pre-departure use trip-prep."
license: MIT
metadata:
  variant: family
---

# Ingest Trip Skill (Family Variant)

Specialized content-type ingester for trip itineraries — booking confirmations, hotel reservations, flight tickets, rental car bookings, activity reservations. Composes a source-type ingester for cleanup, then applies trip schema. Output: a structured trip page in `wiki/travel/upcoming/`.

## When to Use

The orchestrator routes here when:
- A booking confirmation arrives (email, PDF, web page)
- The user says "save this trip booking" / "track this reservation"
- Multiple bookings need to be aggregated into a single trip

## Composition (two-axis routing)

| Source | Source-type cleanup | Result |
|---|---|---|
| Booking confirmation URL | [[ingest-website]] (defuddle; pure.md fallback for booking sites) | clean markdown |
| Booking confirmation PDF | [[ingest-document]] (Docling) | clean markdown |
| Email forward (booking email) | none if text — paste handling; [[ingest-document]] if attachment | content |
| Multiple bookings (one trip, many confirmations) | run multiple times, aggregate into the same trip page | trip page |

## Inputs

After source-type cleanup:
- The cleaned-up booking content
- Existing trip pages in `wiki/travel/upcoming/` — to detect whether this booking belongs to an existing trip or starts a new one
- `wiki/people/` — for who's traveling
- `wiki/travel/past/` — for similar past trips' lessons-learned

## Algorithm

1. **Extract booking type.** Flight, hotel, rental car, activity, train, ferry, etc.
2. **Extract core fields.**
   - Dates (arrival / departure)
   - Confirmation number
   - Booked through (Booking.com, Expedia, direct, etc.)
   - Cost
   - Contact info (hotel phone, airline reservation line)
3. **Identify travelers** — usually in the booking; default to whole household if ambiguous.
4. **Detect trip association.**
   - If a trip page already exists for the dates / destination, append to that trip
   - If not, propose a new trip page
5. **Detect destination.** Hotel address, flight destination, etc. Cross-reference with past trips for the same destination.

## Output

If new trip: create `wiki/travel/upcoming/{YYYY-MM-DD}-{destination-slug}.md`:

```yaml
---
title: "{Destination} {Year}"
type: trip
status: upcoming   # upcoming | active | past
provenance: extracted
created: {today}
modified: {today}
tags: [trip, {destination-slug}]
travelers: [{names}]
start_date: {date}
end_date: {date}
destination: "{destination}"
---
```

Body sections:
- `## Synopsis` — one sentence on the trip
- `## Travelers` — who's going
- `## Bookings` — flights, hotels, rentals with confirmation numbers
- `## Itinerary` — day-by-day plan (filled in as more bookings arrive)
- `## Activities` — planned activities + reservations
- `## Logistics` — passport check, mail hold, pet care, etc. (filled in by [[trip-prep]] skill)
- `## Cross-references` — past trips to similar destinations

If existing trip: **append the booking** to the relevant section (Bookings, Itinerary, or Activities).

**Always:** save raw confirmation to `raw/travel/{YYYY-MM-DD}-{slug}.md`. Companion page if it's a PDF.

## Side-effects

1. **Surface trip dates** for family calendar awareness.
2. **Surface passport / ID expiration check** if travel is international.
3. **Surface [[trip-prep]] readiness check** at 2-3 weeks before departure.
4. **Update `wiki/travel/upcoming/index.md`** with the trip listed.
5. **Append to `log/changelog.md`**: "Trip ingested: [[travel/upcoming/{slug}]]."

## Interactive Review

```
Trip ingested: Vermont Family Trip, 2026-06-12 to 2026-06-19

Booking detected: Hotel Mountain Inn, Stowe VT
Confirmation: ABC123456
Cost: $1,840 (4 nights)
Booked through: Direct (hotel.com)

Trip association:
  No existing trip page for these dates → propose creating new trip
  Past trip: 2024 New England — Vermont segment for reference

Travelers: defaulting to whole household (Eugene, Sarah, Jake, Mia)
  Adjust travelers?

International travel: NO (passport check skipped)

Trip-prep timing: 3 weeks pre-trip = 2026-05-22 — schedule reminder?

Create trip page and save booking?
```

## Failure Modes

- **Booking conflicts with existing trip.** E.g., a hotel booking for dates that overlap an existing trip but at a different destination. Surface — could be a side-trip, error, or new trip.
- **Travelers ambiguous.** Default to household but surface; if a sub-set of family is traveling, capture that explicitly.
- **Booking date in the past.** Probably a confirmation arriving for a past trip. Move to `wiki/travel/past/` instead of upcoming.
- **Confirmation number / contact info missing.** Save what's available; flag what's missing.

## Cadence

- **On demand:** Run when each booking arrives.
- **Aggregation pattern:** A trip typically has multiple bookings; expect to run this skill several times for one trip.
- **No scheduling:** Reactive.
- **Pairs with [[trip-prep]]:** trip-prep reads the populated trip page 2-3 weeks pre-trip.
