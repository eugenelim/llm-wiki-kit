# Family Knowledge System Design

## Architecture: Household as an Active Operating System

The family variant takes the LLM Wiki pattern and pushes it past "knowledge management." A team wiki primarily *stores and retrieves* — engineers read it to ground decisions, write it to capture context for the next session. A family wiki has a different center of gravity: it has to *operate*. Meals get planned each week. Dentist visits come due. The HVAC filter needs replacing. A trip is three weeks out and the packing list doesn't exist yet. These aren't query operations against a knowledge base; they're scheduled actions that draw on the knowledge base as input.

The design treats the family vault as two layers stacked on the same markdown substrate:

1. **A knowledge base** — structured records of who's in the family, what their health looks like, what recipes work, where things are in the house, what's happened in the past.
2. **An operating layer** — recurring operations (meal planning, follow-up tracking, trip prep, weekly digests) that read the knowledge base, compose, and write new pages back into it as plans, reminders, and schedules.

The same Obsidian vault, the same `CLAUDE.md` schema, the same ingest pipeline. The difference from the work variant is what dominates: family vaults that fail almost always fail because nobody used them — the capture loop ran but the operate loop never started. Recipes accumulate but no meal gets planned. Medical records get filed but the follow-up never happens. The wiki becomes a digital filing cabinet that no one opens.

This document describes the family variant's architecture, ontology, and the two patterns that make the operate loop work: **structured ingestion** (recipes, medical records, receipts, trips arrive in a form the operating layer can use) and **operations** (planning, reminding, synthesizing, recommending, responding to crisis).

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    FAMILY KNOWLEDGE OS                            │
│                                                                   │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│   │  Captures   │    │   Structured  │    │   Operations     │   │
│   │             │ →  │     Wiki      │ →  │     Layer        │   │
│   │  Recipes    │    │              │    │                  │   │
│   │  EOBs       │    │  people/     │    │  Meal planning   │   │
│   │  School docs│    │  health/     │    │  Follow-up calls │   │
│   │  Receipts   │    │  food/       │    │  Trip prep       │   │
│   │  Trip emails│    │  home/       │    │  Maintenance     │   │
│   │  Photos     │    │  travel/     │    │  Weekly digest   │   │
│   │  Conversations│  │  ...         │    │                  │   │
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
│         │(parents)│    │(everyone)│    │ (kids) │                │
│         └────────┘     └──────────┘    └────────┘                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

Two flows traverse the system:

- **Capture flow** (left → middle): a recipe URL, a doctor's visit summary, a receipt photo, a school newsletter — anything family-relevant — is ingested through a specialized ingester that produces a *structured page* in the right wiki location with the right frontmatter. Recipes in `food/`. Medical records in `health/{person}/`. Trips in `travel/upcoming/`.
- **Operate flow** (middle → right): on demand or on a schedule, an operation skill reads the relevant structured pages, composes a derived artifact (this week's meal plan, the trip packing list, the home maintenance schedule), and writes it back into the wiki as a new structured page. The output of an operation is itself wiki content, which subsequent operations can read.

The agent layer at the bottom — Claude Code for parents who want full file-system access, Claude Cowork for whoever's at the kitchen table, Claude Chat with web search for quick lookups — all read and write the same vault.

---

## Layer 1: Storage & Sync

### Single shared vault per household

A family is one operational unit. Use one vault, not one per parent. The whole point is shared visibility — any parent can ask "when's Jake's next checkup?" and get the same answer. Splitting the vault by parent reintroduces the very problem the wiki is meant to solve.

### Shared cloud drive is the right default

Most households already have OneDrive, Google Drive, or Dropbox set up for photos and shared documents. Drop the vault folder inside that synced location and Obsidian opens it on every device — no new infrastructure, no Git literacy required.

For families, **don't use Git unless someone in the household actively wants to** — it adds friction the use case doesn't reward. The full sync-vs-Git tradeoff and the Google Workspace caveats around Office formats live in [`guides/sync-options.md`](../guides/sync-options.md).

### Multi-device access, multi-caregiver coordination

A typical family has at least two adults editing the wiki. Possibly aging parents at a distance. Possibly older kids. Conflicts are rare in practice because most family pages are written rarely (medical visits, recipes, vendor records) and read often.

Practical guidance:
- The agent (Claude Code/Cowork) is the primary writer. Humans mostly read.
- If both parents and the agent might edit the same page, queue the writes — agent operates first, human reviews after.
- Don't both edit `home/maintenance/schedule.md` at the same time.

### Privacy posture

A family vault contains medical records, financial info, kid info, and addresses. Treat it accordingly:

- **Vault location.** Put it on each adult's primary machine via cloud drive sync. Don't sync to kids' shared tablets unless that's intentional.
- **Cloud provider.** All major cloud drives (OneDrive, Google Drive, Dropbox) provide encryption at rest and in transit. Pick whatever the household already has.
- **External tools that touch the vault.** Be deliberate about what you point at it. Default research tools (Perplexity, Semantic Scholar) accept a query and return an answer — they don't see the vault. The web ingester (`ingest-website`) sends URLs to defuddle locally by default; the pure.md fallback caches URLs and should never receive intranet/auth links (see [`skills/shared/ingest-website/SKILL.md`](../../skills/shared/ingest-website/SKILL.md)).
- **Children's access.** Younger kids don't need direct access; a parent queries on their behalf. Older kids who do have access should have their own machine login and read-only navigation of the vault is fine. A teenager who wants their own private journal is well-served by their *own* vault, not a private folder inside the family one.

What never enters the family wiki:
- Plain-text passwords or recovery keys (use a password manager).
- Other families' private information without consent (a friend's medical detail Sarah told you in confidence — out).
- Information about anyone who hasn't agreed to be in the wiki (an estranged relative; an in-law's medical history).

