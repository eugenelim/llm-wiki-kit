---
name: ingest-medical-record
description: "Capture a medical document (visit summary, EOB, lab result, prescription note) and append it to the per-person medical summary, updating medications and providers. Use when a medical PDF/photo is dropped, a medical record is pasted, or the user says \"ingest this medical record\" / \"save this visit\". Composes ingest-document for cleanup."
license: MIT
metadata:
  variant: family
---

# Ingest Medical Record Skill (Family Variant)

Specialized content-type ingester for medical records — visit summaries, EOBs, lab results, prescription notes. Composes a source-type ingester for cleanup, then applies medical-record schema. Output: appended to the per-person medical summary; medications and providers updated as side-effects.

## When to Use

The orchestrator routes here when:
- A medical document (EOB, visit summary, lab result, prescription) is dropped or pasted
- The user says "ingest this medical record" / "save this visit"
- A PDF in `raw/` matches a medical-document pattern (insurance / hospital / clinic letterhead)

## Composition (two-axis routing)

| Source | Source-type cleanup | Result |
|---|---|---|
| EOB / visit summary / lab result PDF | [[ingest-document]] (Docling) | clean markdown |
| Patient-portal screenshot or PDF | [[ingest-document]] | clean markdown |
| Pasted summary (from email or visit notes) | none — handle directly | raw text |

## Inputs

After source-type cleanup:
- The cleaned-up medical content
- The person whose record this is (asked of the user if ambiguous)
- `wiki/health/{person}-medical.md` — for chronological appending
- `wiki/health/medications.md` — for prescription updates
- `wiki/health/providers.md` — for provider updates

## Algorithm

1. **Identify the person.** Most documents name the patient; cross-check with `wiki/people/`. If ambiguous, ask.
2. **Extract date of service** + **provider** + **reason for visit**.
3. **Extract diagnoses** (ICD-10 codes if present, plain-text descriptions otherwise).
4. **Extract procedures** (CPT codes + descriptions).
5. **Extract prescriptions** — drug, dose, frequency, prescribing provider, dates.
6. **Extract follow-up instructions** — "recheck in 6 months," "schedule allergy panel," "call if X symptoms."
7. **Extract cost breakdown** (insured / patient responsibility) if EOB.
8. **Detect new providers** not in `providers.md`; surface for addition.
9. **Detect prescription changes** — new prescriptions, dose changes, discontinuations; surface medication-page updates.

## Output

**Update `wiki/health/{person}-medical.md`** — append a dated entry at the top (reverse chronological):

```markdown
## 2026-04-15 — {Reason for visit}

**Provider:** Dr. Chen, Riverdale Pediatrics
**Source:** [[raw/2026-04-15-jake-visit-summary.md]]

### Findings
- {Diagnosis or finding}

### Prescriptions
- {drug, dose, frequency} — see [[health/medications]]

### Follow-ups
> [!important] Follow-up due by 2026-10-15
> Allergy panel recheck (Dr. Chen).

### Cost
- Insured: ${X}
- Patient responsibility: ${Y}
```

**Update `wiki/health/medications.md`** if prescriptions changed:
- New medication added with start date and prescriber
- Dose change noted with date and reason
- Discontinuation marked with date and reason

**Update `wiki/health/providers.md`** if a new provider appeared.

**Save the raw document** to `raw/{YYYY-MM-DD}-{person}-{slug}.md` (the source-of-truth original).

**Create a companion page** in `wiki/health/_assets/` if the original was a PDF or image (per the kit's asset management pattern).

## Side-effects

1. **Surface follow-ups for the [[follow-up-tracker]].** The `> [!important]` callout is what follow-up-tracker scans for.
2. **Trigger [[medical-summary]] readiness check** — if the person's last medical-summary is >6 months old, surface that a refresh is due.
3. **Append to `log/changelog.md`**: "Medical record ingested for {person}: [[health/{person}-medical#{date}]]."

## Interactive Review

```
Medical record ingested: Jake's allergy panel recheck (2026-04-15)
Provider: Dr. Chen, Riverdale Pediatrics

Findings:
  - Negative for new allergens
  - Existing gluten sensitivity confirmed
  - Continue current management

Prescriptions:
  - No changes (continue Children's Claritin daily during pollen season)

Follow-ups:
  - Recheck in 6 months → 2026-10-15

Append to Jake's medical page? Update medications.md? (no changes needed
this visit) Surface to follow-up tracker (yes)?
```

## Failure Modes

- **Person ambiguous.** Multiple family members could be the patient. Ask explicitly.
- **OCR garbled** (handwritten notes, low-quality scan). Surface what was extracted; ask the user to confirm the key facts (date, provider, diagnoses, prescriptions) before saving.
- **Conflicting prescription data.** New record contradicts what's currently in `medications.md`. Surface with `> [!danger] Contradiction` callout — don't silently update.
- **No clear date of service.** Some EOBs span multiple visits. Ask the user to confirm the date.

## Cadence

- **On demand:** Run when a medical record arrives.
- **No scheduling:** Reactive.
- **Pairs with [[follow-up-tracker]] and [[medical-summary]].**
