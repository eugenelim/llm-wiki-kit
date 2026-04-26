---
title: "{{Exercise Name}}"
type: exercise
slug: {{slug}}
movement_pattern: ""           # squat | hinge | push | pull | carry | lunge | rotation | locomotion
modality: ""                   # barbell | dumbbell | machine | kettlebell | bodyweight | cardio
muscle_groups: []              # [quads, glutes, hamstrings, chest, back, shoulders, ...]
primary_metric: ""             # "weight × reps" (strength) | "distance × pace" (cardio) | "duration × hold" (isometric)
pr_estimated_1rm: 0            # current best estimated 1RM (strength only); auto-updated by log-fitness-session
pr_set_summary: ""             # "315×3 @ 2026-03-15" — most recent PR descriptor
sessions_count: 0              # cumulative count; auto-updated
last_session: ""               # YYYY-MM-DD; auto-updated
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [exercise, {{modality}}, {{movement_pattern}}]
---

## Synopsis

{{One line: what this exercise is and why you train it.}}

## PR History

<!-- log-fitness-session appends new PRs here, newest first. Format: date — weight×reps (estimated 1RM) — wikilink to session. -->

- {{YYYY-MM-DD}} — {{weight}}×{{reps}} (e1RM ~{{value}}) — see [[sessions/{{date}}-{{slug}}]]

## Form / Setup Notes

{{Cues, setup, what works for your body. Refresh as form evolves.}}

## Variations

{{Tempo, pause, paused, deficit, banded, etc. Useful for rotating stimulus.}}

## Programming Notes

{{Where this fits in your programming — frequency target, rep ranges that work, recovery demands.}}