---

## Layer 2: Ontology — People First, Domains Second

The work variant organizes by *project*. The family variant organizes by *person*, with topical domains as the secondary axis. This isn't cosmetic — it shapes how knowledge gets retrieved.

When a family member asks a question, they almost always start from a person:

- "What's Jake's next dentist appointment?" → `wiki/people/jake.md` → `wiki/health/jake-medical.md`
- "What was Sarah's blood pressure at the last visit?" → `wiki/people/sarah.md` → `wiki/health/sarah-medical.md`
- "What grade is Mia in?" → `wiki/people/mia.md` → `wiki/education/mia/overview.md`

Domains capture cross-person and household-level context — providers serve the whole family, the home is owned by all of them, recipes are cooked for all of them. So the ontology is:

```
wiki/
├── index.md                 # Family dashboard
├── people/                  # One page per family member (the entry points)
├── health/
│   ├── {name}-medical.md    # Per-person medical summaries
│   ├── providers.md         # Doctors, dentists, specialists, vet
│   ├── insurance.md         # Plans, deductibles, claim contacts
│   ├── medications.md       # Current medications across the family
│   └── history/             # Past visits, lab results, immunization records
├── education/
│   └── {child-name}/        # School records, activities, teachers
├── home/
│   ├── overview.md
│   ├── maintenance/         # Schedule + history
│   ├── vendors.md           # Plumber, electrician, HVAC, lawn, etc.
│   ├── appliances.md        # Model numbers, warranties, manuals
│   └── vehicles/            # Per-vehicle records and service history
├── finances/
├── food/
│   ├── family-favorites/    # Recipes the whole family likes
│   ├── weeknight/           # Quick recipes for school nights
│   ├── dietary-notes.md     # Allergies, preferences, restrictions per person
│   └── meal-plans/          # Output of the meal-planning operation
├── travel/
│   ├── upcoming/            # Trips in planning
│   └── past/                # Trip journals and learnings
├── pets/
├── memories/                # Milestones, stories, family lore
└── reference/               # Misc household info
```

### Ontology design principles

1. **People are the primary entry point.** The dashboard (`wiki/index.md`) lists people prominently. Every domain folder either has per-person pages (`{name}-medical.md`, `{child-name}/`) or whole-household pages that cross-reference people. A parent should be able to open the wiki, click a name, and reach every domain that touches that person.

2. **Domains are stable; people are dynamic.** People come and go (new baby, kid moves out, grandparent passes). The domain structure stays put. Don't restructure folders when the household changes — add or archive person pages.

3. **Cross-link aggressively.** A recipe references the dietary notes of each family member. A medical record references the person and the provider. A vendor in `home/vendors.md` cross-links from every maintenance event that used them. The graph is the thing — the more wikilinks, the more value the wiki delivers to operations.

4. **Currency matters more than completeness.** A medical summary that's six months stale is worse than no summary at all, because someone might rely on it. The kit's outdated-info callouts (>6mo medical, >1yr financial, >3mo medications) flag these for review. Don't aim to capture everything; aim to keep what's captured *current*.

5. **Low-friction capture beats schema rigidity.** When a parent has 90 seconds between dropping a kid at school and the next thing, getting "Mia got a tetanus shot today, due again in 10 years" into the vault matters more than getting the frontmatter exactly right. The agent fixes the frontmatter on ingest; the human just dumps the fact.

### Page types

| Type | Description | Location |
|---|---|---|
| `index` | Folder navigation | Any folder |
| `person` | Family member profile | `wiki/people/` |
| `medical` | Visit notes, summaries, lab results | `wiki/health/` |
| `provider` | Doctor, dentist, specialist, vet | `wiki/health/providers.md` |
| `school` | School and education records | `wiki/education/` |
| `recipe` | Family recipes (structured) | `wiki/food/` |
| `meal-plan` | Output of meal-planning operation | `wiki/food/meal-plans/` |
| `trip` | Travel plans and journals | `wiki/travel/` |
| `home` | Home maintenance and property | `wiki/home/` |
| `vehicle` | Vehicle records and service history | `wiki/home/vehicles/` |
| `financial` | Accounts, deductibles, key dates | `wiki/finances/` |
| `vendor` | Service-provider contacts | `wiki/home/vendors.md` |
| `pet` | Pet care and records | `wiki/pets/` |
| `memory` | Family milestones and stories | `wiki/memories/` |
| `reference` | General household reference | `wiki/reference/` |
| `asset` | Companion page for non-text files | Co-located |

