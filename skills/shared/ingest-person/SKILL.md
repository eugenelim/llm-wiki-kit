---
name: ingest-person
description: "Capture a person into the variant's people directory. Composes a source-type ingester (ingest-website for LinkedIn / company-page URLs, ingest-document for business-card photos / scanned cards / vCards, paste handling for email signatures / intro emails / conversational descriptions) with a variant-appropriate person schema. Routes to wiki/people/ (work, family) or wiki/network/relationships/ (personal). Use when the user says \"add this person\" / \"capture this contact\" / \"ingest this LinkedIn profile\" / \"save this business card\" / \"track this new colleague / vendor / doctor / mentor\". Refuses to create a duplicate if a person with the same name + role/company already exists; offers person-update instead."
license: MIT
metadata:
  variant: shared
---

# Ingest Person Skill

Specialized content-type ingester for **people**. Composes a source-type ingester for cleanup, then applies the variant's person-schema. Output: a structured `person` page at the variant-appropriate path, ready for the operations layer (request-tracker, follow-up-tracker, networking-digest, medical-summary) to read.

## When to Use

The orchestrator (`skills/shared/ingest/SKILL.md`) routes here when:

- The user says "add this person" / "capture this contact" / "save this business card" / "ingest this LinkedIn profile"
- A LinkedIn URL or `linkedin.com/in/...` is dropped
- A business-card photo or vCard (`.vcf`) file is provided
- An email signature block is pasted ("`Sarah Chen / Senior Engineer / Acme / sarah@acme.com`")
- A recruiter intro email is forwarded that introduces a person
- A meeting note mentions a new external party who isn't yet captured (orchestrator may suggest ingest-person as a follow-up)

For routine logging of an interaction with someone we already know, use [[person-update]] instead — this skill creates a new person page; person-update appends to an existing one.

## Composition (two-axis routing)

| Source | Source-type cleanup | Result |
|---|---|---|
| LinkedIn URL / company-page URL | [[ingest-website]] (defuddle; pure.md fallback) | clean markdown of the profile |
| Business-card photo / scanned card | [[ingest-document]] (Docling with OCR) | OCR'd text |
| vCard (`.vcf`) | none — parse directly | structured contact record |
| Email signature block (paste) | none — parse directly | name, role, company, email |
| Conversational description (paste) | none — handle directly | raw text |
| Meeting transcript mentioning a new person | extract from existing meeting note | name + context |

## Variant Routing

The skill reads `_variant/CLAUDE.variant.md` to pick the right path + template:

| Variant | Folder | Template |
|---|---|---|
| **work** | `wiki/people/{slug}.md` | `_templates/person.md` (work — team-collab focus) |
| **family** | `wiki/people/{slug}.md` | `_templates/person.md` (family — relationship + service-provider focus) |
| **personal** | `wiki/network/relationships/{slug}.md` | `_templates/person.md` (personal — network-cadence focus). For formal advisors specifically, use `_templates/advisor.md` and route to `wiki/network/advisors/{slug}.md`. |

The orchestrator surfaces the chosen path before writing — if the user wants a different folder (e.g., a work contact who's also a personal mentor), they can override.

## Inputs

User provides:
- Source (URL, file, or pasted text)
- Optional: explicit relationship type ("they're a vendor" / "she's my new mentor")
- Optional: variant override (rare — usually inferred)

Reads:
- `_variant/CLAUDE.variant.md` — to pick path + template
- `wiki/people/` (or variant equivalent) — for duplicate detection
- `wiki/people/index.md` — for relationship taxonomy

## Algorithm

1. **Clean the source.** Route through the right source-type ingester.
2. **Extract person fields.** Name (required), role, company/team, email, phone/Slack, LinkedIn, location, how-we-met, expertise. From whichever fields the source provides — leave the rest empty.
3. **Detect duplicate.** Search the variant's people folder for `name:` matches (or close variants — `Sarah Chen` ≈ `S. Chen` at the same company). If a match is likely:
   - Surface: "This may already exist as [[{slug}]]. Update that page (run [[person-update]]) or create a new one anyway?"
   - Default to update unless user confirms otherwise.
4. **Pick the relationship type.** From explicit user signal, the source content (LinkedIn job title vs. recruiter email vs. intro context), or interactive ask. Use the variant's relationship taxonomy (see each variant's `wiki/people/index.md`).
5. **Apply the schema.** Fill the variant's `_templates/person.md` with extracted fields. Leave `## Synopsis` and `## Notes` for human review.
6. **Set `last_contact:`.** Default to today (the capture itself counts as a touch); user can override.
7. **Cross-link.** If the source mentions a project, meeting, or event, add a wikilink in `## Recent Interactions` (work) / `## Our Conversations` (personal) / `## Notes` (family).
8. **Hand back to the orchestrator** for the standard validation, contradiction check, and changelog flow.

## Output

A `type: person` page at the variant-appropriate path. Frontmatter populated; sections seeded with extracted content; placeholders left for human review.

## Side-effects

1. Append to `log/changelog.md`: "Captured person: [[{slug}]] (relationship: {type}, variant: {variant})."
2. If the source is a meeting transcript mentioning the person, also link the new person page from the meeting's frontmatter `attendees:`.
3. (Personal only) If `cadence_target:` is provided, the next [[networking-digest]] run uses it.

## Pairs With

- **[[person-update]]** — primary follow-on. After capture, use person-update to log future interactions.
- **[[ingest-meeting]]** *(work)* — when a meeting mentions a new external party, ingest-person captures them; the meeting note links to the new page.
- **[[networking-digest]]** *(personal)* — reads `wiki/network/relationships/` after capture.
- **[[follow-up-tracker]]** *(family)* — reads `## Follow-ups` callouts on people pages.
- **[[request-tracker]]** *(work)* — reads `## Open Asks` callouts on people pages.

## Failure Modes

- **No identifiable name.** Refuse to create the page. Surface: "I can't extract a name from this source. Provide the name explicitly or paste a clearer source."
- **Likely duplicate.** Default to surfacing the existing match and offering person-update; only create a duplicate if the user confirms (different person, same name).
- **Variant ambiguous.** If running outside a vault root (rare), ask which variant to target.
- **Sensitive content.** If the source includes anything that looks like SSN, financial credentials, or private medical details, refuse to capture without redaction; suggest the appropriate ingester (ingest-tax-document, ingest-medical-record).

## Cadence

On demand — runs whenever a new person enters the picture.
