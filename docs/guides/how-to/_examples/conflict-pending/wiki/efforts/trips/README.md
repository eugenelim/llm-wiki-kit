# efforts/trips/

The **trip** container registry. One container per trip — a folder-mode
container: each trip is a folder `efforts/trips/<trip>/` that accumulates
booking confirmations, an itinerary, planned activities, and the packing
and pre-trip task list `trip-prep` writes 2-3 weeks ahead of departure.

## Conventions

- **One folder per trip.** `efforts/trips/<YYYY-MM-DD-destination-slug>/`
  where the date is the trip's start date — e.g.
  `efforts/trips/2026-06-portland/`. The trip's pages live **flat** inside
  it; the only permitted subfolder is a non-semantic bulk sink
  (`_assets/` for scans and tickets, `_working/` for scratch).
- **Status is a property, not a folder.** `status: active | archived |
  someday` lives in frontmatter. There is **no** `upcoming/` or `past/`
  subfolder — lifecycle is the `status` facet, and the `_index.md` map
  filters on it. Flip the status when the trip ends; the change is
  journaled.
- **Travelers as wikilinks.** Each name in `trip_travelers` resolves to a
  node page under `wiki/people/`. The `trip-doc` ingester stubs new people
  pages on first reference.
- **Membership by `parent:`.** A page that belongs to a trip names it with
  `parent: [[wiki/efforts/trips/<trip>]]`.

## What goes in a trip folder

- A trip page (synopsis, dates, destination, travelers).
- Bookings (flights, hotels, rentals) with confirmation numbers.
- Itinerary day-by-day, populated as more bookings arrive.
- Packing list + pre-trip tasks (filled in by `trip-prep`).
- Cross-references to past trips to similar destinations.

## Created by other primitives

- `trip-doc` ingester captures booking confirmations and starts or
  appends to a trip.
- `trip-prep` operation reads the populated trip and writes the packing
  list and pre-trip task list back.