The work variant has lifecycle states (`draft`, `ready`, `active`, `in-progress`, `review`, `done`, `archived`, `superseded`). Family doesn't need that complexity — three values cover it: `current`, `outdated`, `archived`. A medical summary is `current` until a newer visit produces a newer summary; a vehicle becomes `archived` when sold; a recipe becomes `outdated` if the family decided they don't make it anymore.

---

## Layer 3: Schema — `_variant/CLAUDE.variant.md`

The family variant extends the root `CLAUDE.md` with family-specific identity, sensitive-info rules, and operations. Full schema in `vault-templates/family/_variant/CLAUDE.variant.md`. Highlights:

**Identity and tone.** Friendly, clear, practical. Family members of all ages may ask questions. If a child asks, adjust language to be age-appropriate. Always be specific — "Dr. Chen at Riverdale Pediatrics, phone 555-0123" is better than "check the providers page."

**Sensitive-information rules.** Medical, financial, and legal information must be handled with care. Never surface one family member's private information unprompted. Flag information that seems outdated (>6mo medical, >1yr financial, >3mo medications) with `> [!warning]` callouts.

**Tagging taxonomy.**
- *Person:* `#jake`, `#sarah`, `#family` (use first names)
- *Domain:* `#medical`, `#school`, `#financial`, `#home`, `#food`, `#travel`
- *Urgency:* `#follow-up`, `#deadline`, `#recurring`
- *Season:* `#spring`, `#summer`, `#fall`, `#winter` (for seasonal tasks)

The variant doc also defines per-domain ingest steps (medical records, recipes, home maintenance, school records). Those steps are the seed of what becomes — in this design — the **structured-ingestion pattern** below.

---

## Layer 4: Structured Ingestion

This is the first of the two patterns that make the family wiki actively useful rather than just a filing cabinet.

### The two-axis model

The kit's orchestrator (`skills/shared/ingest/SKILL.md`) currently routes by **source type** — URL, PDF, paste, image. Source-type ingesters produce clean markdown in `raw/`:

- `ingest-website` (URL → defuddle / pure.md → markdown)
- `ingest-document` (PDF/DOCX/etc → docling → markdown)

But for a family vault, source type isn't enough. A recipe URL and an article URL both go through the same source-type ingester, but they need very different downstream handling:

- An article goes through generic article extraction → optionally update domain pages → research brief in `research/`.
- A recipe needs ingredient extraction → step parsing → cross-reference dietary notes → land in `wiki/food/{slug}.md` with the recipe template's frontmatter (servings, prep_time, source, dietary tags) → register with the recipe library so meal-planning can use it.

The family variant introduces a second axis: **content type**. The orchestrator routes by source-type to clean the input, then by content-type to structure it.

```
Source                  Source-type            Content-type
arrives                 ingester               ingester
                        (cleans)               (structures)
   │                        │                       │
   ▼                        ▼                       ▼
Recipe URL ──────► ingest-website ───────► ingest-recipe ──────► wiki/food/{slug}.md
                       │                       │                      (recipe template)
                       │                       ▼
                       │                  Cross-link dietary-notes
                       │                  Register with recipe library
                       ▼
EOB PDF ──────────► ingest-document ───► ingest-medical-record ──► wiki/health/{person}-medical.md
                                                  │                  (visit appended)
                                                  ▼
                                             Update medications.md if changed
                                             Flag follow-up if needed
```

Source-type ingesters are *generic* — they only know how to clean. Content-type ingesters are *family-specific* — they know the schema for their target wiki section.

### Content-type ingesters in the family variant

The MVP set:

| Content-type ingester | Handles | Target location | Schema applied |
|---|---|---|---|
| `ingest-recipe` | URL, scanned card, conversation, photo | `wiki/food/{slug}.md` | Ingredients, steps, servings, prep/cook time, source attribution, dietary tags, allergen cross-refs |
| `ingest-medical-record` | EOB PDF, visit summary, lab result | `wiki/health/{person}-medical.md` (append) + `wiki/health/medications.md` if changed | Date, provider, summary, follow-ups, prescription changes |
| `ingest-receipt` | Receipt photo, PDF, statement entry | `wiki/finances/` or appropriate domain | Vendor, amount, date, category, what it was for |
| `ingest-school-doc` | Report card, calendar, permission slip, newsletter | `wiki/education/{child}/` | Date, type (academic / activity / admin), key dates, action items |
| `ingest-trip` | Itinerary, confirmation email, hotel booking | `wiki/travel/upcoming/{date}-{destination}.md` | Dates, accommodations, activities, packing-list trigger |

