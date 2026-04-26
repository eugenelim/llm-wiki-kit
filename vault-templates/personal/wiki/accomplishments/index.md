---
type: index
title: Accomplishments
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [accomplishments, index]
---

## Synopsis

Append-the-moment accomplishments log. Each meaningful win — career, craft, learning, network, health, finance, relationships, side-project, community, personal-growth — gets a small page at `wiki/accomplishments/{YYYY-MM-DD}-{slug}.md` using the `_templates/accomplishment.md` schema.

The discipline: **log it when it happens, not at year-end**. Recall is unreliable; an in-the-moment log of "what I'm proud of this week" is the only durable input to a year-end retrospective that actually reflects what mattered.

## How to use

- **Log a win** — `log-accomplishment` skill: "I just got promoted" / "log: shipped the new auth service" / "completed AWS solutions architect cert" / "ran my first half-marathon". Creates the page; asks for `dimension` if not obvious.
- **Reflect by dimension** — `quarterly-review` and `annual-review` read `wiki/accomplishments/*.md` and allocate reflections per dimension. Each dimension gets its own subsection in the review.
- **Browse** — `accomplishments.base` (Obsidian Bases) renders this folder grouped by `dimension`, sortable by `date` and `impact`.

## Dimensions

| Dimension | What lands here |
|---|---|
| `career` | Promotions, role changes, project launches at work, recognition, salary milestones |
| `craft` | Skill demonstrations — technical wins, design wins, writing published, talks given |
| `learning` | Knowledge acquisition — books finished and applied, courses, certifications, paper readings that shifted thinking |
| `network` | Relationship-building — intros made, mentorship moments, conferences, communities joined |
| `health` | Physical / mental health — fitness milestones, habits established, medical milestones, therapy work |
| `finance` | Financial milestones — savings, investments, debt paydown, financial habits |
| `relationships` | Partner / family / friend milestones |
| `side-project` | Non-work creative or technical work shipped, started, or published |
| `community` | Volunteering, civic, open-source contributions |
| `personal-growth` | Internal work — journaling streaks, therapy milestones, big realizations |

The taxonomy is user-extensible — add a new value to `dimension:` and the reviews will pick it up.

## Impact levels

- `micro` — a satisfying moment worth marking but not retrospective-worthy on its own
- `meaningful` — a clear step forward; will likely show up in a quarterly review
- `significant` — a milestone for the year; will likely anchor an annual-review section
- `major` — a defining accomplishment; rare; shows up in multi-year trajectory

Use `impact:` to let the reviews weight automatically — annual-review elevates `significant` + `major` to durable-themes, deprioritizes `micro` to a count.
