# Personal Knowledge & Career System Design

## Architecture: One Person's Operating System

The personal variant adapts the LLM Wiki + Active OS pattern to a single user managing both their *knowledge* (Zettelkasten-style notes, books, papers, conversations) and their *career trajectory* (portfolio, applications, network, narrative). One person, one vault, two compounding loops:

1. **A personal knowledge base** — atomic notes that link freely, synthesized topic pages, structured records of books / talks / papers consumed.
2. **A career operating layer** — recurring operations that produce planning artifacts (weekly reviews, career narrative refreshes, application packages, networking digests, skill-gap analyses).

The same Obsidian vault, the same `CLAUDE.md` schema. The personal variant differs from work in that there's no team to coordinate with, and from family in that it's individual rather than household-scale. The architecture is the same; the ontology and operations are tuned for the solo professional.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                  PERSONAL KNOWLEDGE & CAREER OS                   │
│                                                                   │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│   │  Captures   │    │  Structured   │    │   Operations     │   │
│   │             │ →  │     Wiki      │ →  │     Layer        │   │
│   │  Notes      │    │              │    │                  │   │
│   │  Books      │    │  notes/      │    │  Weekly review   │   │
│   │  Talks      │    │  topics/     │    │  Quarterly /     │   │
│   │  Papers     │    │  projects/   │    │  annual reviews  │   │
│   │  Meetings   │    │  career/     │    │  Career narrative│   │
│   │  Apps       │    │  network/    │    │  Job-search prep │   │
│   │  Reviews    │    │  reviews/    │    │  Knowledge       │   │
│   │  Reflections│    │  ...         │    │  consolidation   │   │
│   └──────┬──────┘    └──────┬───────┘    └────────┬─────────┘   │
│          │                  │                      │              │
│          └──────────────────┼──────────────────────┘              │
│                             │                                     │
│                  ┌──────────▼──────────┐                          │
│                  │   CLAUDE.md schema   │                          │
│                  │   + variant ontology │                          │
│                  └──────────┬──────────┘                          │
│                             │                                     │
│             ┌───────────────┼───────────────┐                     │
│             │               │               │                     │
│         ┌───▼────┐     ┌────▼─────┐    ┌───▼────┐                │
│         │ Claude │     │ Claude   │    │ Claude │                │
│         │ Code   │     │ Cowork   │    │ Chat   │                │
│         │(power) │     │(daily)   │    │(mobile)│                │
│         └────────┘     └──────────┘    └────────┘                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

Two flows traverse the same vault:

