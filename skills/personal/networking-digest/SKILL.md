---
name: networking-digest
description: "Read meetings + relationships + advisors from the last 30-90 days; surface follow-ups owed (`## Things I've Promised` callouts), stale connections past their cadence_target, and recent conversations to weave into projects or decisions. Reads `wiki/network/relationships/*.md` and `wiki/network/advisors/*.md` (kept current via ingest-person + person-update). Use monthly, before active job search (job-search-prep reads relationships), before a conference/event where you might see past contacts, or on request: \"run my networking digest\"."
license: MIT
metadata:
  variant: personal
---

# Networking Digest Skill (Personal Variant)

Read meetings + relationships from the last 30-90 days. Surface follow-ups owed, stale connections that could use re-engagement, and recent conversations worth weaving into projects or decisions. Keep the network alive without performative outreach.

## When to Use

- Monthly (default cadence)
- Before active job search ([[job-search-prep]] reads relationships)
- Before a conference / event where you might run into past contacts
- On request: "Run my networking digest"

## Inputs

User provides:
- Optional: time window (default 90 days)
- Optional: focus filter (e.g., "engineering contacts only," "former colleagues only")

Reads:
- `wiki/meetings/*.md` from the last 90 days — recent conversations
- `wiki/network/relationships/*.md` — per-person pages with `last_contact:` field
- `wiki/career/applications/*.md` with `status: active` — applications where network leverage might help
- Recent decisions in `wiki/decisions/` — context for re-engagement framing
- Recent projects — to surface "things worth sharing" with contacts

## Algorithm

1. **Categorize relationships.** For each `wiki/network/relationships/{person}.md`, compute days-since-last-contact. Bucket:
   - **Active** (contact in last 30 days)
   - **Recent** (30-90 days)
   - **Stale** (90-365 days)
   - **Lost** (>365 days; harder to revive without specific reason)
2. **Detect follow-ups owed.** Scan recent meetings for explicit action items where the user owes something — "I'll send the deck," "I'll introduce you to X," "I'll think about this." If the corresponding action hasn't shipped (no matching changelog entry, no reply meeting), it's owed.
3. **Detect re-engagement moments.** For stale contacts, look for triggers: a recent project the user shipped that's relevant to the contact's interests (per their relationship-page tags); a book the contact recommended that the user finished; a public talk the contact would care about.
4. **Surface application leverage.** For active applications, identify any contact at the target company who could referral, or any contact who works at a similar company and could give context.
5. **Compose the digest.** Categorized, with specific recommended actions per person.

## Output

Write `wiki/log/networking-digest-{YYYY-MM-DD}.md` (one-off, overwritten on next run unless retained):

```yaml
---
type: networking-digest
status: current
created: {today}
modified: {today}
tags: [networking, digest]
window_days: 90
---
```

Body sections:
- `## Synopsis` — counts (active / recent / stale / lost) + key recommendations
- `## Follow-ups Owed` — actions you committed to that haven't shipped, per person
- `## Stale But Worth Re-engaging` — stale contacts with a specific reason to reach out (recent project, book, talk)
- `## Application Leverage` — contacts at companies you're applying to
- `## Recent Highlights` — meaningful conversations from the last 30 days that should weave into projects, decisions, or other follow-ups

Each person mentioned has a wikilink to their relationship page.

## Side-effects

1. **Update `wiki/log/networking-digest-index.md`** (or just overwrite the digest as a single living page).
2. **Update relationship pages** when re-engagement happens (the digest is the *plan*; the actual outreach updates `last_contact:`).
3. **Append to `log/changelog.md`**: "Networking digest: {N} follow-ups owed, {M} stale but reach-able."

## Interactive Review

```
Networking digest — {YYYY-MM-DD} (90-day window):

Follow-ups owed (3):
  1. Sarah — promised the Kafka talk slides (last meeting: 2026-03-15)
     → Action: send before Friday
  2. Maria — promised intro to Jake re: platform-engineering role (2026-04-02)
     → Action: send the email today
  3. Alex — said you'd think about co-authoring the post (2026-04-10)
     → Action: respond yes/no

Stale but worth re-engaging (4):
  1. Diego (last contact: 2025-12-04, 5 months) — shipped event-driven post in Jan;
     you just finished a project that builds on it. Easy reach-out: "I built X
     using the pattern from your post; here's what I learned."
  2. Priya (last contact: 2025-11-15, 5 months) — moved to platform team at {company}
     where you're applying. Context request before submitting?
  3. {Person} — long-stale; you read the book they recommended; share takeaway
  4. {Person} — long-stale; you have a project that intersects with their work

Application leverage (2 active applications):
  Acme Platform Engineer:
    → Sarah works there (active relationship); messaged about referral 2026-04-23
    → Priya formerly there; ask for interview-process context

Recent highlights worth weaving in:
  - Conversation with Maria 2026-04-02 surfaced a research direction
    → Consider: atomic note + addition to wiki/topics/distributed-systems-design

Apply suggested actions or adjust?
```

## Failure Modes

- **`wiki/network/relationships/` is sparse.** First-time use; no relationship pages built yet. Suggest authoring a starter set from frequent meeting attendees.
- **Meetings page references people without relationship pages.** Surface as a hygiene flag — those contacts deserve their own pages so future digests work better.
- **No follow-ups owed but many stale contacts.** Healthy state for the action-items axis; surface the re-engagement opportunities at lower priority.

## Cadence

- **Monthly:** Most useful at month-end or month-start.
- **Pre-search:** Run before any [[job-search-prep]] to maximize network leverage.
- **Scheduled:** A Cowork task on the first Sunday of each month works well.
