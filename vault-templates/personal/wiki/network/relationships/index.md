---
type: index
title: Relationships
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [network, relationships, index]
---

## Synopsis

Personal network directory. One file per person at `wiki/network/relationships/{slug}.md` using the `_templates/person.md` schema. Covers professional peers, mentors, mentees, friends-with-career-overlap, recruiters, and connections you want to keep warm.

Specialized advisor relationships use `_templates/advisor.md` and live at `wiki/network/advisors/{slug}.md` — read by `skills/personal/networking-digest` alongside this folder.

## How to use

- **Capture a new person** — drop a LinkedIn URL, paste a conference intro email, or describe a new contact: the [[ingest-person]] skill creates the page.
- **Log an interaction** — after a coffee, call, or DM exchange, the [[person-update]] skill appends to `## Our Conversations` and bumps `last_contact:`.
- **Run the networking digest** — [[networking-digest]] reads this folder + advisors weekly/monthly and surfaces follow-ups owed, stale connections worth re-engaging, and conversations worth weaving into projects.

## Conventions

| `relationship:` | Meaning |
|---|---|
| `colleague` | Current or past coworker |
| `mentor` | Senior to you in some area; you go to them for advice |
| `mentee` | Junior to you in some area; they come to you for advice |
| `friend` | Personal friend with career overlap worth tracking |
| `community-peer` | Shared community/conference/online — peer-level |
| `recruiter` | External talent — internal recruiter, agency, sourcer |
| `intro` | Someone met once / via introduction; not yet a relationship |

Set `cadence_target:` (e.g., `quarterly`, `monthly`, `as-needed`) so networking-digest can flag when you've gone past the intended interval.

## Browse

A `relationships.base` view renders this folder grouped by `relationship:`, sortable by `last_contact:`, `cadence_target:`, and `company:`.