- **Capture flow** (left → middle): a book finished, a talk attended, a meeting had, a project shipped, a decision made — anything personally significant — is ingested through a specialized ingester that produces a *structured page* in the right wiki location with the right frontmatter.
- **Operate flow** (middle → right): on demand or on a cadence, an operation skill reads the relevant structured pages, composes a derived artifact (this week's review, the refreshed career narrative, the tailored application package, the prioritized reading queue), and writes it back into the wiki as a new structured page.

The agent layer at the bottom — Claude Code for power use (vault management, multi-step operations), Claude Cowork for daily writing and capture, Claude Chat with web search for quick lookups while away from the laptop — all read and write the same vault.

---

## Layer 1: Storage & Sync

### Single user, multi-device

A personal vault is typically used across devices: laptop, desktop, phone, tablet. Sync via cloud drive (Dropbox, OneDrive, iCloud, Google Drive) is the cleanest option — same as the family variant, without the multi-caregiver coordination concern.

**How it works:**

- Pick whichever cloud drive you already use for personal files
- Create the Obsidian vault inside that synced folder
- Open the vault on each of your devices
- Edits propagate via the cloud's sync engine
- Claude Code or Claude Cowork on each device reads and writes the same files

For solo users, conflicts are rare — only one human is editing. The agent is the only other writer; queue agent runs to a single device or scheduled window if you're paranoid.

The full sync-options walkthrough lives at [`guides/sync-options.md`](../guides/sync-options.md). For personal vaults, **don't use Git unless you specifically want it** — the value-add (governance, review gates, audit trail) doesn't apply to a single-maintainer vault, and the ceremony slows capture.

### Privacy posture

A personal vault contains:

- **Career-sensitive material** — resume drafts, salary expectations, application status, interview notes, performance reviews
- **Personal reflections** — journal entries, decision rationales, doubts, ambitions
- **Network contact details** — phone numbers, email addresses, things people told you in confidence
- **Possibly health, financial, or legal information** — depending on what you choose to track

Treat the vault as personal data:

- **Vault location.** Cloud drive's encryption-at-rest is sufficient for most users. Don't push the vault to public Git.
- **External tools that touch the vault.** Be deliberate. Default research tools (Perplexity, Semantic Scholar) take abstract queries — they don't see the vault. The web ingester sends URLs to defuddle locally; pure.md fallback caches URLs and should never receive intranet / auth-protected URLs (LinkedIn DM threads, salary tools, internal company links).
- **Career content NEVER goes external.** Application drafts, salary discussions, network contact details should not be sent to third-party LLMs even via abstract queries. Use the orchestrator's local-only path for those.

### Single vault, not domain-vaults

A solo user might be tempted to maintain separate vaults: one for "work knowledge," one for "personal life," one for "career planning." Don't. The whole point is *cross-domain compounding* — the project you finished at work informs your portfolio; the book you read informs both work and personal projects; the people you meet span every context.

**One personal vault**, with `purpose.md` declaring the scope. Confidentiality of work content (e.g., proprietary code, internal company strategy) is handled by *not ingesting* that content — the personal vault is for the *person*, not the employer. Work-the-employer can have its own work-variant vault if needed; the personal vault holds your personal trajectory through your career.

---

## Layer 2: Ontology — Knowledge + Career

The personal variant has a hybrid ontology: a Zettelkasten-style knowledge graph layered with career-trajectory tracking and personal planning rhythm.

```
wiki/
├── index.md                  # Personal dashboard
├── notes/                    # Atomic Zettelkasten-style notes
├── topics/                   # Synthesized topic pages (cross-reference many notes)
├── projects/                 # Personal projects (side projects, learning, hobbies)
├── books/                    # Book / course / podcast / paper notes
├── network/                  # People I know / want to know
│   ├── contacts.md           # Quick contact reference
│   └── relationships/        # Per-person pages for active relationships
├── meetings/                 # 1:1s, networking conversations, mentorship
├── goals/                    # Career and life goals (mid-term and long-term)
├── reviews/
│   ├── weekly/               # Weekly review pages
│   ├── quarterly/            # Quarterly check-ins
│   └── annual/               # Annual retrospectives
├── portfolio/                # Public-facing work — writing, talks, code, designs
├── career/
│   ├── applications/         # Job applications, proposals, fellowships
│   ├── resume/               # Resume drafts and target-role versions
│   ├── narrative/            # Career narrative / brand story / "the deck"
│   └── skills/               # Skill tracking and gap analysis
├── decisions/                # Personal decision log
├── reflections/              # Journal entries / thinking-out-loud
├── research/                 # Multi-source research projects (shared layer)
├── domains/                  # Cross-cutting knowledge areas
└── reference/                # Misc personal reference
```

### Ontology design principles

1. **Notes are atomic.** Each `wiki/notes/{slug}.md` captures *one* idea — a concept, a quote, a question, a connection. Don't bloat a note with related but distinct ideas; create a separate note and link them. Atomicity is what makes the network compound.

2. **Topics emerge upward.** When 5+ atomic notes share a theme, the knowledge-consolidation operation proposes synthesizing them into a `wiki/topics/{slug}.md` page. The atomic notes remain; the topic is a synthesized layer above. This is the Zettelkasten dual-layer.

3. **Career is structured, not free-form.** A resume isn't a free-form note — it's a versioned document targeted to a specific role. A portfolio entry is a curated record. Applications track stage. The personal variant treats career artifacts as first-class structured types, not just notes.

4. **Reviews are the heartbeat.** Weekly, quarterly, and annual reviews are the operational pulse that keeps the vault alive for solo maintainers. Without reviews, the vault decays into a write-only dump.

5. **Network is dual.** People appear both in `network/relationships/` (per-person pages) and as wikilinks from meeting notes, decisions, project context. The relationship pages accumulate context over time; the meeting pages are point-in-time.

6. **Connection over completeness.** Personal vaults compound through cross-linking, not exhaustive coverage. A note that links to 5 other notes is more valuable than a comprehensive standalone essay.

### Page types

| Type | Description | Location |
|---|---|---|
| `index` | Folder navigation | Any folder |
| `note` | Atomic Zettelkasten-style note | `wiki/notes/` |
| `topic` | Synthesized topic page (cross-references many notes) | `wiki/topics/` |
| `project` | Personal project (side project, learning track, hobby) | `wiki/projects/{slug}/overview.md` |
| `book` | Book / course / podcast / paper notes | `wiki/books/` |
| `person` | Person in network | `wiki/network/relationships/` |
| `meeting` | 1:1 / networking / mentorship conversation | `wiki/meetings/` |
| `decision` | Personal decision log entry | `wiki/decisions/` |
| `goal` | Career or life goal | `wiki/goals/` |
| `review` | Weekly / quarterly / annual review | `wiki/reviews/{cadence}/` |
| `portfolio` | Public-facing work sample | `wiki/portfolio/` |
| `application` | Job application / proposal / fellowship | `wiki/career/applications/` |
| `resume` | Resume version | `wiki/career/resume/` |
| `narrative` | Career narrative / brand story | `wiki/career/narrative/` |
| `skill` | Skill tracking page | `wiki/career/skills/` |
| `reflection` | Journal entry | `wiki/reflections/` |
| `domain` | Cross-cutting knowledge area | `wiki/domains/` |
| `reference` | Misc personal reference | `wiki/reference/` |
| `research-project` etc. | Research-layer pages (shared with other variants) | `wiki/research/{slug}/` |
| `asset` | Companion page for non-text files | Co-located with asset |

### Status values

Simpler than work (no formal review/approval lifecycle):

- `active` — currently in use / current
- `someday` — parking lot, may revisit (popular for ideas, books, projects)
- `done` — completed / archived
- `outdated` — needs refresh

### Tagging taxonomy

- **Knowledge:** `#concept`, `#book`, `#course`, `#talk`, `#paper`, `#question`
- **Career:** `#career`, `#interview`, `#networking`, `#job-search`, `#application`, `#portfolio`, `#mentorship`
- **Domains:** `#engineering`, `#leadership`, `#writing`, `#design`, `#ai`, `#data`, `#productivity` (use kebab-case freely)
- **Lifecycle:** `#active`, `#draft`, `#published`, `#archived`
- **Time:** `#now`, `#month`, `#quarter`, `#year` (used to scope reviews and goals)

---

## Layer 3: Schema (CLAUDE.variant.personal.md)

Highlights of the variant agent contract — full schema in `vault-templates/personal/_variant/CLAUDE.variant.md`.

**Identity and tone.** "You maintain a personal knowledge and career operating system. Part research librarian, part career coach. Reflective, growth-oriented, direct. Push the user to articulate clearly and decide concretely. Avoid sycophancy — honest feedback is more useful than agreement."

**Atomic note discipline.** Notes in `wiki/notes/` are atomic — one idea per note. The agent doesn't bloat notes; it creates new notes and links them.

**Career privacy.** Application status, salary expectations, networking notes are sensitive. Never ingest these to external research tools; abstract queries only ("compensation benchmarks for X role at Y stage") not personal queries ("what should I ask for at company Z").

**Tagging conventions.** Use `#career`, `#networking`, `#job-search` aggressively for retrieval; under-tag domain (knowledge cross-cutting topics) where appropriate.

---

## Layer 4: Structured Ingestion

The standard two-axis pattern: source-type ingesters clean the input; content-type ingesters apply schema.

### Personal-variant content-type ingesters

| Ingester | Source kinds | Target |
|---|---|---|
| **`ingest-book-note`** | Kindle highlights, scanned book annotations, course transcripts, podcast notes, paper PDFs | `wiki/books/{slug}.md` |
| **`ingest-paper`** | Academic / industry paper PDF | `wiki/books/{slug}.md` (or domain-specific) |
| **`ingest-talk`** | Conference talk recording / transcript / slides | `wiki/books/talks/{slug}.md` |
| **`ingest-application`** | Job posting URL, application form, recruiter email | `wiki/career/applications/{company}-{role}.md` |
| **`ingest-meeting`** (shared with work) | Networking conversation transcript, mentorship notes, 1:1 notes | `wiki/meetings/{date}-{topic}.md` |
| **`ingest-website`** (shared) | Articles, blog posts, references | `wiki/notes/` or `wiki/research/` |
| **`ingest-document`** (shared) | PDFs, slides, docs | content-dependent |

### Walkthrough: ingesting a book

You finish a book and want it in the vault. You drop the highlights file (Kindle export, scanned annotations, or pasted notes) and say *"Save this as a book note: {Title} by {Author}."*

1. **Routing.** The orchestrator sees the file + content-type intent ("book"). Dispatches to `ingest-book-note`.
2. **Cleanup.** If the source is a PDF or a Kindle export, route through `ingest-document` for cleanup.
3. **Schema extraction.** `ingest-book-note` extracts: title, author(s), publisher, ISBN if present, year, your highlight list with chapter / location, key claims / quotes you marked.
4. **Apply book template.** Populates `_templates/book.md` (when authored) — frontmatter (title, author, year, status: read), body sections (Synopsis, Key Claims, Standout Quotes, How It Connects).
5. **Cross-link.** Identify topics already in `wiki/topics/` that this book relates to. Identify atomic notes you have on those topics. Propose: "this book deepens [[topics/event-driven-architecture]] — should I draft 2-3 atomic notes capturing the new claims?"
6. **Save** as `wiki/books/{slug}.md`. Update reading-status frontmatter on previous version if you had it as `someday` or `in-progress`.

### Walkthrough: ingesting a job application

You see a posting and decide to apply. You paste the URL or job description and say *"Track this application: {Company} - {Role}, deadline {date}."*

1. **Routing.** Orchestrator sees URL or text + content-type intent ("application"). Dispatches to `ingest-application`.
2. **Cleanup.** If URL → `ingest-website` (defuddle on the job posting). If pasted text → handle directly.
3. **Schema extraction.** `ingest-application` extracts: company name, role title, location, comp range if listed, key requirements, application deadline, source (where you found it).
4. **Apply application template.** Populates `_templates/application.md` — frontmatter (company, role, status: active, deadline), body sections (Synopsis, Stage tracking, Why This Role, Tailored Materials, Network).
5. **Cross-link to network.** Search `wiki/network/relationships/` for connections at the company. Surface: "you know [[network/relationships/sarah]] who works there — consider reaching out for a referral."
6. **Save** as `wiki/career/applications/{company}-{role}.md`. The page now lives in the application tracker.

The job-search-prep operation (Layer 5) runs against this page later to assemble tailored resume + cover letter + portfolio piece selection.

---

## Layer 5: The Personal OS — Operations

The operations layer is what turns the personal vault from filing cabinet into operating system.

### What an operation is

(Same general shape as work and family.) An operation reads structured wiki pages, composes, and writes a derived structured page back into the vault. The result page is itself queryable, linkable, and consumable by subsequent operations.

### Operation classes (personal-flavored)

| Class | Personal examples |
|---|---|
| **Planning** | Weekly priorities, quarterly goals, job-search prep (tailored resume + portfolio assembly) |
| **Reminding** | Networking follow-ups owed, decisions due for re-examination, books with deadline |
| **Synthesizing** | Weekly / quarterly / annual reviews, knowledge consolidation (atomic → topic), career narrative refresh |
| **Recommending** | Reading queue prioritization (against goals), skill gap analysis, similar past projects |
| **Crisis-responding** | Job loss / unexpected role change → assemble narrative + portfolio + applications quickly |

### Walkthrough: weekly review (canonical)

The personal-variant analogue of sprint planning (work) and meal planning (family). High-leverage starter operation; if any single operation matters, it's this one.

A user on Sunday evening: *"Run my weekly review."*

The `weekly-review` skill runs roughly this:

1. **Read the inputs.**
   - `log/changelog.md` entries from the last 7 days
   - All wiki pages with `modified:` in the last 7 days (across notes, books, projects, decisions, meetings)
   - Active project pages (their Current State sections)
   - Goals page — for the lens to evaluate progress against
   - The most recent weekly review (last week's) — for carry-over and theme continuity

2. **Apply reflective prompts.** The skill's job isn't just summarization — it asks the user to articulate. Generated prompts:
   - "What did you ship this week that you're proud of?"
   - "What got blocked, and was it your blocker or someone else's?"
   - "What did you learn that surprised you?"
   - "What's the one thing you want next week to be about?"
   - "Are any active projects no longer aligned with current goals?"

3. **Compose the output.** Write `wiki/reviews/weekly/2026-04-26.md`:

   ```markdown
   ---
   type: review
   review_cadence: weekly
   week: 2026-W17
   created: 2026-04-26
   modified: 2026-04-26
   tags: [review, weekly]
   status: current
   ---

   ## Synopsis

   Week of strong knowledge work, mediocre career-tracking discipline.
   Shipped the Kafka observability talk draft; one application stalled
   waiting on referral. Reading queue grew faster than it shrank.

   ## What I Shipped

   - [[portfolio/kafka-observability-talk-v2]] — second draft, ready
     for review by [[network/relationships/sarah]]
   - [[notes/event-loops-vs-actor-models]] — atomic note connecting
     three previously-separate ideas
   - [[decisions/2026-04-23-decline-fellowship]] — declined the
     research fellowship; reason captured in the decision

   ## What I Learned

   - {{Distillation from books finished and notes added}}
   - {{Specific surprise or update}}

   ## What's Blocked

   - [[career/applications/acme-platform-engineer]] —
     waiting on Sarah's referral; nudge if not in by Wednesday
   - [[projects/personal-site-rewrite]] — design decision overdue

   ## What's Next

   1. Acme application status — close the loop
   2. Send talk draft to Sarah
   3. Personal-site design decision (pick a direction)
   4. Two atomic notes from {{currently-reading book}}
   5. Quarterly review prep — only 2 weeks out

   ## Themes I Noticed

   - Cross-pollination between event-driven thinking (work) and
     personal-site design (personal project) — worth a topic page
   - Reading queue is growing; consolidation is needed

   ## Energy & Reflection

   {{Honest read on energy, what's working, what's draining.}}

   ## Cross-References

   - Last week: [[reviews/weekly/2026-04-19]]
   - Active goals: [[goals/2026-q2]]
   - Recent decisions: [[decisions/]]
   ```

4. **Side-effects.**
   - Update `wiki/reviews/weekly/index.md` with the new week's link
   - If themes detected (recurring topics), surface them as candidates for [[knowledge-consolidation]] (which proposes promoting atomic notes to a topic page)
   - If goals appear stalled, surface for next-quarter-review prep
   - Append to `log/changelog.md`

5. **Interactive review.** The skill presents the proposed review and asks the user to expand the reflective prompts. The user fills in the open sections; the skill saves the final.

### Other operations worth authoring

| Operation | Inputs | Output | Cadence |
|---|---|---|---|
| **Quarterly review** | All weekly reviews from the quarter, goal progress, decisions | `reviews/quarterly/{quarter}.md` | Every 3 months |
| **Annual review** | All quarterly reviews, all decisions, year retrospective lens | `reviews/annual/{year}.md` | Once per year (December) |
| **Career narrative refresh** | Recent projects, portfolio additions, decisions, current narrative | Updated `career/narrative/{date}.md` | Quarterly or after major shifts |
| **Job-search prep** | Target role + company, portfolio, recent projects, current resume | `career/applications/{company}-{role}.md` + tailored `resume/{target}-{date}.md` | Per application |
| **Knowledge consolidation** | Atomic notes accumulating around a theme | New `topics/{slug}.md` synthesis | When 5+ notes share a theme |
| **Networking digest** | meetings/ from last 30-90 days, network/relationships | `reviews/networking-{date}.md` (one-off) | Monthly |
| **Reading queue** | books/ with status: someday or in-progress, goals | Prioritized list (inline report) | When considering what to read next |
| **Decision check** | decisions/ from last 12 months, current goals | List of decisions to revisit (inline) | Quarterly |
| **Skill gap analysis** | skills/ pages, goals, recent learnings | Skill development priorities (inline) | Quarterly |

### Operations as the wiki's heartbeat

A personal vault without operations dies *fast*. Solo maintainers don't have a team holding them accountable; if the vault stops producing visible weekly value, the maintainer stops contributing, and within 2-3 months the vault is a write-only graveyard.

The cure: **ship the weekly-review operation in the first month and run it religiously.** The other operations layer on top once the weekly rhythm is established.

---

## Layer 6: Privacy & Solo-Maintainer Tradeoffs

### Single-user concerns

Personal vaults don't have multi-caregiver coordination, but they have their own failure modes:

- **The maintainer's burnout = vault death.** No one else is keeping it alive.
- **Privacy is one-person's-discipline.** No one else is going to catch you sending career-sensitive content to external tools.
- **Cross-domain temptation.** It's tempting to dump work-product into the personal vault. Don't — the personal vault is for *your* trajectory, not your employer's IP.

### Mitigations

- **Lower the activation energy for capture.** A capture mechanism that takes 90 seconds beats a thorough one that takes 5 minutes.
- **Lock the weekly-review cadence early.** Same time, same place, every week. Skip a week and the vault decays exponentially.
- **External-tool boundaries are documented in `purpose.md`.** The agent reads them before every research operation.
- **Don't optimize for completeness.** A 60% complete personal vault that you actually use beats a 95% complete one that's a chore.

---

## Layer 7: Failure Modes

Why personal vaults fail. Worth naming, since most are predictable.

### The "shiny note" trap

You accumulate atomic notes faster than you consolidate them. After 6 months, you have 200+ notes and no topic pages. Browsing notes is harder than browsing the books you read them from.

**Counter:** Run knowledge-consolidation regularly. When weekly review surfaces a theme, immediately create or update the topic page. Atomic notes are inputs; topics are the synthesis layer that makes them queryable.

### The "career amnesia" trap

You ship things at work. You attend conferences. You learn from books. None of it gets captured to the personal vault. Performance review time arrives, or a recruiter asks "what have you done lately," and you can't remember.

**Counter:** The weekly review's "What I Shipped" section. Every week, capture three concrete things — even small ones. Annual review reads back across all 52 weekly reviews and produces the year retrospective.

### The "infinite reading list" trap

Books pile up faster than they're read. Reading queue becomes aspirational fiction.

**Counter:** Reading-queue operation prioritizes against current goals. Books that don't serve a current goal go to `status: someday`. Books from someday to active require an explicit goal-justification.

### The "stale narrative" trap

Career narrative was written 2 years ago. Doesn't reflect current strengths. You go to interviews telling an outdated story.

**Counter:** Career-narrative-refresh operation runs quarterly. Reads recent projects + portfolio + decisions, proposes updates. The narrative is a living document.

### The "isolated vault" trap

Vault exists. Nobody opens it. Even *you* don't open it. You're maintaining for the future-you who'll never need it.

**Counter:** Ship operations that produce *outputs you consume*. The weekly review is a planning artifact you read on Monday. The career narrative is what you reference for interviews. The reading queue is what you check before picking up a book. If the vault doesn't produce reading material for present-you, it'll die.

---

## Implementation Roadmap

### Phase 1: Vault setup (one weekend)

1. Pick a cloud drive provider (Dropbox is popular for personal). Create the synced folder. Copy `vault-templates/personal/` into it.
2. Install Obsidian on each device. Open the vault.
3. Customize `_variant/CLAUDE.variant.md` with your identity, tone preferences, and any privacy specifics.
4. Customize `purpose.md` with your scope statement.
5. Walk through [`setup guide`](../guides/setup.md) to install obsidian-skills, kit skills, Python deps.
6. Edit `wiki/index.md` to reflect your current state — top projects, goals, etc.

### Phase 2: First captures (week 1-2)

7. Pick one capture domain to start. Suggested: **books / reading** if you're knowledge-leaning, **applications + network** if you're job-searching.
8. Ingest 5-10 recent books or 3-5 recent applications. Validate the templates fit.
9. Add a few atomic notes from your current thinking. Cross-link them.
10. Don't try to backfill years of history. Start where you are.

### Phase 3: First operation (week 3-4)

11. Set up the weekly-review cadence. Run it Sunday evening or Monday morning. Use the skill if authored, or use the template manually.
12. After 3 weeks of weekly reviews, the rhythm starts paying back.
13. Add a second operation when you feel friction in the current rhythm: career-narrative-refresh if interviewing, knowledge-consolidation if notes are piling up.

### Phase 4: Operational maturity (ongoing)

14. Run lint weekly. Address staleness flags.
15. Quarterly review every 3 months. Annual every December.
16. Career operations on demand: job-search prep before each application; narrative refresh quarterly.
17. Resist the temptation to add more operations until current ones are habituated.

---

## Cost Estimate

Per month, single user.

| Component | Cost | Notes |
|---|---|---|
| Obsidian | Free | Sync is $5/mo if used; otherwise $0. |
| Cloud drive | Free–$10 | Most users already pay for this. |
| Claude Pro/Max | $20–100 | One subscription. Pro is fine for most. |
| Perplexity Pro | $0–20 | Optional; free tier handles most personal lookups. |
| Semantic Scholar | Free | No cost. |
| Defuddle | Free | Local CLI. |
| pure.md | Free | Anonymous tier handles most ingest volume. |
| Docling | Free | Local Python. |
| **Total** | **~$20–40/mo** | Most of which a serious personal-knowledge user already pays. |

The personal variant is the cheapest of the three — no PM tools, no team subscriptions, no Gemini default.

---

## Key Design Decisions & Rationale

**Why Zettelkasten + structured career?**
Zettelkasten alone is the gold standard for PKM but misses the *operational* layer. Career building requires structured artifacts (resumes are not free-form notes) and recurring rhythms (reviews are not optional). Combining them in one vault is what lets the personal-knowledge graph and the career trajectory compound on each other — the project finished at work informs the portfolio; the book read informs the career narrative.

**Why one personal vault, not separate domain-vaults?**
Cross-domain compounding is the whole point. A separate "knowledge vault" and "career vault" would force the user to manually carry context between them, which they wouldn't, and the system would die. One vault, with `purpose.md` defining the scope, is cleaner.

**Why no formal decision records (ADRs)?**
Personal decisions don't have the same lifecycle or stakeholder coordination as architectural decisions in software. Use lightweight `decisions/` entries — the date, the context, the choice, the reasoning. No formal acceptance gate; no immutability. Personal decisions are revisited through the decision-check operation.

**Why is weekly-review the canonical operation?**
For solo maintainers, the vault dies without a recurring rhythm that produces visible value. Weekly review delivers a planning artifact you actually consume on Monday, which keeps you opening the vault, which keeps capture alive, which keeps the system living. Sprint planning serves this role for work; meal planning for family; weekly review for personal.

**Why career narrative as a first-class structured type?**
Most people only write a career narrative when actively job-searching, then it goes stale. Treating it as a structured page that the narrative-refresh operation updates *quarterly* keeps it living, which means when interview opportunities arise, the story is already current.

**Why explicit privacy boundary on career content?**
Career-sensitive material (salary, application status, network confidences) is the most likely thing a careless agent would surface inappropriately. Document the boundary loudly in the variant CLAUDE.md and the agent handles abstract queries only — even when the user is asking a question that *could* benefit from richer context.

**Why outdated-info as a status, not a callout?**
Personal content's currency drifts faster than family content (which drifts faster than work content). A career narrative from 2024 is functionally stale by 2026. Making `outdated` a first-class status (not just a warning callout) lets lint surface stale content for refresh and makes the refresh operations meaningful.
