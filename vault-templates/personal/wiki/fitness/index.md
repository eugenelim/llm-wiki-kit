---
type: index
title: Fitness
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [fitness, index]
---

## Synopsis

Personal fitness layer — structured tracking for strength, cardio, mobility, and hybrid training, plus periodized programs, canonical exercise pages, and body metrics. Distinct from `wiki/hobbies/` (narrative): fitness here is the *data layer*; if running or climbing is also part of your identity, use `wiki/hobbies/{slug}/` for the story and cross-link with `related_hobby:` on sessions.

## Folder pattern

```
wiki/fitness/
├── index.md                    # this file
├── fitness.base                # MOC: recent sessions, current program, PRs, body trend
├── programs/                   # macrocycle + mesocycle plans
│   └── {YYYY}-{slug}.md        # type: fitness-program
├── sessions/                   # one per workout / run / mobility block
│   └── {YYYY-MM-DD}-{slug}.md  # type: fitness-session
├── exercises/                  # canonical exercise pages, accumulating PRs
│   ├── exercises.base
│   └── {slug}.md               # type: exercise
├── body/                       # weekly weight + monthly measurements
│   └── {YYYY-MM-DD}.md         # type: body-metric
└── pr-summary.md               # synthesized current-PRs reference (auto-updated)
```

## How to use

- **Log a session** — `log-fitness-session` skill. Detects modality from context: "log: squat 5×5 @ 225, RPE 8" → strength; "ran 5K in 28:30, zone 2" → cardio; "30 min yoga, hips" → mobility. Updates the relevant exercise pages with PRs achieved.
- **Log body metrics** — `log-body-metric` skill: "weighed in: 175.4 lbs" / "monthly measurements: waist 32.5, chest 42, hips 38". Creates a snapshot in `wiki/fitness/body/`.
- **Start a program** — copy `_templates/fitness-program.md` into `wiki/fitness/programs/{YYYY}-{slug}.md`, lay out mesocycles with deloads, declare your indicator lifts. Future sessions can reference the program via `program:` frontmatter.
- **Track PRs naturally** — every PR achieved during a session auto-appends to the relevant exercise's `## PR History` and bumps `pr_estimated_1rm:`. The `pr-summary.md` page is the at-a-glance reference.
- **Promote a PR to an accomplishment** — significant PRs (first 5K, first sent grade, first bodyweight bench, etc.) warrant an accomplishment entry too. `log-fitness-session` surfaces this for threshold-crossing PRs and offers `log-accomplishment` with `dimension: health` + `related_program:` cross-link.

## Best-practice principles applied

- **Modality-distinct schemas, one page type.** `fitness-session` discriminated by `session_type:` (`strength` / `cardio` / `mobility` / `hybrid`) so you don't have four templates with overlapping fields.
- **Canonical exercise pages.** Each exercise lives in one place; PRs accumulate over time; sessions link via wikilink. Mirrors the i-josh / kaylesworth Obsidian gym-log pattern.
- **Periodization is optional.** Macrocycle → mesocycle → microcycle → deload is supported via `fitness-program`, but not required. Standalone sessions with no `program:` are first-class.
- **Track what matches your goal.** Strength goals → 1RMs and total volume. Endurance goals → pace, distance, HR zones. Body-comp goals → weight + measurements. The frontmatter accommodates all but the reviews emphasize what your active program targets.
- **Subjective recovery on a 1-5 scale.** `sleep_quality`, `soreness`, `energy_pre/post` — captures readiness without requiring a wearable. If you have a wearable, paste the HRV / readiness score into Notes.
- **Cross-link to hobbies, don't duplicate.** Running as identity → `wiki/hobbies/running/`. Running as data → `wiki/fitness/sessions/`. The session's `related_hobby:` and the hobby's `## Resources` connect them. Pick one as primary; cross-link the other.

## Goal types

| Goal | Primary metrics | Secondary metrics |
|---|---|---|
| `strength` | 1RM / e1RM on key lifts; total volume | Bar speed, RPE distribution |
| `hypertrophy` | Total volume per muscle group; sets-to-failure proximity | Body measurements |
| `endurance` | Weekly mileage / time; pace at lactate threshold; zone-2 volume | HRV, easy/hard ratio |
| `body-comp` | Weight (weekly), measurements (monthly), photos | Strength preserved during cut |
| `mobility` | Frequency consistency; ROM benchmarks | Pain-free range, sport-specific positions |
| `sport-specific` | Sport-defined benchmarks (e.g., climbing grade, race time, lift total) | Supporting capacity |