Each one composes the source-type ingester it needs (the recipe-from-URL case calls `ingest-website` first; the recipe-from-photo case calls `ingest-document`), then applies content-type structuring.

### Walkthrough: ingesting a recipe from a webpage

The canonical example. A parent says: *"Add this to our recipes: https://example.com/sheet-pan-chicken-tacos."*

1. **Routing.** The orchestrator sees the URL and the user-stated content type ("recipes"). It dispatches to `ingest-recipe`.
2. **Cleanup.** `ingest-recipe` calls `ingest-website` internally, which uses defuddle to fetch and strip the page to clean markdown — ads, navigation, "you might also like" sidebars all gone.
3. **Schema extraction.** `ingest-recipe` parses the cleaned markdown looking for recipe structure. Most recipe sites embed schema.org/Recipe microdata — `ingest-recipe` checks the original HTML if available, or falls back to heuristic parsing of the cleaned text:
   - Title (article H1)
   - Ingredients list (typically a `<ul>` near the top of the body)
   - Instructions (numbered list or stepped paragraphs)
   - Servings, prep time, cook time (often in a metadata block)
   - Source URL and author attribution
4. **Apply the recipe template.** The structured fields populate `_templates/recipe.md`'s frontmatter. The body fills in `## Ingredients`, `## Instructions`, etc.
5. **Cross-link.** `ingest-recipe` reads `wiki/food/dietary-notes.md` and tags the recipe accordingly: if Jake is gluten-free and the recipe contains soy sauce (typical wheat-derived), add `> [!warning] Contains gluten — Jake.` If Sarah is dairy-free and the recipe has cheese, flag similarly. Use the per-person dietary tags to populate the recipe's `dietary:` frontmatter.
6. **Interactive review.** The agent presents to the user:
   ```
   Recipe extracted: Sheet-Pan Chicken Tacos
   Servings: 4 · Prep: 15 min · Cook: 25 min
   Source: https://example.com/sheet-pan-chicken-tacos

   Allergen flags:
   - ⚠ Gluten — Jake (soy sauce in marinade)

   Dietary tags: weeknight, mexican, sheet-pan
   Save to: wiki/food/family-favorites/sheet-pan-chicken-tacos.md

   Save, or adjust?
   ```
7. **Register.** On save, append to `wiki/food/family-favorites/index.md` (or `weeknight/index.md`). The recipe library is now one entry richer.
8. **Changelog.** A line in `log/changelog.md`.

The full operation is the same shape as any other ingest — read `purpose.md`, check for contradictions (does another recipe with the same name exist? would this overwrite?), produce a structured page, run the shared post-flow. The difference is that the output is a *typed* page that downstream operations (meal planning) can mechanically consume.

### Walkthrough: ingesting a medical record from an EOB

A parent uploads a PDF — the explanation-of-benefits from Jake's last pediatric visit.

1. **Routing.** The orchestrator sees the PDF; the user says "Jake's last visit." Dispatch to `ingest-medical-record`.
2. **Cleanup.** `ingest-medical-record` calls `ingest-document` to convert the PDF to markdown via docling.
3. **Schema extraction.** `ingest-medical-record` parses the cleaned markdown for:
   - Date of service
   - Provider name and specialty
   - Reason for visit
   - Diagnoses (ICD-10 codes if present, plain-text otherwise)
   - Procedures and CPT codes
   - Prescriptions written
   - Follow-up instructions ("recheck in 6 months," "schedule allergy panel")
   - Cost breakdown (insured, patient responsibility)
4. **Per-person summary update.** Append a dated entry to `wiki/health/jake-medical.md`. The summary stays in reverse chronological order with a current-status block at the top.
5. **Side-effects.**
   - If a new prescription appears → update `wiki/health/medications.md` with start date, dose, prescriber.
   - If a new provider appears → check `wiki/health/providers.md`; add if missing.
   - If a follow-up is required → log to `wiki/health/jake-medical.md` with `> [!important] Follow-up due by 2026-10-15` and create a corresponding line in the operation queue (see Layer 5).
6. **Companion page for the source PDF.** The PDF lives in `_assets/`; a companion page in `health/` links to it.
7. **Privacy gate.** Medical content stays in the vault; the agent never sends it to external research tools.
8. **Interactive review.** The agent shows the parent what it extracted before writing — particularly the follow-up triggers, since those become operations.

### Why this matters for the operate loop

If recipes are just "wiki pages with prose," meal planning has to read each one and re-extract the ingredients and dietary fit at planning time. That's expensive and fragile. If recipes are *structured pages* with consistent frontmatter (servings, prep_time, dietary) and consistent body sections (ingredients as a list, steps as a numbered list), meal planning becomes a query — *give me four weeknight recipes, total prep ≤ 90 min, all dietary-compatible with Jake and Sarah*.

