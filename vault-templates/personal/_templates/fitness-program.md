---
title: "{{Program Name}}"
type: fitness-program
slug: {{slug}}
period: "{{YYYY-MM}}..{{YYYY-MM}}"   # macrocycle window
goal: ""                              # strength | hypertrophy | endurance | body-comp | mobility | sport-specific
status: active                        # active | completed | paused
periodization: ""                     # linear | undulating | block | conjugate | none
weekly_frequency: 0                   # planned sessions per week
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
current_mesocycle: ""                 # e.g., "Hypertrophy block (weeks 1-4)"
current_microcycle: ""                # e.g., "Week 3"
related_hobby: ""                     # optional — if this program serves a hobby (e.g., training plan for the marathon hobby)
tags: [fitness-program, {{goal}}]
---

## Synopsis

{{One paragraph: what this program is, why now, what success looks like at the end of the macrocycle.}}

## Macrocycle Goal

{{The big-picture outcome — "add 30 lbs to back squat 1RM," "complete a sub-25 5K," "drop 8 lbs while preserving strength," "rebuild base after injury."}}

## Mesocycles

<!-- Each mesocycle: 4-6 weeks, focused adaptation. End with a deload week. -->

### Mesocycle 1 — {{focus}} (weeks 1-{{4|5|6}})

- Goal: {{specific adaptation}}
- Volume / intensity: {{landmark — e.g., "8-12 reps, RPE 7-9, 4 sessions/week"}}
- Key indicator lifts: {{the 3-5 movements you grade progress on}}
- Deload: {{week {{4|5|6}} — reduced volume, intensity at 60-70%}}

### Mesocycle 2 — {{focus}} (weeks {{X-Y}})

- ...

## Weekly Template

<!-- The microcycle layout. Day-of-week → session focus. -->

- Mon: {{focus}}
- Tue: {{focus}}
- Wed: {{focus or rest}}
- Thu: {{focus}}
- Fri: {{focus}}
- Sat: {{focus or long session}}
- Sun: rest / mobility

## Indicator Lifts / Benchmarks

<!-- The 3-5 things that signal whether the program is working. -->

- [[exercises/{{slug}}]] — start: {{baseline}} | target: {{end-of-program}}

## Notes

{{Why this periodization style, anchor references, lessons from past programs.}}
