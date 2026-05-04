---
name: archive-done-tasks
description: "Move completed tasks from a project's tasks.md Done section into monthly archive files (wiki/projects/{slug}/archive/tasks-YYYY-MM.md), keeping the active task board focused on open and in-progress work. Groups tasks by their Completed: date; tasks with no date land in the current month. Run on request: \"archive done tasks for {project}\" / \"clean up the {project} task board\" / \"move done tasks to archive\" / \"archive all done tasks\". Scope to one project, a list, or all projects. Pairs with extract-accomplishments (reads the archive) and task-tracking (manages the live board). Not a delete operation — archiving preserves full history."
license: MIT
metadata:
  variant: work
---

# Archive Done Tasks Skill (Work Variant)

Housekeeping operation for the task board. Moves all `- [x]` items from
a project's `tasks.md` Done section into a monthly archive file, grouped
by the month in each task's `Completed:` field. Keeps the active board
focused on open and in-progress work; preserves the full done history in
queryable archive files that `extract-accomplishments` can read.

## When to Use

- After a sprint or milestone, when the Done section has grown longer
  than one screen
- Before running `extract-accomplishments` — clean archives improve coverage
- On request: "archive done tasks for {project}" / "clean up {project}'s
  task board" / "move done tasks to archive" / "archive all done tasks"

## Inputs

User provides:
- **Project** — one project slug, a comma-separated list, or `all` (prompt if
  not stated; default to all if the user says "archive all done tasks")
- **Confirm** — show a preview before executing (default: yes)

Reads:
- `wiki/projects/{slug}/tasks.md` — the active task board
- Existing `wiki/projects/{slug}/archive/tasks-YYYY-MM.md` — to append rather
  than overwrite

## Algorithm

1. **Locate tasks.md.** If `all`, enumerate `wiki/projects/*/tasks.md`. For a
   named slug or list, open only those files.
2. **Parse Done section.** Extract all `- [x]` task blocks from `## Done`. Each
   block spans from the `- [x]` line through all indented continuation lines
   (stop at the next `- [x]` or a `## ` heading).
3. **Assign month.** For each task, parse the date from `Completed: YYYY-MM-DD`.
   If absent, assign to the current month and note the default in the archive.
4. **Group by month.** Bucket tasks into `YYYY-MM` keys.
5. **Preview (if confirm: yes).** Show before writing:
   ```
   Archive preview for order-platform:
     2026-04: 5 tasks → archive/tasks-2026-04.md (new)
     2026-05: 2 tasks → archive/tasks-2026-05.md (new)
   Proceed? [y/n]
   ```
6. **Duplicate guard.** For each task about to be inserted, check the target
   archive file for an existing entry with the same title (strip priority
   marker `**[HIGH]**` / `**[MED]**` / `**[LOW]**` and whitespace before
   comparing). Skip and warn if a match is found:
   ```
   Skipped (already archived): "Implement canonical model transformation"
   ```
7. **Write archive files.** For each month bucket, create or append to
   `wiki/projects/{slug}/archive/tasks-YYYY-MM.md`. Create the `archive/`
   folder automatically if absent. Append tasks under a `## Done — {Month YYYY}`
   heading. If that heading already exists in the file, append below its last
   existing task entry.
8. **Update tasks.md.** Remove the archived tasks from the `## Done` section.
   Update Synopsis counts (recount Open / In Progress / Done). Update `modified:`.
9. **Changelog.** Append to `log/changelog.md`:
   "Archived {N} done tasks from {project}/tasks.md → {archive file list}."

## Archive File Format

```markdown
---
type: task-archive
project: {project-slug}
period: YYYY-MM
created: YYYY-MM-DD
modified: YYYY-MM-DD
provenance: extracted
tags: [tasks, archive, {project-slug}]
---

## Synopsis

Done tasks archived from [[../tasks]] for {Project Name} — {Month YYYY}.
{N} tasks completed this month. Earliest: {date}. Latest: {date}.

## Done — {Month YYYY}

- [x] **[HIGH]** Implement canonical model transformation
  Assignee: @eugene · Completed: 2026-04-22
  Context: [[../specs/order-ingestion-service]]

- [x] **[MED]** Add Schema Registry integration
  Assignee: @sarah · Completed: 2026-04-23
  Context: [[../specs/order-ingestion-service]]
```

Archive files live at:
```
wiki/projects/{project-slug}/
├── tasks.md                       ← Active: Open + In Progress only
└── archive/
    ├── tasks-2026-04.md
    └── tasks-2026-05.md
```

If new months appear in a future archive run, they append as additional
`## Done — {Month YYYY}` sections within the correct monthly file.

## Failure Modes

- **No Done section or Done section is empty.** Surface: "No completed tasks
  in {project}/tasks.md — nothing to archive." Treat as success (no-op).
- **tasks.md missing for a named project.** Surface: "{project} has no
  tasks.md — skipping." Continue with remaining projects.
- **Completed: date malformed or missing.** Default to current month; annotate
  the archived task with `(date missing — defaulted to {YYYY-MM})`.
- **All tasks in Done already exist in archive** (duplicate guard fires on
  everything). Warn: "All Done tasks for {project} appear to already be
  archived. No changes made."

## Pairs With

- **[[task-tracking]]** — manages the live board; archive-done-tasks cleans it up
- **[[extract-accomplishments]]** — reads the archives this skill produces

## Cadence

- **Sprint-end:** Archive before planning the next sprint.
- **Monthly:** Prevent the Done section from spanning multiple months.
- **Pre-report:** Run before `extract-accomplishments` for full coverage.
