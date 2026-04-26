---
name: log-accomplishment
description: "Capture an accomplishment as it happens — career, craft, learning, network, health, finance, relationships, side-project, community, or personal-growth — into wiki/accomplishments/{date}-{slug}.md with dimension, impact level, evidence, and optional cross-links to projects/people/hobbies. Low-friction append-the-moment log; the discipline is to log when it happens, not at year-end. Use when the user says \"I just got promoted\" / \"log: shipped X\" / \"note this accomplishment: completed Y\" / \"log a win: ran my first half-marathon\" / \"add this to my accomplishments\". Asks for dimension if not obvious; defaults impact to meaningful. For routine hobby practice/sessions (no milestone) use log-hobby-session instead — that captures the activity; this captures the milestone. A milestone within a hobby (first 5K, first sent grade, finished knit) often warrants BOTH skills, with related_hobby cross-linking. Read by quarterly-review and annual-review which group reflections by dimension."
license: MIT
metadata:
  variant: personal
---

# Log Accomplishment Skill (Personal Variant)

Capture operation. The personal-OS analog of `person-update` and `ingest-bookmark` — a low-friction in-the-moment log that costs almost nothing to invoke and produces a durable artifact.

The discipline this skill encodes: **log accomplishments as they happen, not at year-end**. Recall is unreliable; the only retrospective worth its weight is one grounded in real-time records.

## When to Use

- A meaningful win just happened (promotion, ship, completion, recognition, milestone, threshold crossed)
- Catching up on a backlog of un-logged wins (batch mode)
- On request: "I just got promoted" / "log: shipped X" / "note this accomplishment: {what}" / "add a win"
- Not for: micro-moments that don't matter in a quarter (those don't need a wiki page); use a journal entry or skip

## Inputs

User provides:
- **What** — one sentence describing the accomplishment
- **Dimension** — `career` | `craft` | `learning` | `network` | `health` | `finance` | `relationships` | `side-project` | `community` | `personal-growth`. If not provided, ask.
- Optional: `date` — when it actually happened (default: today)
- Optional: `impact` — `micro` | `meaningful` | `significant` | `major` (default: `meaningful`)
- Optional: `evidence` — link, screenshot path, project wikilink, person who can vouch
- Optional: `related_project` and/or `related_person` — wikilinks for cross-graph navigation

Reads:
- `wiki/accomplishments/index.md` — for the dimension taxonomy and impact-level definitions
- `_templates/accomplishment.md` — the schema
- Existing `wiki/accomplishments/*.md` — to detect a likely-duplicate (same dimension + same week + similar headline)

## Algorithm

1. **Parse the user's intent.** Extract the headline, infer dimension where possible (e.g., "promoted" → `career`, "ran a half-marathon" → `health`, "shipped the auth service" → `craft`).
2. **Confirm dimension if ambiguous.** Surface 2-3 likely candidates; ask user to pick. Don't silently default for ambiguous cases — wrong-dimension allocation pollutes the review.
3. **Detect duplicates.** If a similar headline exists with `date:` in the last 7 days under the same dimension, surface and ask whether to merge / update instead.
4. **Apply the schema.** Fill `_templates/accomplishment.md` with the gathered fields. Generate slug from `{date}-{kebab-case-headline}`.
5. **Seed the body.** Auto-fill `## What` from the user's description. Leave `## Why It Matters`, `## Context`, and `## Evidence` for the user to enrich (or fill if the user provided enough detail in one shot).
6. **Set `status: logged`.** Quarterly-review marks entries as `reviewed-quarterly`; annual-review marks them as `reviewed-annually`.
7. **Cross-link.** If `related_project` or `related_person` is provided, also add a backlink from those pages (`## Recent Wins` section on the related person's page; `## Accomplishments` section on the related project's overview).
8. **Append a short reference to `wiki/accomplishments/index.md`** if the impact is `significant` or `major` — keeps the index a quick at-a-glance summary.

## Output

A new `wiki/accomplishments/{YYYY-MM-DD}-{slug}.md` file using the accomplishment template, with frontmatter populated and `## What` body filled.

## Side-effects

1. Append to `log/changelog.md`: "Logged accomplishment: [[{slug}]] (dimension: {x}, impact: {y})."
2. If `impact: major`, surface an inline reminder: "This is a major accomplishment — consider whether `career-narrative-refresh` should run now rather than at the next quarterly cadence."
3. If the user has a `wiki/portfolio/` and the dimension is `craft` or `career`, surface: "Should this be portfolio-eligible? Run `portfolio-add` (when defined) or note manually for the next refresh."

## Pairs With

- **[[quarterly-review]]** — reads `wiki/accomplishments/*.md` from the quarter; groups reflections by dimension; bumps `status:` to `reviewed-quarterly`.
- **[[annual-review]]** — reads the year's accomplishments, allocates one subsection per dimension, elevates `significant` + `major` to durable themes.
- **[[career-narrative-refresh]]** — reads `dimension: career` and `dimension: craft` accomplishments since the last refresh.
- **[[weekly-review]]** — can surface "what's worth logging?" by scanning the week's modified pages and meetings, then prompting the user to log any uncaptured wins.

## Failure Modes

- **No dimension and no signal to infer one.** Ask the user; don't guess. Wrong-dimension allocation breaks the review's per-dimension reflections.
- **Vague headline.** If the user types "log a win" with no detail, ask for the headline before creating the page. The page is worthless without specificity.
- **Duplicate detected.** Surface the prior entry with date and dimension; offer to update instead.
- **Backdated entries.** Allow `date:` in the past (catching up is fine), but warn if `date:` is more than 90 days before today — recall accuracy drops.

## Cadence

- **As-it-happens** — the right cadence. Log within a day of the event while it's fresh.
- **Weekly catch-up** — at the end of the weekly-review, ask: "Any wins this week not yet logged?"
- **Pre-quarterly** — before quarterly-review runs, confirm there's no major un-logged accomplishment.
