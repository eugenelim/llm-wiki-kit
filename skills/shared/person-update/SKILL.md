---
name: person-update
description: "Log an interaction with someone we already know — append a brief note to the person's interactions log, bump last_contact, and optionally add a follow-up callout. Reads the existing person page and updates in place. Use when the user says \"log a coffee with @sarah\" / \"update Jane's page after our 1:1\" / \"track this call with Dr. Patel\" / \"after-meeting update for @mark — add a follow-up\". For first-time capture of a NEW person use ingest-person; for project-context meeting capture use ingest-meeting (work) — that skill calls person-update as a side-effect for each attendee."
license: MIT
metadata:
  variant: shared
---

# Person Update Skill

Maintenance operation. Append a brief interaction entry to an existing person's page, bump `last_contact:`, and optionally add a follow-up callout that the variant's tracker scans (request-tracker for work, follow-up-tracker for family, networking-digest for personal).

Distinct from [[ingest-person]] (first-time capture) and [[ingest-meeting]] (full meeting synthesis with decisions / action items). person-update is the lightweight, one-liner-per-touch operation.

## When to Use

- After a brief interaction (coffee, call, DM exchange, hallway chat) that's worth logging but doesn't warrant a full meeting note
- After a doctor visit, parent-teacher conference, or contractor visit — log the touch on the provider's page
- When the user says "log this conversation with @them" / "after our chat with @them, update their page" / "add a follow-up on @their page"
- As a side-effect of [[ingest-meeting]] (work) — that skill iterates attendees and runs person-update for each, linking the meeting note

## Inputs

User provides:
- Person identifier — wikilink, name, or @handle (the skill resolves to the right page)
- Interaction summary — one or two sentences ("had coffee, talked about her new role at Acme")
- Optional: explicit date (default: today)
- Optional: a follow-up to add ("I'll send her the Kafka post by Friday" → renders as a `> [!important]` callout)
- Optional: a topic tag for filtering by networking-digest

Reads:
- The person's existing page at the variant's path (`wiki/people/{slug}.md` for work/family, `wiki/network/relationships/{slug}.md` or `wiki/network/advisors/{slug}.md` for personal)
- `_variant/CLAUDE.variant.md` — to know the variant's interaction-section name (`## Recent Interactions` / `## Our Conversations` / `## Notes`)

## Algorithm

1. **Resolve the person.** Match by wikilink → exact filename → fuzzy name match across the variant's people folder. If multiple matches, ask. If no match, propose [[ingest-person]] instead.
2. **Open the page.** Read the current frontmatter and section structure.
3. **Append the interaction.** To the variant's interactions section:
   - **Work:** `## Recent Interactions` — `- {date}: {summary} — see [[meetings/...]]` (if linked to a meeting)
   - **Family:** `## Notes` (or a `## Recent Visits` subsection for providers)
   - **Personal:** `## Our Conversations` — same shape as work
4. **Bump `last_contact:`.** Update frontmatter to today (or the explicit date the user provided).
5. **Update `modified:`.** Standard frontmatter rule.
6. **Add follow-up callout (if provided).** Place under the page's `## Follow-ups` (family) / `## Open Asks` (work) / `## Things I've Promised / Owe` (personal) section using the variant's standard pattern. The trackers scan these.
7. **Cross-link.** If the interaction was a real meeting captured elsewhere, add the wikilink. If the user mentions a project, decision, or topic, add a tag.
8. **Surface a confirmation.** Print: "Updated [[{person}]]: last_contact → {date}, +1 interaction, +{N} follow-ups."

## Output

In-place update to the existing person page. No new files unless the user explicitly asks for a separate meeting note (in which case route to [[ingest-meeting]] for work, or just leave the summary on the person page for family/personal).

## Side-effects

1. Append to `log/changelog.md`: "Updated person: [[{slug}]] — {summary truncated to 80 chars}."
2. If a follow-up was added, the variant's tracker (request-tracker / follow-up-tracker / networking-digest) will surface it on its next run.
3. (Personal) If `cadence_target:` was being missed and this update brings it back into spec, networking-digest's next run will reflect the recovery.

## Pairs With

- **[[ingest-person]]** — capture path for new people; person-update is the maintenance complement.
- **[[ingest-meeting]]** *(work)* — full meeting synthesis. Best practice: ingest-meeting calls person-update for each attendee so meeting context flows into people pages automatically.
- **[[networking-digest]]** *(personal)* — reads `last_contact:` + interaction logs; person-update keeps both fresh.
- **[[follow-up-tracker]]** *(family)* — reads follow-up callouts on people pages alongside medical/vehicle/home schedules.
- **[[request-tracker]]** *(work)* — reads `## Open Asks` callouts on people pages.

## Failure Modes

- **Person not found.** Surface: "No person matching '{input}' in {variant-path}. Did you mean {nearest match}? Or run [[ingest-person]] to add them."
- **Multiple matches.** Surface candidates with disambiguating context (company, team, last_contact) and ask.
- **Page exists but has no interactions section.** Add the section in the variant's standard position (after `## Synopsis`).
- **Stale page (last_contact > 1 year, status not dormant).** After update, surface: "This person's last contact was 14 months ago. Consider updating `status:` to `active` (already done) or revisiting `cadence_target:`."

## Cadence

On demand — runs after each interaction worth logging. Treat as low-friction: the longer entries (full meeting notes) belong in `wiki/meetings/`; person-update is the one-liner that keeps the people graph alive.
