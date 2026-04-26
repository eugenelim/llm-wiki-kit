---
name: medical-summary
description: "Generate a current-state medical summary for a family member (active conditions, medications, allergies, recent visits, outstanding follow-ups) suitable for a doctor visit, school form, or emergency reference. Use before a doctor visit (especially a new specialist), for annual physical prep, when a school/camp requires a form, or on request: \"generate a medical summary for {person}\"."
license: MIT
metadata:
  variant: family
---

# Medical Summary Skill (Family Variant)

Synthesizing operation. For a person, produce a current-state medical summary suitable for sharing with a provider, attaching to a school form, or referencing during an emergency. Aggregates active conditions, current medications, allergies, recent visits, and outstanding follow-ups.

## When to Use

- Before a doctor visit (especially with a new specialist)
- Annual physical preparation
- When a school / camp requires a medical form
- When an emergency happens and you need a quick reference
- On request: "Generate a medical summary for {person}"

## Inputs

User provides:
- Person name (or wikilink to their page)
- Optional: visit context ("for the dentist," "annual physical," "ER intake")

Reads:
- `wiki/people/{name}.md` — basics: DOB, blood type, primary care
- `wiki/health/{name}-medical.md` — chronological visit history
- `wiki/health/medications.md` — filtered to this person
- `wiki/health/providers.md` — full provider list
- `wiki/health/insurance.md` — coverage details
- Recent medical-record ingests via `raw/` — last 12-24 months

## Algorithm

1. **Compile core medical identity.** Name, DOB, blood type if known, allergies, chronic conditions.
2. **Active medications.** Current prescriptions with dose, frequency, prescriber.
3. **Recent visits** — last 6-12 months, dated and concise.
4. **Outstanding follow-ups** — what's due, by when, with which provider.
5. **Insurance details** — plan name, member ID, key contact numbers (if context warrants).
6. **Format for context.** A summary for a dentist visit emphasizes oral health + bleeding risks + medications affecting dental procedures. A summary for an ER intake emphasizes allergies + meds + chronic conditions + emergency contacts. Tailor.

## Output

Write `wiki/health/{name}-summary-{YYYY-MM-DD}.md` (versioned):

```yaml
---
title: "{Name} Medical Summary"
type: medical-summary
person: {name}
context: "{visit-context}"
created: {today}
modified: {today}
tags: [medical, summary, {name}]
status: current
provenance: synthesized
---
```

Body sections:
- `## Synopsis` — 1-2 sentences (for the provider's quick-read at the top)
- `## Identity` — name, DOB, blood type
- `## Active Conditions` — chronic diagnoses with date of diagnosis
- `## Current Medications` — drug, dose, frequency, prescribing provider
- `## Allergies` — substance + reaction severity (especially for emergency context)
- `## Recent Visits` — last 6-12 months, dated, with provider + reason + outcome
- `## Outstanding Follow-ups` — what's due, by when, with whom
- `## Emergency Contacts` — primary care, specialists, insurance member services
- `## Notes for This Visit` — context-specific items

Generate as a printable / shareable document. The companion deliverable in `outputs/` (a PDF version) can be created via Claude's PDF generation if needed.

## Side-effects

1. **Update `wiki/health/{name}-summary-index.md`** with the new versioned summary.
2. **Mark previous summary as outdated** if applicable.
3. **Append to `log/changelog.md`**: "Medical summary generated: [[health/{name}-summary-{date}]]."

## Interactive Review

```
Medical summary for Jake (8 yrs, 2018-04-12) — context: annual physical:

Identity:
  - DOB: 2018-04-12 (8 yrs)
  - Blood type: O+
  - Primary care: Dr. Chen, Riverdale Pediatrics

Active conditions:
  - Mild seasonal allergies (diagnosed 2024-09)
  - History of febrile seizure (2020; no recurrence)

Current medications:
  - Albuterol HFA — as needed for exercise-induced wheeze (Dr. Chen)
  - Children's Claritin — daily during pollen season Apr-Oct

Allergies:
  - Penicillin (rash; documented 2022-03)
  - Wheat / gluten (mild GI; diagnosed 2024-12)

Recent visits (last 12 months):
  - 2026-04-15: ear infection follow-up — clear (Dr. Chen)
  - 2026-02-10: well-child exam — all metrics on track
  - 2025-11-22: allergy panel — confirmed gluten sensitivity
  - 2025-09-08: seasonal allergy mgmt review

Outstanding:
  - Annual flu shot due September 2026
  - Allergy follow-up — 6 months out (so 2026-05-22)

Save summary? Generate as PDF for the visit?
```

## Failure Modes

- **Person page missing.** Surface: "no person page for {name}; create one first."
- **Medical history sparse.** Generate what's available; flag: "summary is based on limited history; recent visits not fully captured."
- **Conflicting medication entries.** Surface: "medications.md and recent visit notes disagree about {drug}; verify before sharing."
- **Date of birth missing.** Block: "DOB is required for medical summaries; add to person page first."

## Cadence

- **On demand:** Before each medical visit or when needed.
- **Annually:** Refresh as part of the annual physical cycle.
- **No scheduled runs:** Medical summaries are visit-driven.
