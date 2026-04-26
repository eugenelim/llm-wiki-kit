---
name: log-fitness-session
description: "Capture a structured fitness session — strength (sets×reps×weight×RPE), cardio (distance/pace/HR/zones), mobility (focus/duration), or hybrid — into wiki/fitness/sessions/{date}-{slug}.md. Auto-detects PRs (compares to each exercise's pr_estimated_1rm), updates the canonical exercise pages with new PR history entries, and refreshes wiki/fitness/pr-summary.md. Use when the user says \"log: squat 5×5 @ 225, RPE 8\" / \"ran 5K in 28:30, zone 2\" / \"30 min yoga, hips\" / \"lifted today: bench 185×3, OHP 115×5\". For hobby-as-narrative logging (running as identity, climbing community, gym story) use log-hobby-session — that captures activity narrative, this captures structured metrics. For body weight + measurements (state, not activity) use log-body-metric. A PR session can both log fitness data AND surface as an accomplishment via log-accomplishment with dimension: health."
license: MIT
metadata:
  variant: personal
---

# Log Fitness Session Skill (Personal Variant)

Capture operation. Structured per-modality session log that maintains canonical exercise pages, detects PRs automatically, and seeds the data for periodization-aware reviews.

The discipline this skill encodes: **track what matches your goal, log immediately, let the canonical exercise pages accumulate.** Sessions are the daily artifact; exercises are the long-term record; PRs are the natural milestones.

## When to Use

- Right after a workout — strength, cardio, mobility, or hybrid session
- On request: "log: {exercise} {weight}×{reps}" / "ran {distance} in {time}" / "{duration} {modality} session" / "log fitness: {free-form}"
- Not for: hobby-as-narrative entries (use [[log-hobby-session]]) — fitness sessions are the structured-metrics layer

## Inputs

User provides (all optional but at least one of session_type / focus needed):
- **Session type** — `strength` | `cardio` | `mobility` | `hybrid`. Auto-inferred from content if not stated.
- **Focus** — one line ("upper push", "zone-2 run", "hips + thoracic")
- Optional: `program` — wikilink to active fitness-program if one exists
- Optional: `mesocycle` / `microcycle` markers
- **Strength sessions:** list of `(exercise, set, weight, reps, RPE)` tuples. The user may write inline: `squat 5×5 @ 225 RPE 8` → 5 sets of 5 reps at 225 lb, RPE 8.
- **Cardio sessions:** distance, duration, avg pace, HR avg/max, HR zone distribution (if available), elevation, splits.
- **Mobility sessions:** duration, focus areas, style.
- **Recovery context:** `energy_pre`, `energy_post`, `sleep_quality`, `soreness`, session-level `rpe` — all 1-5 (1-10 for `rpe`).
- Optional: `related_hobby` — wikilink if this session also belongs to a hobby narrative
- Optional: `date` — defaults to today

Reads:
- `wiki/fitness/index.md` — for the goal-type taxonomy and modality conventions
- `wiki/fitness/exercises/{slug}.md` — current PRs per exercise (read for comparison)
- `wiki/fitness/programs/*.md` (status: active) — for periodization context
- `_templates/fitness-session.md`, `_templates/exercise.md`

## Algorithm

1. **Parse the user's input.** Detect session type from content cues:
   - "squat / bench / deadlift / OHP / row / curl / press × @ RPE" → `strength`
   - "ran / cycled / swam / km / mi / pace / zone" → `cardio`
   - "yoga / stretch / mobility / foam roll" → `mobility`
   - mix of two or more → `hybrid`
2. **Resolve exercises.** For strength sessions, match each exercise name to a canonical page in `wiki/fitness/exercises/`. If no match, scaffold a new exercise page from `_templates/exercise.md` (asking the user to confirm `movement_pattern` + `modality`).
3. **Compute derived metrics (strength).**
   - **Total volume** per exercise: `Σ (set_weight × set_reps)`.
   - **Estimated 1RM (e1RM)** per top set: Epley formula `weight × (1 + reps/30)`. Use the highest e1RM for PR comparison.
