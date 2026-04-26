---
name: onboarding-pack
description: "Given a new team member's role (and optional project), assemble a curated reading order across playbooks, domains, current projects, and key ADRs. Crisis-responding operation. Use for a new team member joining (engineer, architect, PM, designer, intern), a cross-team transfer, or on request: \"build an onboarding pack for {name}, joining as {role}\"."
license: MIT
metadata:
  variant: work
---

# Onboarding Pack Skill

Given a new team member's role, assemble a curated reading order across playbooks, domains, current projects, and key ADRs. Crisis-responding operation (the "crisis" being a new hire's first week with no idea where to start).

## When to Use

- New team member joining: software engineer, architect, PM, designer, intern
- Cross-team transfer: someone moving from one team to another
- On request: "Build an onboarding pack for {name}, joining as {role}"

This skill saves what is otherwise the most time-consuming part of onboarding — figuring out where the relevant docs are and in what order to read them.

## Inputs

1. **Role.** The new team member's role. Affects what's relevant: an engineer needs ADRs and specs; a PM needs strategy docs and project briefs; a designer needs design pages and approach docs.
2. **Specific project (optional).** If the new member is joining a specific project, narrow accordingly.
3. **The wiki.** Especially:
   - `wiki/playbooks/` — reusable methodologies (architecture review, spec format, sprint cadence)
   - `wiki/domains/` — cross-project domain knowledge
   - `wiki/projects/` — active projects' overviews
   - `wiki/tools/` — tool evaluations the team relies on
   - Key ADRs (project-level decisions a new member needs to know)
4. **Team page if maintained.** `wiki/team.md` — who's who, who owns what.

## Algorithm

1. **Map role to relevant content categories.** Engineers: heavy on specs, ADRs, code-relevant playbooks. PMs: project briefs, strategy, customer research. Designers: design pages, approach docs, brand / tone docs.
2. **Filter by recency.** Prefer recent / `active` content; deprioritize archived material.
3. **Sequence the reading.** Foundations first (what the team is, how it works), then current context (what's in flight), then deep references (read-as-needed).
4. **Estimate time.** Add a time estimate per item so the new member can budget their first week.
5. **Surface key people.** Who to talk to about what. The list complements the reading; some questions are better answered by a person.

## Output

Write `wiki/people/{first-name}/onboarding.md` (creating the person folder if needed):

```yaml
---
type: onboarding-pack
person: {first-name}
role: {role}
created: {today}
modified: {today}
tags: [onboarding, {first-name}]
status: active
---
```

Body sections:

- **`## Synopsis`** — 2-3 sentences. "Welcome, {Name}. As a {role} joining {project or team}, here's a reading order for your first 2 weeks."
- **`## Day 1 — orientation`** — small, fast: team page, current sprint plan, your project's overview. ~30 minutes total.
- **`## Week 1 — foundations`** — the playbooks and domains that explain how the team operates. Each item: wikilink, time estimate, why it matters.
- **`## Week 2 — current context`** — the active specs, in-flight ADRs, and recent meeting decisions on your project.
- **`## Reference (read as needed)`** — deeper material: tool evaluations, historical ADRs, archived projects with relevant patterns.
- **`## People to know`** — who owns what; suggested 1:1 cadence for the first month.

For each reading item:

```markdown
- [[playbooks/architecture-review-process]] (~15 min) —
  How we run architecture reviews. You'll be in one in your second week.
```

## Side-effects

1. **Update `wiki/team.md`** to add the new member.
2. **Update `wiki/people/{first-name}/overview.md`** (create if absent) with the basics.
3. **Append to `log/changelog.md`** noting the onboarding pack creation.

## Interactive Review

Before finalizing, review with the manager or sponsor of the new hire:

```
Proposed onboarding pack for Sarah (Senior Engineer, joining order-platform):

Day 1 (30 min):
- team.md
- projects/order-platform/overview.md
- projects/order-platform/delivery/sprint-2026-04-26.md (current)

Week 1 — foundations (~6 hrs):
- playbooks/spec-format
- playbooks/sprint-cadence
- playbooks/architecture-review-process
- domains/event-driven-architecture
- domains/kafka

Week 2 — current context (~4 hrs):
- specs/order-ingestion-service (in-progress; she'll pick up step 6)
- decisions/adr-003-kafka-over-rabbitmq
- decisions/adr-007-schema-evolution (currently draft)
- recent meetings (3)

People to know:
- Eugene (tech lead, order-platform) — weekly 1:1
- Jake (DLQ work) — pair on integration tests

Adjust scope or sequence?
```

The manager can adjust ("skip the Kafka deep-dive, she's already an expert"; "add the DLQ design page since she'll own it"), then save.

## Failure Modes

- **No matching playbooks for the role.** Probably the kit's first onboard for that role; flag for the user to author missing playbooks (which themselves become reusable for the next hire).
- **Project overview missing or out of date.** The pack is only as good as the underlying wiki; surface gaps as TODOs the team should address.
- **No team page.** Suggest creating one.
- **Excessive reading.** If the pack lands at >20 hours, trim the Reference section and surface only essentials. The new member can read more once they're oriented.

## Cadence

- **Per new hire / transfer:** Run once when each person joins.
- **Annually:** Refresh existing team members' packs as career progressions might change which content is relevant.
