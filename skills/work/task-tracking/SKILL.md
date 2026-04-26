---
name: task-tracking
description: "Lightweight task management within the wiki, per project. Each project gets a tasks.md tracking tasks by assignee, status (Open / In Progress / Done), and priority. Use when adding/updating tasks, asking \"what's on @sarah's plate?\" / \"show me the task board for {project}\", or extracting action items from meeting notes. When the team outgrows this (5-6+ people, sprint reporting needs), move to a PM tool."
license: MIT
metadata:
  variant: work
---

# Task Tracking Skill (Work Variant)

Lightweight task management within the wiki, per project. Tracks tasks
by assignee, status, and priority without requiring an external PM tool.

## When to Use

- Teams that want all project context in one place (wiki + tasks)
- Before a PM tool is adopted, or for small projects that don't need one
- Alongside a PM tool, as a local mirror for Claude Code session awareness
- For tracking action items that emerge from meeting notes and decisions

## Structure

Each project gets a `tasks.md` file:

```
wiki/projects/{project-slug}/
├── overview.md
├── tasks.md          ← Project task board
├── specs/
├── design/
└── ...
```

### tasks.md format

Frontmatter + Synopsis + per-status sections (Open / In Progress / Done):

```markdown
---
type: tasks
project: order-platform
created: {date}
modified: {date}
tags: [tasks, order-platform]
provenance: mixed
---

## Synopsis

Task board for the order-platform project. 3 open, 2 in progress, 8 done.
Next deadline: schema validation spec review (Apr 28).

## Open
- [ ] **[HIGH]** Write integration tests for DLQ handling
  Assignee: @sarah · Due: 2026-04-30
  Context: [[specs/order-ingestion-service#implementation-plan]]

## In Progress
- [ ] **[HIGH]** Implement canonical model transformation
  Assignee: @eugene · Started: 2026-04-23
  Context: [[specs/order-ingestion-service]] — step 4 of implementation plan
  Notes: Blocked on schema finalization. See [[meetings/2026-04-24-standup]]

## Done
- [x] **[MED]** Add Schema Registry integration
  Assignee: @eugene · Completed: 2026-04-23
  Context: [[specs/order-ingestion-service]]
```

## Operations

### Add a Task

When asked to add a task (or when extracting action items from meeting
notes, decisions, or specs):

```
"Add a task to order-platform: write integration tests for the DLQ,
 high priority, assign to Sarah, due April 30"
```

1. Open `wiki/projects/order-platform/tasks.md`
2. Add the task under **Open** with priority, assignee, due date
3. Link to the context page (spec, meeting, decision) that created it
4. Update the Synopsis with new counts
5. Update `modified:` date

### Update a Task

Move between sections as state changes:
- **Open → In Progress:** add `Started: {date}`
- **In Progress → Done:** change `[ ]` to `[x]`, add `Completed: {date}`

Update the Synopsis counts after each change.

### Show Tasks by Person

```
"What's on Sarah's plate across all projects?"
```

1. Scan `tasks.md` in all active project folders
2. Filter for tasks assigned to @sarah
3. Group by project, sorted by priority
4. Report open and in-progress tasks with due dates

### Show All Tasks for a Project

```
"Show me the task board for order-platform"
```

1. Read `wiki/projects/order-platform/tasks.md`
2. Present the Synopsis (counts by status)
3. List open and in-progress tasks with context links

### Extract Tasks from Meeting Notes

When ingesting meeting notes that contain action items:

1. Identify action items (look for: "action:", "TODO:", "assigned to",
   "@name will", "by {date}", decisions that require follow-up)
2. For each action item, add a task to the project's `tasks.md`
3. Link the task back to the meeting note
4. Note in the meeting synthesis that tasks were created

### Sync with Feature Specs

A spec's unchecked implementation-plan items are effectively tasks. The task board can reference spec steps via the `Context:` line. When a spec step is completed during a Claude Code session, update both the spec's implementation plan AND the task board.

## Cross-Project Task View

For a team-wide view, create a Bases view at the wiki root:

```
wiki/
├── all-tasks.base        ← Bases view across all project tasks
├── projects/
│   ├── order-platform/
│   │   └── tasks.md
│   └── auth-service/
│       └── tasks.md
```

The `.base` file filters for `type: tasks` pages and displays a
unified table. See the `obsidian-bases` skill for syntax.

## When to Use a PM Tool Instead

This skill is for lightweight tracking. Move to Linear/Jira/Plane when:
- Team grows beyond 5-6 people
- You need sprint velocity, burndown charts, or reporting
- Multiple stakeholders need visibility without vault access
- You need workflow automation (auto-assignment, SLA tracking)

The PM sync skill can then pull external tool status into the wiki,
replacing or supplementing this local task board.
