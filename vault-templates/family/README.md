# Family Vault — Household Knowledge OS

A wiki + agent-driven operating layer for your household. Recipes, medical records, school documents, trips, home maintenance, finances — all in plain markdown your family owns, kept current by Claude.

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

- **A medical record** — per-person summaries, providers, medications, follow-up flags. Drop an EOB or visit note; the relevant pages update.
- **A recipe library** — family favorites, weeknight rotation, dietary notes (allergens, preferences). Plan a week of meals from what's actually in the library.
- **A trip planner + journal** — itineraries, packing lists, points of interest, post-trip notes.
- **A home log** — vendors who did good work, appliance manuals, maintenance schedule, vehicle service history.
- **A finances index** — subscriptions, holdings, tax documents per year — without your statements leaving the vault.
- **A weekly rhythm**: Sunday meal plan, follow-up tracker, weekly digest of what changed.

The **vault is the source of truth**, not the agent. Claude proposes; a parent reviews.

---

## Prerequisites

| Required | Why |
|---|---|
| [Obsidian](https://obsidian.md) (free) | Browse the vault, search, graph view |
| [Claude Code](https://claude.com/code) or Claude Cowork with file-system access | The agent that maintains the vault |
**When you need Python 3.10+:**

| `pip install …` | When you need it |
|---|---|
| `docling` | PDF, DOCX, PPTX, XLSX ingest |
| `pyyaml` | Wiki lint scripts |

| Node / npm | When you need it |
|---|---|
| `defuddle-cli` | Web URL clipping |

---

## Setup — pick one path

You have two ways to set up the vault. Both end with the same result.

### Path A — Edit `purpose.md` yourself (5 minutes, no agent)

1. **Move this folder** to a synced location (OneDrive / iCloud / Google Drive / Dropbox):
   ```bash
   mv . ~/OneDrive/our-family-wiki
   cd ~/OneDrive/our-family-wiki
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
   cp -r "$WIKI_KIT/skills/shared/"* .claude/skills/
   cp -r "$WIKI_KIT/skills/family/"* .claude/skills/
   ```

4. **Edit `purpose.md`** — replace placeholders with your family's actual scope. 3-7 sentences, in-scope and out-of-scope bullets. Claude reads this before every ingest, so anything outside scope gets skipped rather than polluting the wiki.

5. **Edit `_variant/CLAUDE.variant.md`** — top sections only: family member first names (used in tags like `#jake`, `#sarah`), tone preferences, anything specific to your household. The rest works as-is.

6. **Open the folder in Obsidian** as a vault. `wiki/index.md` is your dashboard.

You're done. Skip to [Your first session](#your-first-session).

### Path B — Let Claude walk you through setup (10 minutes, conversational)

Do steps 1, 2, and 3 from Path A (move folder, install obsidian-skills, copy kit skills), then start Claude in the vault directory:

```bash
cd ~/OneDrive/our-family-wiki
claude
```

Paste this prompt:

> Set up this family vault for me. Read `CLAUDE.md` and `_variant/CLAUDE.variant.md` first to understand the schema, then ask me one question at a time to fill in:
>
> 1. **Household members** — first names of every family member you'll track (parents, kids, anyone else). For each, briefly: birth year, key dietary notes, any chronic medical considerations I want surfaced.
> 2. **Pets** — names + species if any.
> 3. **In-scope topics** — which categories I want maintained: medical, recipes, school records, home/vehicles, finances/taxes, travel, memories, pet records.
> 4. **Out-of-scope topics** — anything I want skipped (e.g., extended family medical, work-related material).
> 5. **Sensitivity** — anything that needs extra care (e.g., a child's medical condition that should never be surfaced unprompted).
> 6. **Tone** — friendly-conversational, briefer-and-functional, or somewhere in between. Whether replies should be age-appropriate when a kid asks.
> 7. **Travel home base** — city/region for trip planning context.
>
> When done, write the result to `purpose.md` (replacing the placeholder), update the identity sections of `_variant/CLAUDE.variant.md`, and create stub `wiki/people/{name}.md` pages for each household member from `_templates/person.md`. Don't change anything else. Show me the diffs before saving.

Claude will ask one question at a time and write `purpose.md` plus per-person pages at the end.

---

## Your first session

Run the **canonical operation** before capturing anything else. It's what makes the vault feel alive — the rhythm that gives captures a purpose.

For the family variant, that's **meal-planning** (Sunday afternoon):

```
Plan meals for next week. We have {N} dinners to plan; {who} is around for which days.
Constraints: {one-pot Tuesday, takeout Friday, anything else}.
```

Claude will:
1. Read your recipe library, dietary notes, and last week's meal plan (if it exists).
2. Propose a 7-day plan respecting allergies and "we just had X".
3. Write it to `wiki/food/meal-plans/{YYYY-MM-DD}.md` with a shopping list grouped by store section.

Open the new plan in Obsidian. That's your shopping list and dinner schedule for the week.

> [!tip] If your recipe library is empty
> Capture 5-10 family favorites first using the [Recipes](#recipes) section below. Even a small library is enough to get the meal-planning loop going.

**What you get** — a meal plan looks like this:

```markdown
---
type: meal-plan
week_of: 2026-04-28
provenance: synthesized
created: 2026-04-27
modified: 2026-04-27
tags: [meal-plan, food]
---

## Synopsis

Meal plan for the week of April 28. 5 home-cooked dinners, 1 takeout,
1 leftover night. Shopping list grouped by section.

## Plan

| Day | Dinner | Notes |
|---|---|---|
| Mon | [[lemon-herb-chicken]] | Defrost chicken Sun night |
| Tue | [[one-pot-pasta-primavera]] | Use zucchini before it turns |
| Wed | [[sheet-pan-salmon]] | — |
| Thu | Leftovers | — |
| Fri | Takeout | Thai or pizza, family vote |
| Sat | [[slow-cooker-chili]] | Start at noon |
| Sun | [[grain-bowl]] | Clear the fridge |

## Shopping List

**Produce:** zucchini (2), bell peppers (3), lemons (4), garlic, baby spinach

**Protein:** chicken thighs (2 lbs), salmon fillets (4), ground turkey (1.5 lbs)

**Pantry:** pasta (1 lb), crushed tomatoes (2 cans), chicken broth (32 oz)

**Dairy:** parmesan, plain Greek yogurt
```

---

## Capturing new content

The pattern: tell Claude what you have, paste or point to source material, and let it land in the right place with the right frontmatter.

### Family members

```
Add a person to the household: {name}, {birth year}, {role: parent / child / pet / extended-family}.
Notes: {dietary, medical, anything important}.
```

Lands at `wiki/people/{name}.md`. Re-run with new info to update.

### Recipes

From a URL, scanned recipe card, photo, or just typed-out:

```
Save this recipe: {URL or paste}. Source: {who shared it / where it came from}.
Family adjustments we usually make: {any tweaks}.
```

Lands at `wiki/food/{slug}.md` with ingredients, steps, prep time, servings, dietary tags, and a link to `dietary-notes.md` if it triggers any allergens.

### Medical records (visits, EOBs, lab results, prescriptions)

Drop the document into `raw/health/{name}/` (or paste the contents), then:

```
Ingest this medical document for {name}: {file path or paste}.
Surface any follow-ups with dates.
```

Updates `wiki/health/{name}-medical.md`, `medications.md` if prescriptions changed, `providers.md` if a new provider appeared. Surfaces follow-ups as `> [!important] Follow-up due by {date}` callouts that the **follow-up tracker** picks up.

### School documents (report cards, IEPs, school newsletters)

```
Ingest this school document for {child's name}: {file path or paste}.
```

Updates `wiki/education/{child}/academic.md`, `activities.md`, and surfaces deadlines.

### Trips (planning + journaling)

```
Start trip planning: {destination}, {dates}, traveling with {who}.
Goals: {what we want to do — relax, hike, visit family, ...}.
```

Scaffolds `wiki/travel/upcoming/{slug}/` with itinerary, packing list, points-of-interest research, and a pre-trip task list. After the trip:

```
Wrap up the {destination} trip: {what we did, what we'd do differently}.
Move it from upcoming/ to past/.
```

### Home maintenance + repairs

```
Log a home repair: {what broke}, {who fixed it}, ${cost}, {date}.
Add the vendor to vendors.md if not already there.
```

Updates `wiki/home/maintenance/history.md`, the relevant system page (HVAC, plumbing, etc.), and `vendors.md`. If recurring (e.g., HVAC service every 6 months), it lands in `maintenance/schedule.md` too.

### Vehicles

```
Log a service for {vehicle name}: {what was done}, {mileage}, ${cost}, {date}.
```

Updates `wiki/home/vehicles/{name}.md` service history.

### Vendors and contractors

```
Add a vendor: {name}, {trade — plumber/electrician/etc.}, phone {N}, used for {context}.
Quality: {your rating + 1-2 sentences}.
```

Lands at `wiki/home/vendors.md` (or `wiki/network/relationships/{slug}.md` for service providers we use repeatedly). Future repairs auto-link.

### Receipts (proof of purchase, warranties, taxable items)

Drop the photo or PDF into `raw/finances/receipts/`, then:

```
Ingest this receipt: {file path}.
Tag whether it's tax-relevant or warranty-relevant.
```

Creates a companion page; tax-relevant items also link from `wiki/finances/tax/{year}/`.

### Subscriptions

```
Track a subscription: {service}, ${cost} per {month/year}, paid by {whoever}, started {date}.
```

Lands at `wiki/finances/subscriptions/{slug}.md`. Renders via `wiki/finances/subscriptions/subscriptions.base` so you can spot duplicates and stale ones.

### Holdings (investments)

```
Add a holding: {ticker / fund name}, account {brokerage}, owned by {name}, {shares} shares.
```

Lands at `wiki/finances/holdings/{slug}.md`.

### Tax documents (W-2, 1099-*, 1098, K-1)

Drop the form into `raw/finances/tax/{year}/`, then:

```
Ingest this tax document: {file path}.
```

Creates a structured `wiki/finances/tax/{year}/{form-type}-{slug}.md` page. The collection makes tax filing season far less painful.

### Memories and milestones

```
Capture a memory: {date}, {what happened}, {who was there}.
```

Lands at `wiki/memories/{date}-{slug}.md`. Photos go in an `_assets/` folder with companion pages.

### Bookmarks and web clips

```
Bookmark {URL} with note: {why it's useful — recipe to try, school resource, ...}.
```

Or, if using the [Obsidian Web Clipper](https://obsidian.md/clipper), clips land in `Clippings/` and you run `Process pending clippings.` to route them.

### Restaurants and points of interest

```
Add a restaurant: {name}, {cuisine}, {neighborhood}, last visited {date}.
What we usually order: {dishes}.
```

Lands at `wiki/food/restaurants/{slug}.md`. Render the full collection via `wiki/food/restaurants/restaurants.base` filtered by cuisine, neighborhood, or kid-friendly tag.

### Documents (PDF, .docx, .xlsx)

Drop the file in the appropriate `raw/` subfolder, then:

```
Ingest this document: raw/{folder}/{filename}.
```

The `ingest-document` skill (uses Docling) extracts to clean markdown and creates a co-located companion page so the file shows up in the graph and search.

---

## Producing deliverables

Operations read structured wiki pages and write derived pages back. The output is itself a wiki page subsequent operations can consume.

### Weekly meal plan + shopping list
```
Plan meals for next week. {Constraints, who's around, what's in the fridge}.
```

### Follow-up tracker (medical / vehicle / home — next 60 days)
```
Show me everything due in the next 60 days.
```
Reads follow-up callouts on health, vehicle, and home pages plus follow-ups on people pages.

### Trip prep (packing list + pre-trip tasks)
```
Generate a packing list and pre-trip task list for the upcoming {destination} trip.
```

### Weekly digest (what changed across the household)
```
Produce this week's digest of household changes.
```
Lands at `wiki/syntheses/weekly-{YYYY-MM-DD}.md`.

### Medical summary (synthesize one person's recent care)
```
Summarize {name}'s medical care over the last 6 months.
```
Useful before a specialist appointment or for sharing with another caregiver.

### Recipe recommender (given context)
```
What should we cook tonight? We have {ingredients on hand}, {30 minutes}, {kid-friendly}.
```

---

## Querying the vault

Just ask. Claude uses **progressive loading** — it scans `wiki/index.md`, then page synopses, and only reads full pages once it's confirmed relevance. That keeps token use low even when the vault grows.

Examples:

- `When is Jake's next dentist appointment?`
- `What's the recipe for Grandma's Thanksgiving stuffing?`
- `Who was the plumber that fixed the leak last year?`
- `What's our home insurance deductible?`
- `What medications is Mom currently taking?`
- `Have we been to {restaurant} before? What did we get?`
- `Which subscriptions auto-renew this month?`

If a query would be useful to future questions, ask Claude to save the answer:

```
Save that as a reference page in wiki/reference/.
```

---

## Folder map

```
{your-vault}/
├── CLAUDE.md                    # Root agent contract (don't edit)
├── purpose.md                   # Your family's scope statement (you edit this)
├── _variant/
│   └── CLAUDE.variant.md        # Family-variant schema (edit identity sections only)
├── _templates/                  # Page templates with {{placeholder}} fields
│   ├── person.md
│   ├── recipe.md
│   ├── restaurant.md
│   ├── ...
├── raw/                         # Immutable source documents (drop files here)
├── wiki/                        # Structured pages (your source of truth)
│   ├── index.md                 #   Family dashboard
│   ├── people/                  #   One page per family member, pet, extended-family contact
│   ├── health/                  #   Per-person summaries, providers, insurance, medications
│   ├── education/{child}/       #   Per-child academic + activities
│   ├── home/                    #   Maintenance, vendors, appliances, vehicles
│   ├── finances/                #   Subscriptions, holdings, tax docs, accounts
│   ├── food/                    #   Recipes, meal plans, restaurants, dietary notes
│   ├── travel/                  #   Upcoming + past trips, points of interest
│   ├── pets/                    #   Pet records and care
│   ├── memories/                #   Family milestones and stories
│   ├── reference/               #   General household reference
│   ├── bookmarks/               #   URL bookmarks + homepage.base
│   └── research/                #   Multi-source research projects (e.g., heat pump, school choice)
├── outputs/                     #   Claude-generated deliverables
├── log/
│   └── changelog.md             #   Append-only change log
└── .claude/
    ├── skills/                  #   Agent skills (you populated this in setup)
    └── research-providers.yaml  #   API keys for research dispatch (optional)
```

---

## Authoring rules in 30 seconds

These are enforced by `CLAUDE.md` and the `wiki-lint` skill:

- **Filenames are kebab-case** (`grandmas-thanksgiving-stuffing.md`), dates are **ISO 8601** (`2026-04-25`).
- **Every page has YAML frontmatter** (`type`, `status`, `provenance`, `created`, `modified`, `tags`).
- **Every page has a `## Synopsis` section** — 2-3 sentences. This is what enables progressive loading.
- **`provenance:`** is `extracted` (transcribed from a source) | `synthesized` (LLM-generated) | `mixed`.
- **Internal links are wikilinks**: `[[page-name]]`, not relative paths.
- **Non-text files get a markdown companion page** in an `_assets/` folder — that's how they show up in the graph and search.
- **Filenames are canonical slugs — never rename them.** Update `title:` and `aliases:` in frontmatter instead.
- **Sensitive freshness flags**: medical >6mo gets `> [!warning]`; financial >1yr gets `> [!warning] Verify`; medications >3mo gets `> [!warning] Confirm dosage`.

---

## Health checks

Run on demand or weekly:

```
Lint the vault and write the report to log/lint-{today}.md.
```

Detects: orphan pages, stale items, broken wikilinks, missing synopses, contradictions, raw files never synthesized, and tag drift.

Underlying scripts (Python 3.10+):
```bash
pip install pyyaml
python .claude/skills/wiki-lint/scripts/tag-lint.py .
python .claude/skills/wiki-lint/scripts/convergence-debt.py .
```

---

## Going further

- **Add custom skills** — drop a new directory under `.claude/skills/{skill-name}/` with `SKILL.md`, `scripts/`, `evals/evals.json` per the [Agent Skills spec](https://agentskills.io/specification). Examples: a custom skill for tracking sports schedules, school lunch menus, or a hobby community.
- **Add custom page templates** — drop `_templates/{type}.md` and add the type to `_variant/CLAUDE.variant.md`'s page-types table.
- **Customize tone, ontology, or sensitive-info handling** — edit `_variant/CLAUDE.variant.md`.

---

## Privacy and safety

A family vault holds medical, financial, and personal records. The defaults err on the side of privacy:

- **The vault runs entirely on your machines.** Nothing leaves unless you explicitly enable a research integration (Perplexity / Gemini / Semantic Scholar) for a specific query.
- **Use private sync** — OneDrive / iCloud / Google Drive personal accounts inherit your existing access controls and encryption. If using Git, keep the repo private.
- **Sensitivity tagging** — anything you flag as sensitive in `_variant/CLAUDE.variant.md` is never surfaced unprompted (e.g., a child's medical condition stays put unless asked).
- **Never delete files without asking** — the agent archives instead.
- **`raw/` is immutable** — never modify ingested source documents after the fact.
- **Review what Claude proposes before you accept.** Family wikis stay trustworthy only with human curation.