The same logic applies to medical follow-ups (queryable: *who in the family has a follow-up due in the next 60 days?*), home maintenance (*what's in season this month?*), trips (*what's coming up that needs prep?*). Structured ingestion is the precondition for the operations layer.

### Adding a new content-type ingester

When the family encounters a recurring source type the existing ingesters don't handle well — say, sports-team game schedules, or babysitter availability calendars — the path is:

1. Decide the schema for the target wiki page (what fields, what sections).
2. Create or repurpose a template in `_templates/`.
3. Author `skills/family/ingest-{type}/SKILL.md` describing extraction, schema mapping, cross-links, and side-effects.
4. Register the trigger signal (file extension, URL pattern, user-stated intent) in the orchestrator's source-type-detection table.

Most households will need 5-10 content-type ingesters total. The recipe one earns its keep faster than any other; the medical one earns its keep most by what it prevents (missed follow-ups).

---

## Layer 5: Operations — The Active OS Pattern

This is the second pattern, and the one that turns the wiki from filing cabinet into operating system.

### What an operation is

An **operation** is a skill that:

1. Reads a defined set of structured pages from the wiki.
2. Applies a domain-specific algorithm (meal planning, follow-up scheduling, trip prep, etc.).
3. Writes a new structured page back into the wiki as the result.

The result page is itself queryable, linkable, and consumable by subsequent operations. A meal plan is a wiki page; a shopping list is a wiki page derived from the meal plan; a kitchen prep schedule could be derived from both.

Operations are explicitly different from ingest in two ways:

- Ingest: external source → wiki. Operation: wiki → wiki.
- Ingest: triggered by a captured artifact. Operation: triggered by a request (user-driven) or a schedule (e.g., every Sunday).

### The five operation classes

| Class | What it does | Family examples |
|---|---|---|
| **Planning** | Compose a forward-looking artifact from current wiki state | Weekly meal plan; trip packing list; home maintenance schedule for the season |
| **Reminding** | Surface time-sensitive items by reading dated metadata | "Follow-ups due in the next 30 days"; "vehicle services overdue"; "vaccinations approaching" |
| **Synthesizing** | Compress a wide span of wiki content into a digest | "What's the family's week look like?"; "Year-end review of family health"; "Summary of last summer's trips" |
| **Recommending** | Apply ranking/filtering to a library given a context | "Recipe suggestions for tonight given what's in the fridge"; "Trip ideas for spring break under $X budget"; "Movies for family night that everyone hasn't seen" |
| **Crisis-responding** | Rapid composition of relevant info under time pressure | "Jake's running a fever — gather his current meds, allergies, pediatrician contact, after-hours line"; "Power's out — vendors and procedures"; "Lost wallet — what cards to call, where insurance docs are" |

The same wiki content participates in multiple operation classes. Recipe pages feed the meal-plan planner *and* the recipe recommender *and* the seasonal-suggestions synthesizer.

### Walkthrough: meal planning

A parent on Sunday afternoon: *"Plan meals for this week."*

The `meal-planning` skill runs roughly this:

1. **Read the inputs.**
   - All recipe pages in `wiki/food/family-favorites/` and `wiki/food/weeknight/`. Group by `dietary` tags, prep time, last-cooked date.
   - `wiki/food/dietary-notes.md` — current restrictions per family member (Jake gluten-free, Sarah no shellfish, Mia hates mushrooms).
   - The most recent meal plan in `wiki/food/meal-plans/` — what was cooked last week, to avoid immediate repetition.
   - The family calendar context if available — Tuesday Jake has soccer (need a 30-minute meal), Friday is a regular pizza night, Saturday everyone's home (more ambitious meal OK).
   - Optional: leftovers / what's in the fridge if the household tracks that. (Most don't; it's fine.)

