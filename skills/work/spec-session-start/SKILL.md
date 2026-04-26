---
name: spec-session-start
description: "Resume a Claude Code build session for a spec-driven project where it left off. Reads the project overview, active spec (status: in-progress), referenced ADRs and design pages, and verifies code-repo state matches the spec's last checkpoint. The work variant's most-used operation. Use at the start of every Claude Code session continuing implementation work on a spec, or on request: \"resume work on {project}\" / \"pick up the spec session\"."
license: MIT
metadata:
  variant: work
---

# Spec Session Start Skill

Resume a Claude Code build session from where it left off. The work variant's most-used operation — encodes the spec-driven development pattern that makes Claude Code build sessions actually continuous.

## When to Use

- Start of every Claude Code session that's continuing implementation work on a spec
- On request: "Resume work on the order-ingestion service" / "Pick up the spec session"

This skill is the planning operation that makes the spec-driven development pattern work. Without it, every Claude Code session restarts cold.

## Inputs

1. **Project context.** Either passed by the user ("the order-platform project") or inferred from the current working directory of the code repo.
2. **Project overview.** `wiki/projects/{project-slug}/overview.md` — the project brief, current state, key decisions.
3. **Active spec.** The spec in `wiki/projects/{project-slug}/specs/` with `status: in-progress`. If multiple, ask the user which to resume.
4. **Spec's full content.** All sections, with focus on Current State and Implementation Plan.
5. **Referenced ADRs.** Any ADR linked from the spec's frontmatter or body — read in full.
6. **Referenced design pages.** Any design page linked from the spec — read synopsis (depth 1), full read (depth 2) only if highly relevant to the next implementation step.
7. **The code repo.** Verify state matches the spec's last-recorded checkpoint (the spec's Current State should reference specific files / lines).

## Algorithm

1. **Identify the next step.** Read the spec's Implementation Plan; find the first unchecked item.
2. **Verify state matches the spec.** Open the relevant code files (referenced in the spec's Current State or in recent commit messages); confirm the previous step landed.
3. **Surface uncertainty.** If the code state doesn't match what the spec claims, surface this as a discrepancy — don't proceed assuming the spec is right.
4. **Load the right context.** Don't read every wiki page; use progressive loading. Load: the spec (full), referenced ADRs (full), referenced design pages (synopses + targeted), recent meetings tagged with this project (synopses).
5. **Produce a session-start summary.** What's being resumed, what was last done, what's next, what blockers exist.

## Output

This is a *runtime* operation — its primary "output" is the session being correctly oriented. Produce a brief markdown summary for the user:

```markdown
## Resuming: {Spec Title}

**Project:** {project-slug}
**Spec status:** {status}
**Last update:** {modified date}

**Previously completed:**
{bulleted list from Implementation Plan items marked [x]}

**Current step (resuming here):**
{the first unchecked Implementation Plan item}

**Referenced context loaded:**
- {ADR title} — {1-line summary}
- {Design page title} — {1-line summary}
- ...

**Open questions / blockers:**
{from spec's Current State or open-questions section}

Ready to proceed?
```

The user confirms or redirects, then implementation work begins.

## Side-effects

1. **Update spec's `modified` date** at session start to mark resumption.
2. (At session end, the spec-session-end operation captures state for the next session.)

## Interactive Confirmation

Always confirm with the user before starting implementation work:

- Is the right spec being resumed?
- Is the proposed next step still the right next step?
- Have decisions been made out-of-band that the spec doesn't reflect yet?

If the user redirects ("actually we decided to skip step 4 and go to step 6"), update the spec's Implementation Plan to reflect that before continuing.

## Failure Modes

- **No spec in `in-progress`.** The project may be between specs. Suggest: "Specs in `ready` are: {list}. Move one to `in-progress` before starting?" Or the user wants to start a fresh spec — route to a spec-creation skill.
- **Multiple specs in `in-progress`.** Ask the user which to resume; surface this as a hygiene flag (typically only one spec per assignee should be in-progress at a time).
- **Code repo state doesn't match spec.** Major discrepancy — possibly someone made commits the spec doesn't reflect, or the spec was updated without code changes. Don't proceed; surface to the user with specific file:line discrepancies.
- **Spec references missing pages.** Broken wikilinks to ADRs or design pages. Surface as a lint-style flag; either fix the links or proceed without.

## Cadence

- **Per session:** Run at the start of each Claude Code session that continues spec work.
- **Pairs with spec-session-end:** capture state at the end of each session; restore at the start of the next.