4. **Detect PRs.** For each exercise in this session, compare top-set e1RM to the exercise's `pr_estimated_1rm`:
   - If new e1RM > existing → PR. Add to session's `prs_set:` and append a new entry to the exercise's `## PR History` (newest first).
   - Update the exercise's `pr_estimated_1rm` and `pr_set_summary`.
   - Refresh `wiki/fitness/pr-summary.md` with the updated row.
   - Bump exercise's `sessions_count` and `last_session`.
5. **Generate the session file.** Slug = `{date}-{focus-or-summary-slug}`. Path = `wiki/fitness/sessions/{slug}.md`. Apply `_templates/fitness-session.md` with the gathered fields. Drop sections that don't match `session_type:`.
6. **Surface PR-as-accomplishment for thresholds.** If a PR was set AND the user's input contains threshold language ("first", "PR", "new max", "broke", "finally"), surface: "This is a PR — also log as accomplishment? (dimension: health, related_program: [[{program}]] if active)". Don't auto-create — user decides.
7. **Surface program-context advice.** If the session is part of an active program with a deload week scheduled, and the user's input shows high RPE late in a mesocycle, surface: "You're in {meso} week {N}; consider whether to push or hold steady. Deload starts {date}."
8. **Write the breadcrumb.** `## Next Time` reflects the next planned session in the program (if any) OR asks the user. Don't silently skip — context-switching friction is the enemy.

## Output

A new `wiki/fitness/sessions/{date}-{slug}.md`. Updates to the affected `wiki/fitness/exercises/*.md`. Refresh of `wiki/fitness/pr-summary.md` if any PRs.

## Side-effects

1. Append to `log/changelog.md`: "Fitness session logged: [[{slug}]] ({session_type}, {duration_min}m{, PRs: N if any})."
2. If any PR was set, the next [[weekly-review]] surfaces it; if user confirms, [[log-accomplishment]] runs inline with `dimension: health` + `related_program:` cross-link.
3. If `related_hobby:` is set, a back-pointer is added to that hobby's `## Recent Sessions` — the hobby's narrative thread sees the structured session.

## Pairs With

- **[[log-hobby-session]]** — narrative layer for fitness as identity (running, climbing, lifting as hobbies). A session can be either or both, but don't auto-double-write — the user explicitly picks the layer.
- **[[log-accomplishment]]** — milestone PRs and threshold-crossings (first 5K, first sent grade, first bodyweight bench).
- **[[log-body-metric]]** — separate skill for weight + measurements; pairs with sessions for body-comp goal interpretation.
- **[[weekly-review]]** — surfaces session counts per modality, PRs this week, body-weight delta, weekly mileage, indicator-lift trends.
- **[[quarterly-review]]** — program completion, mesocycle progression, indicator-lift deltas, dormant-program check.
- **[[annual-review]]** — fitness trajectory: programs completed, PR summary, body trajectory, hobby-overlap.

## Failure Modes

- **Ambiguous exercise name.** "Bench" → barbell-bench-press? dumbbell-bench-press? incline? Ask. Don't silently pick.
- **Inconsistent units.** If `weight` is sometimes lbs and sometimes kg, the e1RM math breaks. Detect and warn; default to user's preferred unit declared in the most recent session.
- **Missing reps for a strength set.** Refuse to record the set; e1RM and volume require both. Ask.
- **Cardio with no distance OR duration.** Ask — at least one is needed for the session to be useful.
- **PR claimed but data doesn't support.** If user says "PR'd squat" but the entered weight×reps doesn't beat the current e1RM, surface the gap and confirm whether to record.
- **Active program out of phase.** If user logs a session that doesn't match the program's planned focus (e.g., heavy lifting on a deload week), surface but don't block — life happens.

## Cadence

- **As-it-happens** — log within the same day while details are fresh and breadcrumb is meaningful.
- **End-of-week catch-up** — the weekly-review can prompt: "Any sessions this week not yet logged?"
- **Weekly review:** scan recent fitness sessions for trends; surface PRs and indicator-lift movement.
