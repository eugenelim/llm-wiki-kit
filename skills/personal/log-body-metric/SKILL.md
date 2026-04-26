---
name: log-body-metric
description: "Capture a body-metric snapshot — weight, body-fat percent (if measured), measurements (chest, waist, hips, etc.), plus subjective 1-5 averages for sleep, energy, and a soreness pattern note — into wiki/fitness/body/{date}.md. Use weekly for weight (recommended same-time-of-day), monthly for measurements, or on request: \"weighed in: 175.4 lbs\" / \"monthly measurements: waist 32.5, chest 42, hips 38\" / \"log body: 175.4 lbs, 16.8% BF, sleep avg 4 this week\". Read by quarterly-review and annual-review for body-trajectory analysis. For workout sessions use log-fitness-session — that captures activity; this captures state."
license: MIT
metadata:
  variant: personal
---

# Log Body Metric Skill (Personal Variant)

Capture operation. Lightweight body-state snapshot — separate from session logs because measurement cadence is different (weekly weight, monthly measurements) and the data is contextual to interpreting fitness sessions.

The discipline this skill encodes: **weigh and measure consistently, not exhaustively.** Same time of day for weight; monthly for measurements. The number is noise without trend; the trend is noise without context. Notes capture context.

## When to Use

- Weekly weigh-in (default cadence — same time of day, ideally morning post-bathroom pre-eating)
- Monthly body measurements (chest, waist, hips, thigh, arm)
- After a body-fat measurement (DEXA, BodPod, calipers, smart scale)
- On request: "weighed in: {n} lbs" / "log body: {n} lbs, {pct}% BF" / "monthly measurements: {fields}"
- Not for: per-session weight check; sessions are activity, body-metrics are state

## Inputs

User provides (any combination):
- `weight_lbs` or `weight_kg` — at least one for a weigh-in entry
- Optional: `body_fat_pct` — only if actually measured, not a smart-scale guess unless user trusts it
- Optional: `measurements` — sub-fields (`chest_in`, `waist_in`, `hips_in`, `thigh_in`, `arm_in`)
- Optional: `sleep_avg_last_7d` (1-5), `energy_avg_last_7d` (1-5), `soreness_pattern` (free-form short note)
- Optional: `date` — defaults to today
- Optional: contextual notes (travel, stress, illness, dietary changes, training block)

Reads:
- `_templates/body-metric.md`
- Most recent body-metric entries — for trend display

## Algorithm

1. **Parse the user's input.** Extract numeric fields. Detect units (lbs vs kg, in vs cm); store both `weight_lbs` and `weight_kg` (compute the conversion). Same for measurements (in vs cm).
2. **Detect the snapshot type.**
   - Weight only → quick weekly weigh-in
   - Measurements only → monthly snapshot
   - Both → typical end-of-month entry
   - With body-fat % → calls out a higher-precision measurement event
3. **Surface trend context.** Look up the prior 4 weeks of weight entries; show the delta (e.g., "Weight down 1.2 lbs over last 4 weeks (175.4 → 174.2)"). For measurements, show the delta vs last month.
4. **Write the snapshot.** Path = `wiki/fitness/body/{YYYY-MM-DD}.md`. Apply `_templates/body-metric.md` with the fields. Drop unprovided sub-fields rather than zero-filling them.
5. **Append context to Notes.** If the user provided contextual notes, place under `## Notes`. Examples: "post-vacation, expect bounce-back", "first week of cut", "started new program, expecting initial water retention".

## Output

A new `wiki/fitness/body/{date}.md` file.

## Side-effects

1. Append to `log/changelog.md`: "Body metric logged: {date} — weight {n} lbs{; +N measurements if any}."
2. If a goal of `body-comp` is active in any program, the next weekly-review highlights weight trend vs. program target.
3. If sleep / energy averages drop materially (≥1 point on 1-5 scale) week-over-week, surface in the next weekly-review as recovery context for adjusting upcoming sessions.

## Pairs With

- **[[log-fitness-session]]** — sessions are activity; body metrics are state. Both feed program interpretation.
- **[[weekly-review]]** — body weight delta surfaces here; trend chart lives in `wiki/fitness/fitness.base`'s body-metrics view.
- **[[quarterly-review]]** — body-comp trajectory; measurement deltas vs goal.
- **[[annual-review]]** — yearly body trajectory + correlation with program phases.

## Failure Modes

- **Wildly inconsistent weight.** If today's weight differs >5 lbs from last week, surface the gap and ask for context (post-meal? travel? illness?). Don't auto-flag as data error — body weight fluctuates — but make the noise visible.
- **No prior entries.** First entry: skip the trend display and surface "first body-metric entry; future entries will show trends."
- **Missing units.** "Logged 175" — lbs or kg? Ask. Don't guess from the number magnitude.
- **Measurements without weight.** Allowed — monthly measurements often happen apart from weigh-ins. Just write the partial snapshot.

## Cadence

- **Weight: weekly,** same time of day. Resist daily-weighing temptation unless cutting and tolerant of noise.
- **Measurements: monthly.** Quarterly is also fine if you don't have a body-comp goal active.
- **Body-fat %: as available.** DEXA quarterly or annually; calipers monthly if you trust your technique; smart-scale only if you trust the device.