2. **Apply the algorithm.**
   - Honor the hard constraints (no gluten in any meal Jake eats, no shellfish).
   - Spread cuisines across the week (don't have Italian three nights in a row).
   - Match prep time to calendar (≤30 min on the soccer night).
   - Avoid recipes cooked in the last 2 weeks unless they're the family's top favorites.
   - Suggest one stretch recipe for the weekend — something the family hasn't made before, or a seasonal fit.

3. **Compose the output.** Write `wiki/food/meal-plans/2026-04-26-week.md`:
   ```markdown
   ---
   type: meal-plan
   week: 2026-04-26
   created: 2026-04-25
   modified: 2026-04-25
   tags: [meal-plan]
   status: current
   ---

   ## Synopsis
   Meal plan for week of April 26. Five planned meals + Friday pizza
   night + Saturday flexibility. Average prep: 35 min. All dietary-
   compatible with current restrictions.

   ## Schedule

   ### Sunday 4/26
   [[recipes/family-favorites/sheet-pan-chicken-tacos]] · 40 min
   *Why:* Jake-safe, batch-friendly for leftovers.

   ### Monday 4/27
   [[recipes/weeknight/lemon-pasta]] · 25 min
   *Why:* Sarah's pick; gluten-free pasta swap noted.

   ### Tuesday 4/28 (Jake at soccer 5-7pm)
   [[recipes/weeknight/chicken-rice-bowl]] · 30 min
   *Why:* Quick, kid-friendly, holds well in the oven.

   ### Wednesday 4/29
   Leftover sheet-pan tacos.

   ### Thursday 4/30
   [[recipes/family-favorites/garlic-shrimp-broccoli]] · 35 min
   *(Sarah is at her mother's; Jake/Mia/parent eat — shrimp is OK
   for the three of them.)*

   ### Friday 5/1
   Pizza night (regular).

   ### Saturday 5/2 — stretch recipe
   [[recipes/weeknight/marrakesh-chicken]] · 60 min
   *Why:* New for the family, North African flavors,
   forgiving timing for a Saturday.

   ## Shopping list

   *(Aggregated from this week's recipes minus what's typically
   stocked. See [[food/pantry-staples]] for the assumed baseline.)*

   - Chicken thighs (3 lbs)
   - Bell peppers (3)
   - Cilantro
   - ...

   ## Notes for next week's planner

   - Marrakesh chicken is new — capture family reactions in
     the recipe page so it lands correctly in future plans.
   - Sarah away Thursday; can schedule shrimp/shellfish for
     a similar slot.
   ```

4. **Side-effects.**
   - Update `wiki/food/meal-plans/index.md` with the new week.
   - Optionally push key items to a shopping app, calendar, etc., via downstream skills.

5. **Interactive review.** The parent reviews. Adjustments propagate — if they swap Tuesday for take-out, the shopping list updates.

### What makes this different from "Claude can write a meal plan"

Anyone with an LLM can ask for a meal plan. What makes the family-OS version distinct:

- **The recipe library is the source.** No invented recipes. Every meal in the plan is a real wikilink to a recipe the family has already vetted.
- **Constraints come from the wiki.** Dietary restrictions aren't re-explained each week — they live in `dietary-notes.md` and update once when they change.
- **Outputs feed back in.** The meal plan page is the input to the next week's planner ("don't repeat what you cooked last week"). Family reactions to a stretch recipe get captured in the recipe page, improving future suggestions.
- **The operation is reusable.** A neighboring family can drop their own recipes into the same vault structure and run the same planning operation; no re-implementation.

### Other operations worth authoring

These are the high-leverage ones. P2 in the kit's roadmap; not all need to ship at MVP.

| Operation | Inputs | Output | Cadence |
|---|---|---|---|
| **Weekly digest** | `index.md` of each domain, recent changelog entries | `wiki/log/digest-{week}.md` summarizing what changed | Sunday morning |
| **Follow-up tracker** | All `wiki/health/{person}-medical.md` pages, scanning for follow-up callouts and dates | `wiki/health/follow-ups.md` listing items due in 60 days | Run weekly |
| **Vehicle service due** | `wiki/home/vehicles/*.md`, current odometer + last service date | `wiki/home/vehicles/upcoming.md` | Run monthly |
| **Trip prep** | `wiki/travel/upcoming/{trip}.md`, family member docs (passports, allergies, etc.) | Packing list + pre-trip task list as appended section in trip page | Run on demand 2-3 weeks pre-trip |
| **Recipe recommender** | Recipe library, dietary notes, "what's in the fridge" if tracked, season | Top-N candidates for tonight | Run on demand |
| **Year-end review** | Full vault, focused on memories/, health/, travel/, food/ | `wiki/memories/{year}-review.md` | Run once per year (December) |

### Operations as the wiki's heartbeat

A family wiki without operations dies in 2-4 months. The capture loop runs at first (someone enthusiastic about the new system files everything for two weeks), the operation loop never starts, the family stops getting visible value, capture tapers off, and the wiki becomes a graveyard of half-filled records.

The cure: ship one operation as soon as the wiki is populated enough to support it. Meal planning is the gateway because it has the highest weekly visibility — every household plans meals and shops, every household feels the pain when the planning is bad. Once meal-planning works, follow-up tracking and trip prep follow naturally because the patterns are the same.

---

## Layer 6: Privacy & Multi-Caregiver Coordination

The family variant runs on more sensitive data than the work variant. Three rules for the agent and three rules for the household.

### Agent rules (encoded in `CLAUDE.variant.family.md`)

1. **Never surface one family member's private information unprompted.** If Sarah asks about meal planning, don't bring up Jake's medical history unless directly relevant (e.g., his gluten restriction shapes recipe choices). Privacy by minimal surfacing.

2. **Flag stale information.** Medical >6 months → `> [!warning] Last updated 2025-09-12`. Financial >1 year → `> [!warning] Verify current status`. Medications >3 months → `> [!warning] Confirm current dosage`. Lint runs catch these on schedule (see [`skills/shared/wiki-lint/SKILL.md`](../../skills/shared/wiki-lint/SKILL.md)).

3. **Don't push family content to external tools.** Research operations (Perplexity, Semantic Scholar) accept abstract queries — "evidence on iron supplementation in adolescents" — not specifics about Jake. If a query needs context the agent already has, summarize the abstract version, not the personal version.

### Household rules (operational hygiene)

1. **Designate a primary maintainer.** One adult is accountable for the wiki's hygiene — running lint, reviewing the changelog weekly, checking for stale records. Both adults can write to the wiki; one watches the wiki itself.

2. **Multi-caregiver editing windows.** When both adults are likely to be writing (e.g., back-to-school season, both ingesting school docs), agree informally on who handles what domain. Don't both ingest the same school newsletter twice.

3. **Onboard kids deliberately.** Below age 8: parents query on the kid's behalf. Age 8-12: read-only access on a shared device for reference (recipes, family calendar). 13+: their own login if they want to participate; help them keep their own personal vault separate if they want privacy. Avoid the trap of treating older kids' data as parental property.

### When a family member doesn't want to be in the wiki

This will come up. A teenager who doesn't want their medical visits captured anywhere. An aging parent who's uncomfortable with detailed financial records being readable to adult children. Honor the request. The vault is the household's shared knowledge; if a member opts out, the wiki has minimal info on them and stops there. Don't create a parallel private tracking system in defiance of the request.

---

## Layer 7: Failure Modes

Why family wikis fail. Worth naming, since most of them are predictable.

### The one-parent-maintains-it trap

One adult sets up the wiki, ingests a few weeks of records, and waits for the household to participate. Nobody else does. The maintainer either burns out or adopts a "filing cabinet for me" mindset and the wiki becomes a single-user system that doesn't survive the maintainer's busy season.

**Counter:** Pick an operation that produces something the *other* household members consume — meal plans they shop from, weekly digests they read, follow-up reminders they act on. Visible value to non-maintainers is what gets them to participate in the capture loop ("oh, I should add Mia's allergy to dietary-notes so the planner accounts for it").

### The capture-friction trap

A parent has a recipe to add. The path is: open Claude → describe the URL → wait for the ingest → review the extraction → confirm. The parent has 90 seconds, gives up, the recipe stays in the browser tab forever.

**Counter:** Make the path shorter. A bookmark or shell alias for "ingest this clipboard URL as a recipe." A drop-folder synced to the vault that auto-runs ingest on new files. The kit ships the orchestrator, but the *capture surface* is up to each household to optimize for their own muscle memory.

### The data-staleness trap

Medical records get filed in March and never reviewed. By December the medication list is wrong, the providers list has a moved phone number, the insurance plan changed at open enrollment and nobody updated `insurance.md`.

**Counter:** Lint runs on a schedule (the kit's `wiki-lint` skill flags stale records). The maintainer reviews the lint output weekly. Outdated callouts surface during operations (the meal planner sees `> [!warning] dietary-notes last updated 11 months ago` and suggests a refresh).

### The scope-creep trap

The wiki was set up for "family." Then a parent starts ingesting work artifacts because it's convenient. Then the kids start ingesting school project research. Then the wiki has a confused identity and the family pages drown in noise.

**Counter:** `purpose.md` is the gate. Every ingest reads it first. If a source falls outside the stated scope, the agent skips and logs the skip. Work content goes to a work vault. Each kid's school deep-research goes to their own personal vault.

### The operations-never-started trap

The capture loop runs for three months. No operations get authored. The wiki is rich with records but nothing draws on them. The family gets no operational benefit. The capture loop goes cold.

**Counter:** Ship one operation in week 4-5 of the wiki's life, before capture habit dies. Meal planning is the canonical first operation because every household feels the pain of bad meal planning weekly. Once that one works, the second is easier because the pattern is clear.

---

## Implementation Roadmap

The family variant is much lighter to roll out than the work variant. Three phases instead of four.

### Phase 1: Vault setup (one weekend)

1. Pick a cloud drive provider, create the synced folder, copy the `vault-templates/family/` template into it.
2. Install Obsidian on each adult's machine; open the vault.
3. Customize `_variant/CLAUDE.variant.md` with family member names; customize `purpose.md` with the household's scope.
4. Walk through the [`setup guide`](../guides/setup.md) to install obsidian-skills, kit skills, and Python deps.
5. Create person pages for each family member from `_templates/person.md`. Fill in basics — relationship, DOB, primary doctor, school for kids.

### Phase 2: First ingests (week 1-3)

6. Pick one or two domains to start. Recipe library is recommended (high frequency, low sensitivity, immediate value).
7. Ingest 10-20 recipes the family already cooks regularly. Validate the recipe template fits.
8. Ingest current medications from the most recent prescription bottles into `medications.md`.
9. Ingest the most recent annual physical for each adult and well-child visit for each kid into per-person medical pages.
10. Don't try to backfill 20 years. Start where you are.

### Phase 3: First operation (week 4-5)

11. Run `meal-planning` for an upcoming week. Iterate the algorithm with the family until the plans are useful (less repetition, better fit to weeknight constraints, etc.).
12. Once meal-planning produces useful weekly output, schedule it (Sunday morning operation, output reviewed by whoever shops).
13. Add the next operation that fits the family's pain points — typically follow-up tracking (if there's a chronic condition) or trip prep (if the family travels often).

### Phase 4: Operational maturity (ongoing)

14. Run `wiki-lint` weekly. Address the flagged stale items.
15. Add new content-type ingesters as the household hits new recurring source types (sports schedules, school portals, etc.).
16. Annual rituals: year-end review, capacity planning for the next year (school calendars, travel anchor dates).

---

## Cost Estimate

Per month, single-household.

| Component | Cost | Notes |
|---|---|---|
| Obsidian | Free | Sync is $5/user/mo if used; otherwise $0. |
| Cloud drive | Free–$10 | Most households already pay. |
| Claude Pro/Max | $20–100 | One subscription, shared. Pro is fine for most households. |
| Perplexity Pro | $0–20 | Optional; free tier handles most family lookups. |
| Semantic Scholar | Free | No cost. |
| Defuddle | Free | Local CLI, npm-installable. |
| pure.md | Free–$19 | Anonymous tier handles most ingest volume. |
| Docling | Free | Local Python; only cost is disk space for models. |
| **Total** | **~$20–40/mo** | Most of which the household was already paying. |

The total is small because the family variant doesn't need PM tools, Gemini Deep Research, or Git hosting. The big-ticket subscription is Claude Pro, which most households adopting the LLM Wiki pattern already have.

---

## Key Design Decisions & Rationale

**Why people-first ontology instead of domain-first?**
Most family questions start from a person. Optimizing the navigation path for the most common access pattern matters more than topical purity. People are also stable identifiers — a person doesn't get renamed; a domain folder structure does. Routing through people gives the wiki a natural home for cross-domain context (Jake's pages span health, education, and food preferences).

