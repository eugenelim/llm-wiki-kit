---
name: ingest-meeting
description: "Capture a meeting transcript (paste, URL, or file) into a structured wiki/projects/{slug}/meetings/{YYYY-MM-DD}-{topic}.md page with decisions and action items extracted as first-class fields. Use when the user says \"ingest this meeting\", a paste starts with speaker labels (`Sarah:`, `@eugene:`, timestamps `[00:01:23]`), or a file comes from Granola, Otter, Fireflies, Zoom, Google Meet, or Teams."
license: MIT
metadata:
  variant: work
---

# Ingest Meeting Skill

Specialized content-type ingester for meeting transcripts. Composes a source-type ingester (`ingest-website` for cloud-hosted notes like Granola or Otter, `ingest-document` for PDF exports, paste handling for inline transcripts) with meeting-schema extraction. Output: a structured `wiki/projects/{slug}/meetings/{YYYY-MM-DD}-{topic-slug}.md` page using the `_templates/meeting-synthesis.md` schema, with decisions and action items extracted as first-class fields.

## When to Use

The orchestrator (`skills/shared/ingest.md`) routes here when:

- The user says "ingest this meeting" with pasted text, a URL, or a file
- A pasted text starts with speaker labels (`Sarah:`, `@eugene:`, timestamps like `[00:01:23]`)
- A file is named `meeting-*.md` or comes from a known transcript provider (Granola, Otter, Fireflies, Zoom, Google Meet, Teams)

## Composition (two-axis routing)

This is a content-type ingester. Common compositions:

| Source | Source-type cleanup | Result |
|---|---|---|
| Pasted transcript text | none — handle directly | raw transcript |
| Granola / Otter / Fireflies URL | [[ingest-website]] (defuddle by default; pure.md fallback) | clean markdown of the cloud notes |
| PDF export of meeting summary | [[ingest-document]] (Docling) | clean markdown of the PDF |
| `.md` file dropped into `raw/` | none — already markdown | raw transcript |

After cleanup, this skill applies the meeting schema regardless of source.

## Inputs

After source-type cleanup:

1. **The cleaned-up transcript or summary** — speaker labels, timestamps, dialogue, AI-generated summary if the source was Granola / Otter / Fireflies.
2. **The project context** — either passed by the user ("the order-platform meeting") or inferred from speakers / topic / explicit reference in the transcript. If unclear, ask.
3. **`wiki/projects/{project-slug}/overview.md`** — current state, active specs, current sprint goal.
4. **Active specs** in `wiki/projects/{project-slug}/specs/` — to cross-reference decisions and action items against existing implementation work.
5. **Recent ADRs** in `wiki/projects/{project-slug}/decisions/` — to detect when a meeting decision should be elevated to an ADR.
6. **The meeting template** — `_templates/meeting-synthesis.md` for the target schema.

## Algorithm

1. **Identify participants.** From speaker labels in the transcript. If the transcript provides only first names, cross-reference with `wiki/team.md` if maintained.
2. **Identify the meeting type.** Sprint planning, design review, retro, 1:1, standup, escalation, etc. Infer from context (calendar event title if present, opening exchanges, agenda items mentioned).
3. **Extract decisions.** Look for explicit markers: "we decided", "agreed to", "let's go with", "the call is", "we'll proceed with". For each decision: what was decided, who decided, why (the rationale stated in the meeting).
4. **Extract action items.** Look for: "action: ...", "TODO: ...", "{name} will ...", "by {date}", "{name} owns ...". For each: assignee, action, due date if stated, context.
5. **Extract key discussion topics.** Topics debated but not yet decided. Capture trade-offs surfaced, positions taken, alternatives considered.
6. **Extract open questions.** Things that surfaced during the meeting that need follow-up before they can be decided.
7. **Extract information shared.** Specific facts, data points, references mentioned. These feed the fact-tracking skill if active.
8. **Detect ADR-worthy decisions.** A decision is ADR-worthy if it (a) affects more than the immediate spec, (b) has long-term architectural implications, or (c) was contentious. Flag for the user during interactive review; don't auto-create ADRs.

## Output

Write `wiki/projects/{project-slug}/meetings/{YYYY-MM-DD}-{topic-slug}.md` using the meeting-synthesis template:

