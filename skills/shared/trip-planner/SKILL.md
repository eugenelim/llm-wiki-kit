---
name: trip-planner
description: "Discovery + itinerary skill. Given destination + preferences (pace, interests, constraints, anchors), research authoritative sources, curate POIs (points of interest), and produce a day-by-day itinerary integrated into the trip page. Use 2-6 weeks pre-trip after dates are set, on request \"plan the {trip} trip\" / \"what should we do in {destination}?\", or in discover-only mode for candidate research. For packing/pre-departure logistics use trip-prep; to capture a booking confirmation use ingest-trip."
license: MIT
metadata:
  variant: shared
---

# Trip Planner Skill (Family / Personal — Travel)

Given trip preferences + destination, research authoritative sources, discover and curate POIs (points of interest), and produce a day-by-day itinerary integrated into the trip page. The discovery + itinerary counterpart to [[trip-prep]] (which handles packing list + pre-trip tasks).

## When to Use

- After a trip is booked / dates are set ([[ingest-trip]] has produced the trip page)
- 2-6 weeks pre-trip — late enough to have details, early enough to influence remaining bookings
- On request: "Plan the {trip} trip" / "What should we do in {destination}?"
- **Discover-only mode:** "Could we go to {place} for spring break?" — research candidates without committing to a trip

Applies to vaults that have `wiki/travel/` (default in family variant; personal users can adopt by adding the folder to their ontology).

## Inputs

User provides:
- Trip page (wikilink) OR explicit destination + dates + travelers
- **Preferences:**
  - **Pace** — packed | balanced | relaxed
  - **Interests** — culture, food, nature, history, adventure, kid-friendly, romance, nightlife, shopping, etc.
  - **Constraints** — budget tier, dietary restrictions, mobility considerations, language barrier
  - **Anchors** — must-do items (specific reservations, named POIs, ticketed events the trip is built around)
- Optional: number of days for itinerary (defaults to trip duration)

Reads:
- The trip page — destination, dates, travelers, party size
- `wiki/travel/places/{location}/` — existing POI catalog (don't re-discover what we already know)
- `wiki/travel/past/` — past trip pages to similar destinations for what worked / didn't
- Family member docs (family variant) for ages, mobility, interests
- `wiki/food/dietary-notes.md` (family) or personal preferences (personal)
- Provider config `.claude/research-providers.yaml` to know what's available for discovery

## Operation — three phases

### Phase 1: Discover

Dispatch research queries via the [[research]] orchestrator (which picks Perplexity / Gemini / Semantic Scholar based on question shape and what's enabled):

- "Best things to do in {destination} for {audience} in {month}"
- "Must-eat restaurants in {destination} at {price-tier}"
- "{destination} {interest-tag} options" (e.g., kid-friendly hikes, art museums, adventure activities)
- "Things to skip in {destination}" (overrated tourist traps)
- "{destination} kid-friendly / accessible / dietary-fit options"
- "Recent reviews of {anchor-POI}" (to verify still-good before commiting)

Each query produces research-source pages. The skill auto-creates a research project at [[research-start]] with `verdict_shape: shortlist` (the verdict is "the trip's itinerary"). Sources land in the project's `sources/` folder.

### Phase 2: Curate

For each candidate POI surfaced in research:

- Check `wiki/travel/places/{location}/` for an existing POI page — augment if found, create if not (using `_templates/poi.md`)
- Tag with `kind`, `interests`, `duration`, `kid-friendly` flags
- Cite the research source in the POI's `rating_source:` field
- For anchored items the user named, ensure they have full POI pages (with reservation info, hours, address)

Surface to user for shortlisting, tiered by consensus:

```
Discovered POIs in Tokyo (15 candidates):

  Must-do (3+ sources): [[teamlab-borderless]], [[tsukiji-outer-market]], [[asakusa-senso-ji]]
  Recommended: [[ghibli-museum]] (1-month reservation), [[teamlab-planets]], …
  Lower priority: [[...]] — common-but-overrated

Shortlist for the trip?
```

### Phase 3: Itinerary

Given shortlisted POIs + trip dates:

- **Cluster** POIs by neighborhood / proximity (group nearby items into same-day blocks to minimize transit)
- **Match to pace:** packed = 4-5 POIs / day; balanced = 2-3; relaxed = 1-2
- **Honor party constraints:**
  - Kids: kid-energy budget, nap windows, food timing
  - Dietary: ensure each day has dietary-fit lunch / dinner options
  - Mobility: limit walking-heavy days
  - Anchors: schedule fixed-time items (reservations, ticketed events) first; build the day around them
- **Build day-by-day plan**
- **Append to the trip page's `## Itinerary` section**

Generated itinerary in the trip page:

```markdown
## Itinerary

### Day 1 — 2026-06-12 (arrival)
- Afternoon: [[asakusa-senso-ji]] — temple + shopping (~2 hrs)
- Evening: dinner near hotel; recover from flight

### Day 2 — 2026-06-13
- Morning: [[tsukiji-outer-market]] (breakfast + walk)
- Afternoon: [[teamlab-borderless]] (book 14:00 entry)
- …
```

## Output

Multiple files updated:

1. **POI pages** — `wiki/travel/places/{location}/{slug}.md` for each curated POI (new or augmented)
2. **Trip page** — `## Activities` and `## Itinerary` sections populated
3. **Research project** — `wiki/research/{date}-{trip-slug}/` if scaffolded for the trip, with sources, pillar pages, and a shortlist artifact

## Side-effects

1. POI pages reference the trip in `trips_referenced:` frontmatter
2. Trip page's frontmatter `pois:` lists wikilinks to all included POIs
3. After the trip, run [[trip-planner]] in **retrospect mode** to update POI pages with `visited: true` + `visit_date:` + visit notes
4. Append to `log/changelog.md`

## Interactive Review

The discovery phase produces a candidate list — user shortlists.
The itinerary phase drafts day-by-day — user adjusts pacing, swaps items, or marks anchors-time-fixed.
Both stages confirm before writing to the trip page.

## Failure Modes

- **Destination too vague.** Ask for specifics ("Japan" → "Tokyo / Kyoto / Osaka? How many days each?").
- **No prior POI catalog for this destination.** Build from scratch via research; the catalog grows over time.
- **Research providers all disabled.** Surface; require enabling at least Perplexity for discovery (the cheap default).
- **Trip page absent + discover-only mode.** Save research as a research project; produce a candidate-list artifact; don't try to populate a trip.
- **Calendar / pace mismatch.** If user wants 5 things/day on a relaxed pace, surface the contradiction.
- **Anchor conflicts.** Two reservations same time, or anchored item's hours don't fit the trip dates. Surface; ask user to resolve.
- **Past-trip notes contradict current research.** Surface ("[[past-trip]] noted X was disappointing in 2024; current research says it's been refreshed in 2026; verify current operating hours"); let user weigh.

## Cadence

- **Per trip:** Run once 2-6 weeks pre-trip; iterate as more research surfaces options.
- **Pairs with [[trip-prep]]:** trip-planner handles activities/itinerary; trip-prep handles packing/logistics.
- **Discover-only mode:** any time you're considering a destination — produces a research project, not a trip.
- **Retrospect mode:** post-trip, update POI pages with what actually happened.

## What's next (deferred)

- Multi-destination trip support (Japan: Tokyo + Kyoto + Osaka with allocations per city)
- Booking-integration: ingest reservation confirmations and auto-link from itinerary slots
- Past-trip reflection operation: read past trips for "what we wish we'd done differently"
