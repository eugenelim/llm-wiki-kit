---
name: career-narrative-refresh
description: "Read recent projects, portfolio additions, decisions, and reviews; propose updates to the career narrative so the brand story stays current. Use quarterly after a quarterly-review surfaces narrative-relevant themes, after a major project ships that changes self-description, before any job-search activity, or on request: \"refresh my career narrative\"."
license: MIT
metadata:
  variant: personal
---

# Career Narrative Refresh Skill (Personal Variant)

Read recent projects + portfolio additions + decisions + reviews; propose updates to the career narrative. Keep the brand story living so when an interview or referral conversation happens, the version on hand is current.

## When to Use

- Quarterly (default) — after each quarterly review surfaces narrative-relevant themes
- After a major project ships that changes how you'd describe yourself
- Before any job-search activity ([[job-search-prep]] reads the narrative)
- On request: "Refresh my career narrative"

The most common failure mode of solo-maintained career narratives is staleness — version 2 from 2024 doesn't reflect current strengths in 2026. Make narrative refresh recurring; the operation makes it cheap.

## Inputs

User provides:
- Optional: target shift or angle to emphasize
- Optional: target version label (e.g., "ic-engineer" vs. "tech-lead")

Reads:
- Most recent narrative at `wiki/career/narrative/` — the current canonical
- All `wiki/projects/*/overview.md` modified or completed in the last 6 months
- `wiki/portfolio/` — recent additions
- `wiki/reviews/quarterly/*.md` — last 1-2 quarterly reviews (for theme continuity)
- `wiki/decisions/*.md` from the last 6 months that have career relevance
- `wiki/career/skills/*.md` — current skill state

## Algorithm

1. **Read the current narrative.** Capture its claims about who you are, what you do, what you're known for, where you're going.
2. **Inventory recent evidence.** Projects shipped, talks given, writing published, decisions made, themes that recurred. These are the new facts.
3. **Identify drift.** What does the current narrative claim that recent evidence contradicts (e.g., "I focus on event-driven systems" but you spent 6 months on RAG)? What's missing (a major project not yet woven in)?
4. **Identify amplification.** What does recent evidence make a stronger version of than the narrative currently expresses?
5. **Propose updates.** Three categories:
   - Replace — outdated claims
   - Add — new strengths surfaced by recent work
   - Sharpen — claims that are correct but vague
6. **Preserve voice.** Don't rewrite for rewriting's sake. Keep the user's phrasing where it's still right.

## Output

Write a versioned narrative page at `wiki/career/narrative/{YYYY-MM-DD}-{label}.md`:

```yaml
---
title: "Career Narrative — {Label}"
type: narrative
status: active
provenance: synthesized
created: {today}
modified: {today}
tags: [career, narrative]
supersedes: "[[career/narrative/{previous-version}]]"
---
```

Body sections:
- `## Synopsis` — what changed since the previous narrative (audit, not just preamble)
- `## Who I Am` — short identity statement (1-2 sentences)
- `## What I Do` — current focus + skills emphasized
- `## What I'm Known For` — recurring themes others attribute to you
- `## Recent Evidence` — projects, portfolio pieces, talks, writing supporting the claims
- `## Where I'm Heading` — direction signal for the next 12-24 months
- `## Tailoring Hints` — angles to emphasize when this narrative needs to be tailored for a specific audience (e.g., for engineering-leadership roles emphasize X; for IC roles emphasize Y)

Mark the previous version as `status: outdated` and add a `superseded_by:` frontmatter pointer.

## Side-effects

1. **Update `wiki/career/narrative/index.md`** with the new version listed.
2. **Cross-link from recent portfolio entries and projects** that the narrative now cites.
3. **Trigger [[job-search-prep]] readiness check** — if active applications exist, surface that their tailored materials may need updating against the new narrative.
4. **Append to `log/changelog.md`**: "Career narrative refreshed: [[career/narrative/{...}]]."

## Interactive Review

This operation is heavily collaborative — the narrative is *your* voice, not the agent's. Present:

```
Career narrative refresh — {YYYY-MM-DD}:

Current narrative (v{previous}, last refreshed {date}):
  "I'm a senior platform engineer focused on event-driven systems and observability."

Recent evidence (last 6 months):
  - Shipped Kafka observability talk (peer-reviewed at conference)
  - Built personal site v2 (public)
  - 12 atomic notes on RAG architecture
  - Decision to decline platform-engineering role; stayed IC
  - Quarterly themes: writing-as-practice + event-driven thinking

Proposed updates:
  REPLACE:
    "focused on event-driven systems and observability"
    →
    "focused on event-driven systems, observability, and the operational
     practices that make them maintainable; writing publicly about both"

  ADD:
    "Increasingly known for explaining complex distributed-systems work
     to mid-career engineers — through talks, the personal site, and
     atomic-note synthesis."

  SHARPEN:
    "where I'm heading" — replace vague "next steps in technical leadership"
    with "deeper focus on principal-level IC work; staying close to the
     code while raising the abstraction of the writing"

Preserve the rest verbatim?
```

The user accepts, adjusts wording, or sends specific changes back.

## Failure Modes

- **Recent evidence is sparse.** A 6-month window with little activity means there's nothing to refresh against. Note this; suggest waiting until evidence accumulates rather than producing a forced update.
- **Multiple narrative versions exist (already-tailored).** If the user has IC-narrative AND tech-lead-narrative versions, refresh each separately. Don't merge unless requested.
- **Voice mismatch risk.** The skill should never invent claims; it proposes adjustments backed by evidence. If a proposed claim has no wiki-backed evidence, flag and surface for user confirmation.

## Cadence

- **Quarterly:** After each quarterly review.
- **On demand:** Before any job-search-prep run.
- **No scheduled runs:** Narrative refresh is a deliberate moment, not a cron.