**Why structured ingestion as a pattern, not just "let Claude figure it out"?**
A meal-planning skill that has to re-extract ingredients from each recipe page on every run is fragile and expensive. Structured pages let operations treat the wiki as a queryable database, not a pile of prose. The recipe template, the medical-record schema, and the trip frontmatter are the *contract* between ingestion and operations — change either side without coordinating with the other and the operations break.

**Why two-axis ingest (source-type × content-type) instead of one giant ingester?**
Source-type ingesters (`ingest-website`, `ingest-document`) are reusable across both variants and across content types — a recipe URL and an article URL share the same fetch/clean step. Content-type ingesters (`ingest-recipe`, `ingest-medical-record`) encode family-specific schemas. Keeping them separate means new content types compose existing source-type ingesters without duplicating cleanup logic, and new sources (a future `ingest-podcast`) can feed into existing content types.

**Why active-OS framing instead of pure-KMS?**
Family wikis without operations die. The capture loop requires visible payoff to stay alive, and operations are how the wiki delivers visible weekly payoff to people other than the maintainer. The KMS pattern from the work variant — read the wiki to ground decisions — works for engineers because their work is itself read-write-on-the-wiki. Most family work isn't on the wiki; it's in the kitchen, at appointments, on the road. Operations bridge from wiki state to action.

