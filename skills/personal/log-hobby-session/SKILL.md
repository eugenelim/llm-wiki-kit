---
name: log-hobby-session
description: "Capture a hobby session — practice, outing, attempt, study time — into wiki/hobbies/{slug}/sessions/{date}-{focus}.md with date, focus, duration, mood, and \"next time\" breadcrumb. Updates the hobby's overview.md (## Recent Sessions, ## Next Time, modified) so resumption is frictionless. If the named hobby doesn't yet exist, scaffolds the folder + overview using _templates/hobby.md. Use when the user says \"log: 30 min guitar practice\" / \"session: ran 5K\" / \"logged a climb — sent a 5.10b\" / \"hobby session for {hobby}\". For milestone wins (first 5K, first sent grade, finished knit) ALSO use log-accomplishment with related_hobby set — sessions track practice, accomplishments track milestones."
license: MIT
metadata:
  variant: personal
---

# Log Hobby Session Skill (Personal Variant)

Capture operation. Low-friction in-the-moment session log for any hobby. The personal-OS analog of `person-update` and `log-accomplishment`: a small, append-the-moment skill that produces a durable session record + keeps the hobby hub page current.

The discipline this skill encodes: **always end a session with a breadcrumb.** "Next time, start by ____." This is the single biggest lever against context-switching friction when you next pick the hobby up.

## When to Use

- Right after a session — practice, outing, attempt, study time, run, climb, cook, draw
- On request: "log: {duration} {hobby} — {focus}" / "session: {hobby} {summary}" / "log a hobby session for {hobby}"
- Not for: micro-touches that don't represent a real session (skip those — daily-notes journaling is the right tool)
- Not for: milestone wins — those go to [[log-accomplishment]] with `related_hobby:` set. A session can both log AND trigger a milestone — capture both.

## Inputs

User provides:
- **Hobby** — name or slug (e.g., "guitar", "climbing", "spanish"). The skill resolves to the right hobby folder.
- **Focus** — one line: what you worked on this session
- Optional: `duration_min` — minutes
- Optional: `location` — gym, home, trail, kitchen, etc.
- Optional: `mood` — `energized` | `flat` | `grinding` | `flow` | `frustrated`
- Optional: `what_worked`, `what_didnt`, `next_time` — body content; the user often supplies these inline
- Optional: `date` — defaults to today

Reads:
- `wiki/hobbies/index.md` — for the category taxonomy
- `wiki/hobbies/{slug}/overview.md` — the hobby hub (must exist or be scaffolded)
- `_templates/hobby-session.md` — session schema
- `_templates/hobby.md` — hobby hub schema (used for scaffolding new hobbies)

## Algorithm

1. **Resolve the hobby.** Match by slug → folder name → fuzzy name match across `wiki/hobbies/`. If multiple matches, ask. If no match:
   - Surface: "No hobby '{name}' found. Scaffold a new one? (category: {best-guess based on context}, status: active)"
   - On confirm: create `wiki/hobbies/{slug}/overview.md` from `_templates/hobby.md` with `started: today` and `current_focus:` seeded from the session's focus.
   - Then proceed with the session log.
2. **Generate the session file.** Slug = `{YYYY-MM-DD}-{kebab-case-focus}`. Path = `wiki/hobbies/{slug}/sessions/{slug}.md`. Apply `_templates/hobby-session.md` with the gathered fields.
3. **Seed the body.** Auto-fill `## What I Did` from the user's description. If `what_worked` / `what_didnt` / `next_time` were provided inline, fill those. Otherwise leave for human enrichment.
4. **Update the hobby's overview.md.**
   - Append `- {date}: {focus} — see [[sessions/{slug}]]` to `## Recent Sessions` (keep the section to last 5 entries; older entries live in the sessions folder + `.base` view).
   - If `next_time` was provided, replace the hobby's `## Next Time` breadcrumb.
   - Bump `modified:` to today.
5. **Surface the breadcrumb.** If `next_time` wasn't provided, ask: "What's the breadcrumb for next time?" Don't silently skip — this is the discipline.
6. **Detect milestone candidates.** If the user's description contains threshold-crossing language ("first", "PR", "sent", "completed", "finished", "leveled up"), surface: "Sounds like a milestone — also log this as an accomplishment? (dimension: {inferred}, related_hobby: [[{slug}]])". Don't auto-create — the user decides.

## Output

A new `wiki/hobbies/{slug}/sessions/{date}-{focus}.md` file. The hobby's `overview.md` updated in place.

If the hobby was scaffolded, also a new `wiki/hobbies/{slug}/overview.md`.

## Side-effects

1. Append to `log/changelog.md`: "Hobby session logged: [[{slug}]] — {focus} ({duration_min}m)."
2. If a hobby was scaffolded: also: "Hobby scaffolded: [[hobbies/{slug}]] (category: {x})."
3. If a milestone was confirmed: trigger [[log-accomplishment]] inline.
4. If the hobby's `## Next Time` was updated, the next time the user opens that hobby they see the breadcrumb at the top.

## Pairs With

- **[[log-accomplishment]]** — milestone wins within a hobby. Set `related_hobby:` on the accomplishment to cross-link.
- **[[weekly-review]]** — reads recent sessions per hobby; surfaces "this week: 3 climbing sessions, 2 piano practices."
- **[[quarterly-review]]** — surfaces hobbies with no sessions in the quarter (dormant candidates).
- **[[annual-review]]** — hobby trajectory across the year (which grew, which atrophied, any new ones).

## Failure Modes

- **Hobby ambiguous (multiple matches).** Ask. Don't silently pick.
- **Hobby doesn't exist.** Offer to scaffold; don't silently create. The user might have meant a different name.
- **Empty focus.** "What did you work on?" — the focus is the title; without it the session is unsearchable.
- **Missing breadcrumb.** Prompt for `## Next Time` rather than skipping. The whole point of the skill is breadcrumb discipline.
- **Backdated session.** Allow `date:` in the past (catching up is fine), but warn if more than 30 days back.

## Cadence

- **As-it-happens** — the right cadence. Log within the same day while the breadcrumb is fresh.
- **End-of-week catch-up** — the weekly-review can prompt: "Any hobby sessions this week not yet logged?"