```yaml
---
title: "{Meeting Title}"
type: meeting
project: {project-slug}
date: {YYYY-MM-DD}
participants: [{first-names}]
created: {today}
modified: {today}
provenance: synthesized
sources:
  - raw/{project-slug}/meeting-transcripts/{YYYY-MM-DD}-{topic}.md
tags: [meeting, {meeting-type}, {project-slug}]
related_specs: []
related_adrs: []
---
```

Body sections (per the meeting-synthesis template):

- `## Synopsis` — 1-2 sentences: meeting type, key decisions or themes, scope
- `## Decisions` — each as a bullet with rationale; cross-link to ADRs if elevated
- `## Action Items` — each formatted as `- [ ] **{Owner}** — {Action} (due {date})`; these become tasks in the project's tasks.md
- `## Key Discussion` — sub-headings per topic, with the contour of debate
- `## Open Questions` — bullet list
- `## Information Shared` — bullet list of facts and references
- `## Cross-References` — links to project overview, active sprint plan, related design pages

## Side-effects

1. **Save the raw transcript** to `raw/{project-slug}/meeting-transcripts/{YYYY-MM-DD}-{topic}.md` (the source-of-truth original).
2. **Add action items to the project's tasks.md** via the [[task-tracking]] skill. Each action item becomes a task with assignee and due date.
3. **Surface ADR-worthy decisions for human review.** If a decision crosses the ADR-worthiness threshold (per the algorithm), flag during interactive review and ask whether to author an ADR. Don't auto-create — ADRs need deliberate authorship.
4. **Update referenced spec pages.** If the meeting decided something that affects an active spec, append to that spec's Current State section noting the decision.
5. **Append to fact log if active.** If `domains/{topic}.facts.md` exists for any topic mentioned, append new facts.
6. **Append to `log/changelog.md`**: "Meeting ingested: [[projects/{slug}/meetings/{date}-{topic}]]."

## Interactive Review

Before writing, present the extraction to the user:

```
Meeting ingested: Sprint Review for order-platform on 2026-04-25
Participants: Eugene, Sarah, Jake
Type: Sprint review

Decisions extracted (3):
1. Use KRaft mode instead of ZooKeeper for the new Kafka cluster.
   → Likely ADR-worthy (architectural, cross-spec). Author ADR?
2. Postpone DLQ monitoring spec to next sprint to focus on
   schema-registry integration.
3. Sarah owns schema-registry integration; Jake stays on DLQ.

Action items extracted (5):
- [ ] Sarah — finalize schema-registry spec (due 2026-04-29)
- [ ] Eugene — resolve ADR-007 in week 1 (due 2026-04-30)
- [ ] Jake — investigate DLQ alerting options (due 2026-05-02)
- [ ] Sarah — pair with Jake on DLQ integration tests (due 2026-05-05)
- [ ] Eugene — update kafka-architecture-v2 page after KRaft decision
       (due 2026-04-28)

Open questions:
- Should we keep ZooKeeper for the staging cluster during transition?
- Who should review the schema-registry spec besides Sarah?

Save meeting page? Author the flagged ADR?
```

The user confirms or redirects. ADR creation is a separate decision; ingest-meeting flags but doesn't auto-create.

## Failure Modes

- **No clear speakers.** Transcript doesn't have speaker labels (rare with modern AI tools; common with manual notes). Ask the user to confirm participants.
- **Project not identifiable.** Multiple projects discussed, or no clear project context. Ask the user.
- **No decisions or action items.** Pure status / info-sharing meeting. Save the synthesis without those sections; don't fabricate.
- **Cross-project meeting.** Affects multiple projects. Save once under the most-relevant project, but cross-reference from other affected projects' overviews.
- **Sensitive content.** HR meeting, performance discussion, vendor negotiation. Confirm the user wants this in the wiki at all; if so, restrict the wiki page's tags so it doesn't surface in cross-project queries.
- **AI-summary already provided** (Granola, Otter). Use the AI summary as a starting point but verify against the full transcript; don't rely solely on the summary.

## Cadence

- **On demand:** After each meeting that produced decisions or action items.
- **Pairs with `weekly-digest`:** Every meeting ingested becomes a candidate entry in the weekly digest.
- **Pairs with `sprint-planning`:** Recent meeting decisions feed into sprint planning.
