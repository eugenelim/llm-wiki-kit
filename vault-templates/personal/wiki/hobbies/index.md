---
type: index
title: Hobbies
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [hobbies, index]
---

## Synopsis

Hobby hub. One folder per hobby at `wiki/hobbies/{slug}/`, each with an `overview.md` (the hub page) and a `sessions/` folder for individual practices/outings/sessions. Cold-storage hobbies (`status: dormant`) stay in place rather than getting moved — the `.base` view filters them out by default.

## Folder pattern

```
wiki/hobbies/
├── index.md                       # this file
├── hobbies.base                   # MOC view (active hobbies + recent sessions)
├── {hobby-slug}/
│   ├── overview.md                # type: hobby — the hub page
│   ├── sessions/                  # type: hobby-session — one per practice/session/outing
│   │   └── {YYYY-MM-DD}-{slug}.md
│   ├── projects/                  # optional — sub-projects within the hobby
│   │   └── {slug}.md
│   └── _assets/                   # photos, recordings, screenshots
```

## How to use

- **Log a session** — `log-hobby-session` skill: "log: 30 min guitar practice, worked the Bach trill section" / "session: ran 5K in 28:30, felt strong" / "logged a climb — sent a 5.10b at the gym today". Creates the session file under the right hobby; updates the hobby's `## Recent Sessions` and `## Next Time` breadcrumb. If the hobby doesn't yet exist, scaffolds it.
- **Promote a milestone to an accomplishment** — when a session crosses a threshold (first 5K, first sent grade, finished knit), use `log-accomplishment` with `related_hobby:` set. The session captures the practice; the accomplishment captures the milestone for retrospective synthesis.
- **Browse** — `hobbies.base` renders this folder grouped by `category`, with active hobbies surfaced and dormant ones filterable.

## Categories

| Category | Examples |
|---|---|
| `physical` | Running, climbing, cycling, weightlifting, yoga, martial arts, swimming, hiking |
| `creative` | Music-making, writing, drawing, painting, photography, woodworking, knitting, ceramics |
| `learning` | Language, history, philosophy, ongoing self-study without external goal |
| `collecting` | Records, books, plants, coins, watches, observation lists |
| `gaming` | Video games, board games, TTRPGs, puzzles, chess |
| `culinary` | Cooking, baking, brewing, mixology, fermentation, BBQ |
| `nature` | Gardening, birdwatching, fishing, foraging, naturalist field-work |

The taxonomy is user-extensible — add a new value to `category:` and the reviews + `.base` view pick it up.

## Practices

- **Breadcrumb at the end of each session.** `## Next Time` on the session AND on the hobby's overview. The single biggest lever against context-switching friction when you next pick the hobby up.
- **Update `current_focus:` when it shifts**, not on every session. The hub page is the at-a-glance status; the session is the journal entry.
- **Prune via status, not deletion.** A hobby that goes 6+ months without a session: `quarterly-review` surfaces it; you decide whether to set `status: dormant` (parked, may resume) or `status: done` (no longer pursuing). Keep the page either way — past hobbies are part of the trajectory.
- **Milestone accomplishments live in the accomplishments log**, not the hobby page. Each milestone is a `wiki/accomplishments/{date}-{slug}.md` with `dimension:` (usually `craft` for creative, `health` for physical, `learning` for learning hobbies) and `related_hobby:` for the cross-link.
- **Skill ladders for hobbies that have them.** Climbing grades, language levels, instrument pieces — make `## Skill / Progression` explicit. Skip the section for hobbies without ladders.
