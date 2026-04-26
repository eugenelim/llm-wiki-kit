---
title: "{{Name}}"
type: person
status: active            # active | dormant | left-company
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [{{first-name-lowercase}}, {{team-or-company-tag}}]
relationship: ""          # team-member | cross-team | external-vendor | customer | recruiter | advisor | partner
team: ""                  # internal team name OR external team/company
role: ""
email: ""
slack: ""                 # @handle (or chat-tool equivalent)
last_contact: ""          # YYYY-MM-DD; updated by person-update + ingest-meeting
---

## Synopsis

{{One sentence: who they are in our context, what they own / decide / influence.}}

## Working With

<!-- The "how to collaborate" reference. Update as you learn. -->

- Communication style: {{e.g., async-preferred, prefers short Slack threads, reads email weekly}}
- Best channel: {{Slack DM | email | Zoom | in-person 1:1}}
- Decision authority: {{e.g., approves architecture decisions for order-platform; signs off on schema changes}}
- Escalation path: {{their manager / on-call / etc. when needed}}
- Collaboration notes: {{strengths, working preferences, things to be aware of}}

## Recent Interactions

<!-- Brief log; full notes live in wiki/projects/{slug}/meetings/. Cross-link to those. -->

- {{Date}}: {{topic}} — see [[projects/{{slug}}/meetings/{{date}}-{{topic}}]]
- {{Date}}: {{topic}} — see [[projects/{{slug}}/meetings/{{date}}-{{topic}}]]

## Open Asks

<!-- request-tracker scans these. Use the standard callout pattern. -->

> [!important] Waiting on @{{them}} by {{YYYY-MM-DD}}: {{ask}}
> Originally asked: {{YYYY-MM-DD}}. Context: [[...]]

> [!important] Owed back to @{{them}} by {{YYYY-MM-DD}}: {{ask}}
> Promised: {{YYYY-MM-DD}}. Context: [[...]]

## Projects We've Worked On

- [[projects/{{slug}}]] — {{their role on this project}}

## Background

{{Their career, prior context, areas of expertise. Just enough to remember between conversations.}}

## Notes

{{Private context, preferences, off-the-record observations, useful intros they've made, debts owed in either direction.}}
