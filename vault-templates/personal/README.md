# Personal Vault — Knowledge & Career OS

A wiki + agent-driven operating layer for one person's mind and career. Atomic notes, books, projects, decisions, weekly reviews, hobby logs, fitness tracking, applications, network — all in plain markdown you own, kept current by Claude.

This README is **self-contained**. You don't need any other documentation to set up the vault and start using it.

---

## Table of Contents

- [What this vault gives you](#what-this-vault-gives-you)
- [Prerequisites](#prerequisites)
- [Setup — pick one path](#setup--pick-one-path)
- [Your first session](#your-first-session)
- [Capturing new content](#capturing-new-content)
- [Producing deliverables](#producing-deliverables)
- [Querying the vault](#querying-the-vault)
- [Folder map](#folder-map)
- [Authoring rules in 30 seconds](#authoring-rules-in-30-seconds)
- [Health checks](#health-checks)
- [Going further](#going-further)
- [Privacy and safety](#privacy-and-safety)

---

## What this vault gives you

When set up, this vault becomes:

- **A second brain** — atomic Zettelkasten notes (`wiki/notes/`), book/course/paper records, and topic syntheses that compound across captures.
- **A career operating layer** — current narrative, target-tailored resumes, tracked applications, network rolodex with last-contact dates and follow-ups owed.
- **A planning rhythm** — weekly review (Sunday), quarterly review, annual review. Goals decompose to concrete weekly moves.
- **A decision log** — past decisions stay queryable; the **decision check** operation revisits them when context changes.
- **A hobby + fitness layer** — per-hobby session logs with "next time" breadcrumbs, structured workouts that auto-detect PRs, body-comp snapshots.
- **An accomplishment ledger** — log wins as they happen across 10 dimensions (career / craft / learning / network / health / finance / relationships / side-project / community / personal-growth). Reviews read this back.

The **vault is the source of truth**, not the agent. Claude proposes; you decide.

---

## Prerequisites

| Required | Why |
|---|---|
| [Obsidian](https://obsidian.md) (free) | Browse the vault, search, graph view, backlinks |
| [Claude Code](https://claude.com/code) or Claude Cowork with file-system access | The agent that maintains the vault |
**When you need Python 3.10+:**

| `pip install …` | When you need it |
|---|---|
| `docling` | PDF, DOCX, PPTX, XLSX ingest |
| `pyyaml` | Wiki lint scripts |
| _(none)_ | `wiki-search` uses ripgrep + stdlib SQLite FTS5 — no pip install needed |

| Node / npm | When you need it |
|---|---|
| `defuddle-cli` | Web URL clipping |

---

## Setup — pick one path

You have two ways to set up the vault. Both end with the same result.

### Path A — Edit `purpose.md` yourself (5 minutes, no agent)

1. **Move this folder** to a synced location (iCloud / OneDrive / Dropbox / Git):
   ```bash
   mv . ~/Dropbox/my-personal-wiki
   cd ~/Dropbox/my-personal-wiki
   ```

2. **Install [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)** (Obsidian's official agent skills — wikilinks, Bases, Canvas):
   ```bash
   # Pin to a specific commit for stability: ... && git -C /tmp/obsidian-skills checkout fa1e131a014576ff8f8919f191a7ca8d8fded39b
   git clone --depth 1 https://github.com/kepano/obsidian-skills.git /tmp/obsidian-skills
   mkdir -p .claude
   cp -r /tmp/obsidian-skills/.claude/* .claude/
   rm -rf /tmp/obsidian-skills
   ```

3. **Copy this kit's skills** from your `llm-wiki-kit` checkout into `.claude/skills/`:
   ```bash
   # If $WIKI_KIT is not set, run: export WIKI_KIT=/path/to/llm-wiki-kit
   cp -r "$WIKI_KIT/skills/shared/"*   .claude/skills/
   cp -r "$WIKI_KIT/skills/personal/"* .claude/skills/
   ```

4. **Edit `purpose.md`** — replace placeholders with your actual scope. 3-7 sentences, in-scope and out-of-scope. Claude reads this before every ingest, so anything outside scope gets skipped rather than polluting the wiki.

5. **Edit `_variant/CLAUDE.variant.md`** — top sections only: your name, current role / focus, tone preferences, anything specific to how you want the agent to push back. The rest works as-is.

6. **Open the folder in Obsidian** as a vault. `wiki/index.md` is your dashboard.

You're done. Skip to [Your first session](#your-first-session).

### Path B — Let Claude walk you through setup (10 minutes, conversational)

Do steps 1, 2, and 3 from Path A (move folder, install obsidian-skills, copy kit skills), then start Claude in the vault directory:

```bash
cd ~/Dropbox/my-personal-wiki
claude
```

Paste this prompt:

> Set up this personal knowledge & career vault for me. Read `CLAUDE.md` and `_variant/CLAUDE.variant.md` first to understand the schema, then ask me one question at a time to fill in:
>
> 1. **Identity** — first name, current role, 1-line description of what I do.
> 2. **Current focus** — 2-4 themes that most of my work and learning is about right now (e.g., distributed systems, agentic AI, technical writing, climbing).
> 3. **Career direction** — where I'm heading (next role title, industry shift, founding something, staying-and-deepening). One sentence is fine.
> 4. **Active goals** — 3-5 goals I'm working on this quarter. We'll create stub `wiki/goals/{slug}.md` pages from `_templates/goal.md`.
> 5. **In-scope topics** — what I want ingested (books, papers, talks, conversations, decisions, hobbies, fitness, finances, networking).
> 6. **Out-of-scope topics** — what I want skipped (e.g., work-employer-confidential material if my employer has its own vault).
> 7. **Tone preference** — how direct should you be? Default is reflective + growth-oriented + push-me-to-articulate-clearly. I can tune up or down.
> 8. **Hobbies + fitness** — which hobbies and what fitness modality (strength / endurance / mobility / hybrid) — so we can stub `wiki/hobbies/{slug}/overview.md` and an initial `wiki/fitness/programs/` if relevant.
> 9. **Privacy boundary** — confirm you'll never route career-sensitive material (applications, salary, employer details) to external research tools.
>
> When done, write the result to `purpose.md` (replacing the placeholder), update the identity sections of `_variant/CLAUDE.variant.md`, create stub `wiki/goals/{slug}.md` pages for each active goal, and create `wiki/hobbies/{slug}/overview.md` for each hobby. Don't change anything else. Show me the diffs before saving.

Claude will ask one question at a time and write `purpose.md` plus your goal stubs and hobby overviews at the end.

---

## Your first session

Run the **canonical operation** before capturing anything else. It's what makes the vault feel alive — the rhythm that gives captures a purpose.

For the personal variant, that's **weekly-review** (Sunday evening / Monday morning):

```
Run my weekly review for the week ending {YYYY-MM-DD}.
```

Claude will:
1. Pull recent activity — accomplishments, meetings, decisions, completed tasks, hobby sessions.
2. Walk you through reflection prompts (energy, blockers, learnings).
3. Write `wiki/reviews/weekly/{YYYY-MM-DD}.md` with: what shipped, what got dropped, what's next, themes to watch.
4. Surface stale connections, books you said you'd read, decisions due to revisit.

Open the new review in Obsidian. That's the rhythm — Sunday plan, Friday digest, Monday execute.

> [!tip] If your vault is empty
> Run `Capture three accomplishments from this past week.` and `Add one book I'm currently reading.` first. The weekly review needs *some* substrate. The accomplishment ledger and the book log are the two highest-leverage things to start.

**What you get** — a weekly review looks like this:

```markdown
---
type: weekly-review
week_ending: 2026-04-27
provenance: synthesized
created: 2026-04-27
modified: 2026-04-27
tags: [weekly-review, review]
---

## Synopsis

Week of April 21–27. Shipped the auth refactor, read 40% of Thinking Fast and
Slow, missed the gym twice. Main theme: execution on backlog, not new starts.

## What Shipped

- ✅ Auth token refresh endpoint merged and deployed
- ✅ Finished [[books/thinking-fast-and-slow]] chapters 1-8 (notes in book page)
- ✅ Replied to Sarah at Acme (stale connection surfaced from rolodex)

## What Got Dropped

- ❌ Rate limiting design doc — blocked on infra decision, carry to next week
- ❌ 3 of 4 planned gym sessions — travel on Wednesday

## Themes

- **Execution gap:** planned 5 items, shipped 3. Two blockers were external.
- **Reading momentum:** on track for finish by May 10.

## Next Week

1. Write rate limiting design doc once infra decision lands (Mon)
2. Research [[decisions/2026-deployment-strategy]] — verdict overdue
3. Coffee chat with Marcus (added to calendar)

## Open Loops

- [[decisions/2026-deployment-strategy]] — flagged stale, revisit due
- [[network/sarah-chen]] — replied this week; follow up in 3 weeks
```

---

## Capturing new content

The pattern: tell Claude what kind of artifact you're producing, paste or point to source material, and let it land in the right place with the right frontmatter.

### Atomic notes (Zettelkasten-style — one idea per note)

```
Save an atomic note: {one idea, in your own words}.
Link to: {related notes, books, or topics — wikilink names are fine}.
```

Lands at `wiki/notes/{slug}.md`. **Atomicity matters.** A book gets a `wiki/books/{slug}.md` PLUS several `wiki/notes/{slug}.md` capturing standout ideas — never one giant note.

### Topic syntheses (when 5+ notes share a theme)

```
Synthesize a topic page on {theme}. Pull from notes tagged {tags}
and any books I've read on this.
```

Lands at `wiki/topics/{slug}.md`. The **knowledge consolidation** skill suggests these automatically when it spots clusters.

### Books / courses / podcasts / papers

```
Save a book: {title} by {author}, {year}. I'm at {status: someday | reading | done}.
Standout ideas so far: {bullets}.
```

Creates `wiki/books/{slug}.md` PLUS the atomic notes capturing the standout ideas (linked back to the book and to relevant topics). Use the `_templates/book.md` shape.

### Personal projects (side projects, learning tracks, builds)

```
Start a new personal project: {name}. Goal: {outcome}. Time horizon: {weeks/months}.
```

Scaffolds `wiki/projects/{slug}/overview.md` from `_templates/project.md`.

### Goals

```
Add a {quarter | year}-scope goal: {goal in one sentence}.
What success looks like: {observable outcome}.
```

Lands at `wiki/goals/{slug}.md` from `_templates/goal.md`. Linked to relevant projects and skills.

### Decisions (personal decision log)

```
Log a decision: {what I decided}.
Context: {why this came up}.
Options considered: {bullets}.
Why this one: {reasoning}.
When to revisit: {date or trigger}.
```

Lands at `wiki/decisions/{date}-{slug}.md` from `_templates/decision.md`. The **decision-check** operation reads these later.

### Reflections / journaling

```
Save a reflection: {free-form journaling}.
```

Lands at `wiki/reflections/{date}-{slug}.md`. If a reflection surfaces a concrete decision, Claude proposes promoting it to a decision page.

### Accomplishments (log when it happens)

```
Log an accomplishment: {what I did}. Dimension: {career | craft | learning | network |
health | finance | relationships | side-project | community | personal-growth}.
```

Lands at `wiki/accomplishments/{date}-{slug}.md`. Per-dimension reviews read these. **Don't wait for year-end** — recall is unreliable; the log is your honest input to reviews.

### Hobby sessions

```
Log a hobby session: {hobby slug}, {date}, {duration}.
What I worked on: {focus}.
What worked: {bullets}. What didn't: {bullets}. Next time: {breadcrumb}.
```

Lands at `wiki/hobbies/{slug}/sessions/{date}-{slug}.md`. **The "next time" breadcrumb is the single biggest lever** against context-switching friction when you next pick the hobby up. Updates the hobby overview's `## Recent Sessions`, `## Next Time`, and `modified:`.

### Fitness sessions

```
Log a workout: {date}.
Strength: {exercise} {sets}×{reps}×{weight}@RPE{N}, {next}, ...
Cardio: {distance / pace / HR zone / time}.
Mobility: {focus areas, duration}.
Notes: {energy, soreness, anything off}.
```

Lands at `wiki/fitness/sessions/{date}-{slug}.md`. **Auto-detects PRs** against canonical exercise pages (`wiki/fitness/exercises/{slug}.md`) and refreshes `wiki/fitness/pr-summary.md`. PRs that cross milestone thresholds (first bodyweight bench, sub-25 5K) flow into the accomplishment log automatically.

### Body metric snapshots

```
Log body metrics: weight {N}, body-fat {N}%, measurements {chest/waist/hips/...},
sleep {1-5}, energy {1-5}, soreness {1-5}.
```

Lands at `wiki/fitness/body/{date}.md`. Cadence: weekly weight, monthly measurements is the right balance.

### Network — people

From a LinkedIn URL, business card, intro email, or just from memory:

```
Add a person to my network: {name}. How we met: {context}.
What they do: {role / company / focus}. Why I want to stay in touch: {reason}.
```

Lands at `wiki/network/relationships/{slug}.md` from `_templates/person.md`. Use `_templates/advisor.md` for formal mentors → `wiki/network/advisors/`.

### Logging a touch (after a coffee, call, DM exchange)

```
Log a touch with {name}: {date}, {what we discussed}.
What I owe them: {follow-ups, intros, resources I promised}.
```

Bumps `last_contact:` on their page and appends to `## Our Conversations`. Anything in `## Things I've Promised / Owe` gets surfaced by the **networking-digest** as follow-ups owed.

### Career — applications

```
Capture a job application: {company}, {role}, {location}, {comp range},
{deadline}. Source: {URL or paste}.
```

Lands at `wiki/career/applications/{company}-{role}.md` from `_templates/application.md`. Surfaces network connections at the company for outreach. Cross-links to relevant portfolio pieces.

### Career — narrative + resume

```
Refresh my career narrative based on what I've shipped in the last quarter.
```

Updates `wiki/career/narrative/current.md`. Run before applications or networking pushes.

```
Tailor a resume for {company} {role}. Use the application page at {path}.
```

Produces a target-tailored `wiki/career/resume/{company}-{role}-{date}.md` plus a `.docx` in `outputs/career/`.

### Portfolio pieces (writing, talks, code, design)

```
Add a portfolio piece: {title}, {medium}, link {URL}, year {YYYY}.
What it demonstrates: {capability}.
```

Lands at `wiki/portfolio/{slug}.md`.

### Skills (tracking development)

```
Track skill: {skill}. Current level: {1-5 or self-description}. Goal: {target level + by when}.
Next concrete step: {action}.
```

Lands at `wiki/career/skills/{slug}.md`. The **skill-gap analysis** operation reads goals + current skills and proposes development priorities.

### Meetings / 1:1s / networking conversations

```
Save a meeting with {name(s)}: {date}.
Discussed: {topics}. Advice received / given: {bullets}.
Follow-ups for me: {bullets}. Follow-ups for them: {bullets}.
```

Lands at `wiki/meetings/{date}-{topic}.md`. Updates each person's relationship page automatically.

### Bookmarks and web clips

```
Bookmark {URL} with note: {why it matters}.
```

Lands at `wiki/bookmarks/{slug}.md`. With the [Obsidian Web Clipper](https://obsidian.md/clipper), clips land in `Clippings/` or `raw/web-clips/` — then run `Process pending clippings.`

### Documents (PDF, .docx, .epub) — books and papers

Drop the file in `raw/`, then:

```
Ingest this as a book/paper: raw/{filename}. Capture standout ideas as atomic notes.
```

Uses the `ingest-document` skill (Docling) under the hood for clean extraction.

---

## Producing deliverables

Operations read structured wiki pages and write derived pages back. The output is itself a wiki page subsequent operations can consume.

### Weekly review
```
Run my weekly review for the week ending {YYYY-MM-DD}.
```
Lands at `wiki/reviews/weekly/{YYYY-MM-DD}.md`.

### Quarterly review (synthesizes 12 weekly reviews + goal progress + per-dimension reflections)
```
Run my Q{N} {YYYY} review.
```

### Annual review (year retrospective + next-year theme + goal planning)
```
Run my {YYYY} annual review.
```

### Career narrative refresh
```
Refresh my career narrative based on the last {6 months / quarter / year}.
```

### Job-search prep (target role → tailored resume + portfolio pull + application page)
```
Job-search prep for {target role / type of company}.
```

### Knowledge consolidation (atomic notes → topic syntheses)
```
Run knowledge consolidation. Surface clusters where I have 5+ notes
sharing a theme but no topic page yet.
```

### Networking digest (recent meetings + follow-ups owed + stale connections)
```
Show me my networking digest.
```

### Reading queue (books / papers / courses prioritized by goal alignment)
```
Refresh my reading queue based on current goals.
```

### Decision check (past decisions still aligned with current direction)
```
Show me past decisions due to revisit, and any that look misaligned with where I'm heading now.
```

### Skill-gap analysis
```
Given my active goals, what skills am I most underdeveloped in?
```

---

## Querying the vault

Just ask. Claude uses **progressive loading** — it scans `wiki/index.md`, then page synopses, and only reads full pages once it's confirmed relevance.

Examples:

- `What did I ship this week?`
- `Find my notes on event-driven architecture.`
- `What's my current career narrative?`
- `Who haven't I caught up with in 3 months?`
- `What books am I currently reading? What's next?`
- `Past decisions about role changes — what was the context?`
- `Compose a target-role-tailored resume for the {Acme} {role} application.`
- `What was my squat 1RM 6 months ago vs now?`
- `When did I last work on the {hobby} project? What was my "next time" note?`

If a query would be useful to future questions, ask Claude to save the answer:

```
Save that as an atomic note in wiki/notes/.
```

---

## Folder map

```
{your-vault}/
├── CLAUDE.md                    # Root agent contract (don't edit)
├── purpose.md                   # Your scope statement (you edit this)
├── _variant/
│   └── CLAUDE.variant.md        # Personal-variant schema (edit identity sections only)
├── _templates/                  # Page templates with {{placeholder}} fields
│   ├── note.md
│   ├── book.md
│   ├── decision.md
│   ├── goal.md
│   ├── application.md
│   ├── ... (project, review, accomplishment, hobby, fitness-session, ...)
├── raw/                         # Immutable source documents (drop files here)
├── wiki/                        # Structured pages (your source of truth)
│   ├── index.md                 #   Personal dashboard
│   ├── notes/                   #   Atomic Zettelkasten notes (one idea per note)
│   ├── topics/                  #   Synthesized topic pages
│   ├── projects/                #   Personal projects
│   ├── books/                   #   Book / course / podcast / paper records
│   ├── network/
│   │   ├── relationships/       #     People in network
│   │   └── advisors/            #     Formal advisors / mentors
│   ├── meetings/                #   1:1s, networking, mentorship
│   ├── goals/                   #   Career and life goals
│   ├── reviews/{weekly,quarterly,annual}/
│   ├── decisions/               #   Personal decision log
│   ├── reflections/             #   Journal entries
│   ├── accomplishments/         #   Append-the-moment win log
│   ├── hobbies/{slug}/{overview,sessions/}
│   ├── fitness/
│   │   ├── sessions/            #     Per-workout logs
│   │   ├── exercises/           #     Canonical exercise pages (auto-updated)
│   │   ├── programs/            #     Periodized training plans
│   │   ├── body/                #     Weight + measurements snapshots
│   │   └── pr-summary.md        #     Auto-maintained PR summary
│   ├── portfolio/               #   Public-facing work samples
│   ├── career/
│   │   ├── applications/
│   │   ├── resume/              #     Target-tailored resume versions
│   │   ├── narrative/           #     Brand story
│   │   ├── skills/              #     Skill tracking
│   │   └── tooling/             #     Per-role tooling inventory
│   ├── finances/{holdings,tax/{year}/}
│   ├── domains/                 #   Cross-cutting knowledge areas
│   ├── bookmarks/               #   URL bookmarks + homepage.base
│   └── research/                #   Multi-source research projects
├── outputs/                     #   Claude-generated deliverables (.docx, .pptx, .pdf)
├── log/
│   └── changelog.md             #   Append-only change log
└── .claude/
    ├── skills/                  #   Agent skills (you populated this in setup)
    └── research-providers.yaml  #   API keys for research dispatch (optional)
```

---

## Authoring rules in 30 seconds

These are enforced by `CLAUDE.md` and the `wiki-lint` skill:

- **Filenames are kebab-case** (`compounding-by-attention.md`), dates are **ISO 8601** (`2026-04-25`).
- **Every page has YAML frontmatter** (`type`, `status`, `provenance`, `created`, `modified`, `tags`).
- **Every page has a `## Synopsis` section** — 2-3 sentences. This is what enables progressive loading.
- **`provenance:`** is `extracted` (transcribed from a source) | `synthesized` (LLM-generated, needs source footnotes) | `mixed`.
- **Notes are atomic** — one idea per note. A book becomes a record + multiple atomic notes, not one giant note.
- **Internal links are wikilinks**: `[[note-name]]`, not relative paths. Cross-link aggressively — that's what compounds.
- **Filenames are canonical slugs — never rename them.** Update `title:` and `aliases:` in frontmatter instead.
- **Statuses**: `active` (current), `someday` (parking lot), `done` (completed), `outdated` (needs refresh).

---

## Health checks

Run on demand or weekly:

```
Lint the vault and write the report to log/lint-{today}.md.
```

Detects: orphan pages, stale items, broken wikilinks, missing synopses, raw files never synthesized, tag drift.

Underlying scripts (Python 3.10+):
```bash
pip install pyyaml
python .claude/skills/wiki-lint/scripts/tag-lint.py .
python .claude/skills/wiki-lint/scripts/convergence-debt.py .
```

**Search.** `Search the vault for {query}.` invokes the `wiki-search` skill.
Default backend is ripgrep (zero install if you already have `rg` on PATH).
Once the vault grows past ~1000 pages or 50 MB the skill auto-upgrades to a
SQLite FTS5 backend with BM25 ranking, porter stemming, and frontmatter-aware
filters — all via stdlib `sqlite3`, no `pip install`.

---

## Going further

- **Add custom skills** — drop a new directory under `.claude/skills/{skill-name}/` with `SKILL.md`, `scripts/`, `evals/evals.json` per the [Agent Skills spec](https://agentskills.io/specification). Examples: a custom `daily-shutdown` ritual, a `morning-pages` capture, a learning-track tracker.
- **Add custom page templates** — drop `_templates/{type}.md` and add the type to `_variant/CLAUDE.variant.md`'s page-types table.
- **Customize the agent's tone** — edit the Variant Identity section of `_variant/CLAUDE.variant.md`. The default is reflective, growth-oriented, willing to push back. You can dial that in or down.
- **Configure research providers** — fill in `.claude/research-providers.yaml` with API keys for Perplexity / Gemini / Semantic Scholar to enable multi-source research projects. Personal use leans on Perplexity (current state), Semantic Scholar (educational deep dives), Gemini (major life decisions only).

---

## Privacy and safety

A personal vault holds career-sensitive material (applications, salary expectations, interview notes), reflections, network contacts, and possibly health and financial records. Defaults err on the side of privacy:

- **The vault runs entirely on your machines.** Nothing leaves unless you enable a research integration for a specific query.
- **Career-sensitive material is internal-only.** The agent never routes application drafts, salary discussions, employer-specific details, or network contacts to external research tools. Abstract queries ("compensation benchmarks for Senior Platform Engineer at Series-B startups") are fine; targeted ones ("what should I ask for at Acme") are not.
- **Use private sync** — iCloud / Dropbox / OneDrive personal accounts inherit your existing access controls and encryption. If using Git, keep the repo private.
- **Never delete files without asking** — the agent archives instead.
- **`raw/` is immutable** — never modify ingested source documents after the fact.
- **Review what Claude proposes before you accept.** A personal wiki stays trustworthy only with your curation. The agent is a digital secretary — you do the thinking, it does the filing.
