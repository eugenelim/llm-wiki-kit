---
type: index
title: People
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [people, index]
---

## Synopsis

Family people directory. One file per person at `wiki/people/{slug}.md` using the `_templates/person.md` schema. Covers immediate family, extended family, friends-the-family-knows, and recurring service providers (pediatrician, school principal, contractor, mechanic, etc.).

The medical, education, and finance pages cross-link **into** this folder rather than duplicating contact details.

## How to use

- **Capture a new person** — drop a contact card, paste an email signature, or describe in chat: the [[ingest-person]] skill creates the page.
- **Log an interaction** — after a doctor visit, parent-teacher conference, or contractor call, the [[person-update]] skill appends to the interaction log and bumps `last_contact:`.
- **Surface follow-ups** — [[follow-up-tracker]] scans `## Follow-ups` callouts across people pages alongside medical / vehicle / home schedules.

## Conventions

| `relationship:` | Meaning |
|---|---|
| `spouse` / `child` / `parent` / `sibling` | Immediate family |
| `extended` | Aunt, uncle, cousin, grandparent, etc. |
| `friend` | Family friends — adults the kids know, our friends, etc. |
| `provider` | Doctor, teacher, contractor, mechanic, lawyer, accountant — paid relationships |
| `neighbor` | Neighbors worth tracking |

For `provider` entries, fill in `service_type:` (e.g., `pediatrician`, `dentist`, `home-contractor`, `tax-preparer`). The medical-summary skill reads provider entries; the follow-up-tracker reads provider service-due dates.

## Browse

A `people.base` view at `wiki/people/people.base` renders this folder grouped by `relationship:`, with sortable `last_contact:`, `service_type:`, and `birthday:` columns.
