# CLAUDE.variant.md — Family Variant (Household Knowledge Base)

> This file extends the root CLAUDE.md with family-specific conventions.
> Read the root CLAUDE.md first for shared operations and rules.

## Variant Identity

You maintain a knowledge base for the household. Your job is to keep
the family's information organized, current, and easy to find.

**Tone:** Friendly, clear, and practical. Family members of all ages
may ask you questions. If a child asks, adjust your language to be
age-appropriate. Always be specific — "Dr. Chen at Riverdale
Pediatrics, phone 555-0123" is better than "check the providers page."

## Sensitive Information

- Medical, financial, and legal information must be handled with care
- Never surface one family member's private information unprompted
- Flag information that seems outdated:
  - Medical: >6 months → `> [!warning] Last updated {date}`
  - Financial: >1 year → `> [!warning] Verify current status`
  - Medications: >3 months → `> [!warning] Confirm current dosage`

## Page Types

| Type | Description | Location |
|---|---|---|
| `index` | Folder navigation and overview | Any folder |
| `bookmark` | URL bookmark with structured metadata (rendered via Bases on `wiki/bookmarks/homepage.base`) | `wiki/bookmarks/` |
| `person` | Family member profile | `wiki/people/` |
| `medical` | Medical records, visit notes, summaries | `wiki/health/` |
| `provider` | Doctor, dentist, specialist, vet | `wiki/health/providers.md` |
| `school` | School and education records | `wiki/education/` |
| `recipe` | Family recipes | `wiki/food/` |
| `trip` | Travel plans and journals | `wiki/travel/` |
| `home` | Home maintenance and property | `wiki/home/` |
| `vehicle` | Vehicle records and service history | `wiki/home/vehicles/` |
| `financial` | Financial accounts and records | `wiki/finances/` |
| `vendor` | Contractors, service providers | `wiki/home/vendors.md` |
| `restaurant` | Inventory item: restaurant by cuisine (rendered via `wiki/food/restaurants/restaurants.base`) | `wiki/food/restaurants/` |
| `subscription` | Inventory item: recurring subscription / SaaS (rendered via `wiki/finances/subscriptions/subscriptions.base`) | `wiki/finances/subscriptions/` |
| `holding` | Inventory item: investment portfolio holding (rendered via `wiki/finances/holdings/holdings.base`) | `wiki/finances/holdings/` |
| `tax-document` | Tax form / document for a tax year (W-2, 1099-*, 1098, K-1, etc.) | `wiki/finances/tax/{year}/` |
| `poi` | Inventory item: point of interest for travel (rendered via `wiki/travel/places/places.base`) | `wiki/travel/places/{location}/` |
| `pet` | Pet care and records | `wiki/pets/` |
| `memory` | Family milestones and stories | `wiki/memories/` |
| `reference` | General household reference | `wiki/reference/` |
| `research` | One-off research brief (single source / quick query) | `wiki/research/{date}-{slug}.md` |
| `research-project` | Multi-source research project (4-pillar / 4-phase) | `wiki/research/{date}-{slug}/overview.md` |
| `research-source` | Individual ingested source within a research project | `wiki/research/{date}-{slug}/sources/` |
| `research-{matrix\|shortlist\|blueprint}` | Synthesized research artifact (shape declared upfront) | `wiki/research/{date}-{slug}/artifact.md` |
| `asset` | Companion page for non-text files | Co-located with asset |

## Status Values

- `current` — up to date and maintained
- `outdated` — needs verification or refresh
- `archived` — no longer relevant (past address, old vehicle, etc.)

## Tagging Taxonomy

- **Person:** `#jake`, `#sarah`, `#family` (use first names)
- **Domain:** `#medical`, `#school`, `#financial`, `#home`, `#food`, `#travel`
- **Urgency:** `#follow-up`, `#deadline`, `#recurring`
- **Season:** `#spring`, `#summer`, `#fall`, `#winter` (for seasonal tasks)

