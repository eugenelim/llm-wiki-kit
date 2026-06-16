# efforts/cases/

The **case** container registry. A case is a bounded thread of work or
care with its own identity and a start and an end: a medical episode (a
pregnancy, a surgery and its follow-ups, a chronic-condition workup), an
insurance claim, a legal matter, a household project. It is a **folder-mode**
container — each case is a folder `efforts/cases/<case>/` holding its pages
flat.

## Conventions

- **One folder per case.** `efforts/cases/<slug>/` — e.g.
  `efforts/cases/mei-2025-knee/`. The case's pages live **flat** inside it;
  the only permitted subfolder is a non-semantic bulk sink (`_assets/` for
  scans and letters, `_working/` for scratch).
- **Status is a property, not a folder.** `status: active | archived` lives
  in frontmatter; there is no `open/`/`closed/` subfolder.
- **People as wikilinks.** The patient, providers, and other people are
  node pages in `wiki/people/` (`subtype: person` / `vendor` for a clinic).
  The case folder holds the *case*, not the people.
- **Records link up with `parent:`.** An individual medical record is a
  `library/` capture that names its case with
  `parent: [[wiki/efforts/cases/<case>]]`.

## What goes in a case folder

- A case overview page (what this is, who's involved, current status).
- The bounded set of records, results, correspondence, and tasks for it.
- Cross-references to related cases.

## Created by other primitives

- `medical-record` ingester captures a record into `library/` and links it
  to its case here (stubbing the case folder + overview on first
  reference). Sensitive health data is opt-in (`wiki add`) — see the
  `medical-record` content-type.
