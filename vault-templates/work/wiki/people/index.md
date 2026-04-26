---
type: index
title: People
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [people, index]
---

## Synopsis

Cross-project rolodex of people we work with — internal teammates across teams, cross-team partners, external vendors, customers, recruiters, and advisors. One file per person at `wiki/people/{slug}.md` using the `_templates/person.md` schema.

`wiki/projects/{slug}/team.md` is the per-project roster — it links **into** this folder rather than duplicating person details.

## How to use

- **Capture a new person** — drop a business card photo, paste a LinkedIn URL, or forward a recruiter intro: the [[ingest-person]] skill creates the page.
- **Log an interaction** — after a meeting or call, the [[person-update]] skill appends to the person's interaction log and bumps `last_contact:`.
- **Surface open asks** — [[request-tracker]] scans the `## Open Asks` section across people pages and weekly returns what's due / overdue.

## Conventions

| `relationship:` | Meaning |
|---|---|
| `team-member` | Internal teammate, same team |
| `cross-team` | Internal, different team |
| `external-vendor` | External — supplier, contractor, agency |
| `customer` | External — buyer / user representative |
| `recruiter` | External — talent / hiring |
| `advisor` | External or internal — formal/informal mentor |
| `partner` | External — partnership, joint work |

`status:` is `active` | `dormant` | `left-company`. Once a teammate moves on, set `status: left-company` rather than deleting — past collaboration history stays useful.

## Browse

A `people.base` (Obsidian Bases) view at `wiki/people/people.base` renders this folder grouped by `relationship:` with sortable `last_contact:` and `team:` columns.
