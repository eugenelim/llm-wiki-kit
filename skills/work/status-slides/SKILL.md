---
name: status-slides
description: "Convert a structured status source (typically a team-status page, but also any milestone/project status markdown) into a best-practice executive PowerPoint deck. Standard slide structure: title, executive summary, RAG dashboard, top risks, open issues, asks/decisions needed, what's next. Uses scripts/build_slides.py with python-pptx. Use after team-status produces the markdown source, before a steering committee or leadership review, or on request: \"create status slides for {project}\" / \"produce the steering committee deck\" / \"build slides from this status page\". For markdown-only status (Slack, wiki, email) you don't need this skill — team-status produces the markdown directly."
license: MIT
compatibility: "Requires Python 3.10+ and python-pptx (pip install python-pptx)."
metadata:
  variant: work
---

# Status Slides Skill

Output operation. Given a structured status markdown source, generate a best-practice executive PowerPoint deck. The slide structure is opinionated — it follows the patterns most leadership audiences expect (title, exec summary, RAG, risks, issues, asks, next).

Composes with `team-status` (which produces the source markdown), but accepts any markdown that follows the canonical four-section convention: **Progress, Risks, Issues, Asks**.

## When to Use

- After `team-status` produces a markdown status page that needs to be presented as a deck
- Before a steering committee, leadership review, or cross-org program review
- On request: "create status slides for {project}" / "build the steering committee deck"

For markdown-only audiences (Slack thread, wiki link, email body), skip this — `team-status` produces shareable markdown directly.

## Inputs

User provides:
- `--source` — path to a team-status markdown page, or wikilink, or pasted status content
- `--output` — `.pptx` output path (default: `outputs/{date}-{slug}-status.pptx`)
- `--theme` — `default` (clean executive) | `technical` (detail-heavy) | `minimal` (tight density)
- `--audience` — `internal` | `leadership` | `steering-committee` | `customer` (affects what's included)
- `--template` — optional brand-styled `.pptx` to start from

Reads:
- The source page — extracts sections by `## ` heading
- Any `## Progress` table — converts to RAG dashboard
- `wiki/projects/{slug}/overview.md` (when applicable) — for project name and owners
- Optional brand template at `assets/template.pptx` if the team has standard slides

## Best-Practice Slide Structure

The script generates this 7-slide canonical deck (with audience-conditional inclusion):

| # | Slide | Source section | Notes |
|---|---|---|---|
| 1 | Title | frontmatter / overview | Project, period, audience, presenter |
| 2 | Executive Summary | `## Synopsis` | 2-3 bullets max; RAG headline |
| 3 | RAG Dashboard | `## Progress` table | Workstream / RAG / one-line update; RAG cell colors auto-applied |
| 4 | Top Risks | `## Risks` | Structured RISK-* cards: ID, probability×impact icon, title, owner, proximity, one-line mitigation. Falls back to bullet list for unregistered callouts. Cap 3-5 for leadership, 8 for internal. |
| 5 | Open Issues | `## Issues` | Structured ISSUE-* cards: severity icon + ID, title, owner, ETA, status. Critical/high → individual cards; medium → one grouped bullet; low → count only. Falls back to bullet list for untriaged callouts. **Dropped for `customer` audience**. |
| 6 | Asks / Decisions Needed | `## Asks` | Most-important slide for leadership; decisions with owners and dates |
| 7 | What's Next | `## What's Next` | Next 2-4 weeks |

Audience tailoring (handled by the script):
- **leadership / steering-committee:** slides 1, 2, 3, 4, 6 emphasized; 5, 7 condensed.
- **customer:** drop slide 5 (Issues); reframe Risks as "watch items."
- **internal:** all slides; full detail; appendix when overflow.

## Severity / Probability Color Tokens

Consistent across `team-status` markdown output and slide rendering:

| Level | Markdown icon | Slide swatch (RGB) |
|---|---|---|
| critical / high impact | 🔴 | `#D32F2F` |
| high probability | 🟠 | `#F57C00` |
| medium | 🟡 | `#FBC02D` |
| low | ⚪ | `#9E9E9E` |

## Tooling: scripts/build_slides.py

Python script using `python-pptx`. Parses the source markdown by `## ` heading, maps sections to slide layouts, applies theme, writes the `.pptx`.

### Setup (one time)

```bash
pip install python-pptx
```

### Usage

```bash
python scripts/build_slides.py \
  --source wiki/projects/order-platform/status/2026-04-25-team-status.md \
  --output outputs/2026-04-25-order-platform-status.pptx \
  --theme default \
  --audience leadership
```

The script:
1. Parses frontmatter + sections from the source markdown.
2. For each canonical section, builds the corresponding slide.
3. Applies theme (font sizes, colors, RAG cell coloring).
4. Writes the `.pptx`.

If a section is missing, the slide is generated with a `[FILL IN]` placeholder rather than failing — humans review the deck before sharing.

## Algorithm

1. **Validate source.** Confirm at least the four canonical sections exist (Progress, Risks, Issues, Asks). If missing, ask the user to confirm or run `team-status` first.
2. **Pick theme + audience.** Defaults: `default` / `leadership`.
3. **Run the script.** Pass source, output, theme, audience, optional template.
4. **Surface review hooks.** Print: "Generated {output} ({n} slides). Review before sharing — flag any [FILL IN] placeholders, verify RAG colors, double-check Asks slide language."

## Output

A `.pptx` at `outputs/{date}-{slug}-status.pptx`.

## Side-effects

1. Append to `log/changelog.md`: "Status slides produced: {output} from {source}."
2. Add a wikilink to the deck from the source status page's frontmatter (`deck:`).

## Pairs With

- **team-status** — primary upstream; produces the source markdown.
- **request-tracker** — secondary; its escalation output feeds team-status's Asks section, which becomes the Asks slide here.

## Failure Modes

- **python-pptx not installed.** Surface install instruction.
- **Source markdown lacks structure.** If sections aren't found, propose generating from `team-status` first; do not fabricate content.
- **Brand template not found.** Fall back to default theme; surface a warning.
- **Audience-inappropriate content.** If `audience=customer` but Issues contains internal-only language, flag and ask the user to review/redact before generating.
- **Too many risks/issues for one slide.** Default cap at 5 per slide for leadership audiences; overflow surfaces a recommendation to add an appendix or move to internal-audience tailoring.

## Future

- **Slide diff mode:** Given two team-status pages (this week vs. last), highlight what changed on each slide.
- **Per-stakeholder templates:** Auto-pick the brand template based on audience (board template, exec template, customer template).