**Why no formal ADRs?**
Family decisions don't have the same lifecycle as architectural decisions in software. They're rarely formally decided ("we hereby resolve to switch sandwich bread brands") and often get revisited casually. Forcing an ADR-like structure on family decisions adds bureaucracy without payoff. The exception: decisions with significant financial or legal weight (refinance, schools, medical) — those get a `wiki/finances/decisions/` or similar treatment, but with much more flexibility than the work variant's immutable ADRs.

**Why outdated-information callouts instead of automatic deletion?**
Stale family information is occasionally still right (the recipe still works) and occasionally dangerously wrong (the ER allergy info is from 2019 but Jake developed peanut sensitivity in 2024). The kit can't tell which. Surfacing staleness as a `> [!warning]` lets the human review and decide. Automatic deletion would either lose currently-correct information or fail to warn about silently-wrong information.

**Why explicit privacy gates around the research tools?**
Medical, financial, and kid-related context shouldn't leak to third-party services. Research operations are scoped to abstract queries (the "what does the literature say about X" shape) rather than personal queries (the "what should we do about Jake's X" shape). Personal context stays in the vault; abstract context goes out. This is enforced by skill design — the research skills' prompts demand decontextualized queries — rather than infrastructure, but it's worth being explicit about as a household norm.

**Why one vault per household instead of one per parent?**
Shared visibility is the whole point. A vault per parent reintroduces the coordination problem the wiki is meant to solve. The cases where a separate vault is warranted — a teenager who wants a private journal, a parent maintaining their own elderly parent's records — are exceptions handled by spinning up a *separate* vault for that purpose, not by partitioning the family vault.
