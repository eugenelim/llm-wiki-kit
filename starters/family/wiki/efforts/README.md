# efforts/

The **bounded-container** role folder. An effort is something with its
own identity and a beginning and an end: a trip, a medical case, a
project. Each effort type gets a registry subfolder — `efforts/trips/`,
`efforts/cases/`, `efforts/projects/` — supplied by a container primitive.

## Containers, not kinds

`efforts/<type>/` is the one place the produced vault nests folders, and
it nests by **instance**, never by kind-of-page. The type subfolder is a
registry of instances; how each instance stores its material depends on
the container's `container_mode`:

- **`folder` mode** (trips, cases) — exclusive material. Each instance is
  a folder `efforts/<type>/<instance>/` holding the instance's pages
  *flat* (a trip's bookings, itinerary, packing list). The only permitted
  subfolder is a non-semantic bulk sink (`_assets/`, `_working/`) — never
  a genre/lifecycle subfolder like `sources/` or `drafts/`.
- **`hub` mode** (projects) — shared material. Each instance is a single
  page `efforts/<type>/<instance>.md`; member pages live in their own role
  folder (a decision in `library/`) and join the hub by the `parent:`
  relation pointing back at the hub page.

## Conventions

- **No lifecycle folders.** A trip is not in `upcoming/` or `past/`; its
  state is the `status` facet (`active`, `archived`, …). The `_index.md`
  maps filter on it.
- **One `parent:` to the effort.** A page that belongs to an effort names
  it with `parent: [[wiki/efforts/<type>/<instance>]]`, whether the page
  lives inside a folder-mode instance or in `library/` as a hub member.

## Created by other primitives

Container primitives (`trips`, `cases`, `projects`) seed the per-type
registries. Content-type ingesters (`trip-doc`, `stakeholder-update`,
`medical-record`) create and append to instances; operations (`trip-prep`,
`status-synthesis`) read them.
