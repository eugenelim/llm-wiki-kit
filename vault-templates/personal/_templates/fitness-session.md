---
title: "{{Date}} — {{focus}}"
type: fitness-session
session_type: ""               # strength | cardio | mobility | hybrid
date: {{YYYY-MM-DD}}
duration_min: 0
program: ""                    # optional [[wikilink]] to active fitness-program
mesocycle: ""                  # e.g., "Hypertrophy block, week 2" (free-form)
focus: ""                      # e.g., "upper push", "zone-2 run", "yoga", "PR attempt"
location: ""                   # gym, home, trail, pool, etc.
energy_pre: 0                  # 1-5
energy_post: 0                 # 1-5
sleep_quality: 0               # 1-5 (last night)
soreness: 0                    # 1-5 (entering this session)
rpe: 0                         # session-level perceived exertion 1-10
prs_set: []                    # auto-populated by log-fitness-session if PRs were achieved
related_hobby: ""              # optional [[wikilink]] (running/climbing/etc. as a hobby)
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [fitness-session, {{session_type}}]
---

## Synopsis

{{One line: what this session was, how it went.}}

<!-- Pick the section(s) matching session_type. Drop the rest. -->

## Strength — Sets

| Exercise | Set | Weight | Reps | RPE | Notes |
|---|---|---|---|---|---|
| [[exercises/{{slug}}]] | 1 | | | | |
| [[exercises/{{slug}}]] | 2 | | | | |

<!-- Total volume (sets × reps × weight) and estimated 1RM auto-derived by the skill where possible. -->

## Cardio — Metrics

- Distance: {{km / mi}}
- Duration: {{HH:MM:SS}}
- Avg pace: {{min/km or min/mi}}
- HR avg / max: {{bpm}} / {{bpm}}
- HR zones: {{Z1: %, Z2: %, Z3: %, Z4: %, Z5: %}}
- Elevation: {{m / ft}}

### Splits

- {{km/mi 1}}: {{time}}
- {{km/mi 2}}: {{time}}

## Mobility — Focus

- Areas: {{e.g., hips, thoracic, hamstrings}}
- Style: {{yoga | foam roll | stretching | mobility flow}}

## Notes

{{What worked, what didn't, body cues, gear notes, weather (if outdoors), anything to remember.}}

## Next Time

{{Breadcrumb — if this session was part of a program, what's the next session in the plan? If standalone, what's the focus next time?}}