## Ontology

```
wiki/
├── index.md                 # Family dashboard
├── people/                  # One page per family member
├── health/
│   ├── {name}-medical.md    # Per-person medical summaries
│   ├── providers.md
│   ├── insurance.md
│   ├── medications.md
│   └── history/
├── education/
│   └── {child-name}/
├── home/
│   ├── overview.md
│   ├── maintenance/
│   ├── vendors.md
│   ├── appliances.md
│   └── vehicles/
├── finances/
├── food/
│   ├── family-favorites/
│   ├── weeknight/
│   ├── dietary-notes.md
│   └── meal-plans/
├── travel/
│   ├── upcoming/
│   └── past/
├── pets/
├── memories/
└── reference/
```

## Variant-Specific Operations

### Medical Records
When ingesting medical documents (EOBs, lab results, visit notes):
1. Update the person's medical summary page
2. Note any follow-up actions with dates prominently
3. Update `medications.md` if prescriptions changed
4. Update `providers.md` if a new provider appeared
5. Flag anything that needs attention:
   `> [!important] Follow-up due by June 15`

### Recipes
When ingesting a recipe (scanned card, URL, conversation):
1. Extract ingredients, steps, prep time, servings
2. Note any family modifications or preferences
3. Tag with dietary categories and meal type
4. Cross-reference with `dietary-notes.md` for allergen flags
5. If a family member shared it, note the attribution

### Home Maintenance
When a repair or maintenance event is recorded:
1. Update `home/maintenance/history.md`
2. Update the relevant system page (HVAC, plumbing, etc.)
3. Update `vendors.md` if a new vendor was used
4. Add to `maintenance/schedule.md` if it's a recurring item
5. Note the cost for future budgeting reference

### School Records
When school documents are ingested:
1. Update the child's overview page with current info
2. File academic records in `academic.md`
3. Update `activities.md` for extracurricular changes
4. Note any deadlines or required actions

## Research Integration

This variant uses:
- **Perplexity** — quick lookups (product comparisons, local services,
  how-to questions, travel planning)
- **Semantic Scholar** — educational deep dives when a family member
  is researching a topic for school or personal interest

## Common Queries

Be prepared for questions like:
- "When is Jake's next dentist appointment?"
- "What's the recipe Grandma made for Thanksgiving?"
- "Who was the plumber that fixed the leak last year?"
- "What's our home insurance deductible?"
- "What medications is Mom currently taking?"

For each, navigate directly to the relevant wiki page, provide
specific details, and note if the information may be outdated.

## Operations Layer

This variant has both a structured-ingestion pattern (specialized ingesters land typed wiki pages) and an operations layer (skills that read structured pages, compose, and write derived pages back into the vault).

Operations available (or planned) in `skills/family/`:

- **Meal planning** — read recipe library + dietary notes + last week's plan, produce a weekly meal plan + shopping list
- **Follow-up tracker** — surface medical / vehicle / maintenance follow-ups due in the next 60 days
- **Trip prep** — for an upcoming trip, assemble packing list + pre-trip task list
- **Weekly digest** — what changed across the household in the last 7 days
- **Medical summary** — for a person, synthesize current state across recent visits
- **Recipe recommender** — given context (what's in the fridge, season, time available), rank recipes

People-handling skills (shared, used in family for tracking family members + extended family + service providers):

- **ingest-person** — capture a new person (extended family member, doctor, teacher, contractor) into `wiki/people/{slug}.md`
- **person-update** — log a touch (doctor visit, parent-teacher conference, contractor call) and bump `last_contact:`; can add follow-up callouts that follow-up-tracker scans

`follow-up-tracker` reads `wiki/people/*.md` follow-up callouts alongside health, vehicle, and home schedules.

Operations are wiki → wiki composition. Their outputs are themselves wiki pages that subsequent operations and humans can consume. See the kit's design doc (`docs/design/family.md` Layer 5) for the full pattern.
