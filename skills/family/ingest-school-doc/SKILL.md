---
name: ingest-school-doc
description: "Capture a school document (report card, calendar, permission slip, newsletter, conference note) into the relevant child's education folder. Use when a school PDF/photo is uploaded, a school newsletter URL is pasted, a teacher email is forwarded, or the user says \"save this school doc / report card / permission slip\"."
license: MIT
metadata:
  variant: family
---

# Ingest School Document Skill (Family Variant)

Specialized content-type ingester for school documents — report cards, calendars, permission slips, newsletters, conference notes. Composes a source-type ingester for cleanup, then applies school-doc schema. Output lands in the relevant child's education folder.

## When to Use

The orchestrator routes here when:
- A school document is uploaded (PDF, photo, scan)
- A school newsletter URL is pasted
- A teacher email is forwarded
- The user says "save this school doc / report card / permission slip"

## Composition (two-axis routing)

| Source | Source-type cleanup | Result |
|---|---|---|
| Report card / school document PDF | [[ingest-document]] (Docling) | clean markdown |
| Photo / scan | [[ingest-document]] (Docling with OCR) | OCR'd text |
| Newsletter URL or school portal link | [[ingest-website]] | clean markdown |
| Pasted teacher email | none — handle directly | raw text |

## Inputs

After source-type cleanup:
- The cleaned-up content
- The child whose document this is (asked if ambiguous)
- `wiki/education/{child}/` — child's education folder
- `wiki/education/{child}/overview.md` — current school, grade, teachers
- `wiki/education/{child}/activities.md` — extracurricular tracking

## Algorithm

1. **Identify the child.** Match name on document. If unclear, ask.
2. **Identify document type.**
   - Academic — report card, progress report, assessment results
   - Activity — extracurricular schedule, sports calendar, recital announcement
   - Administrative — permission slip, form to sign, fee notice
   - Communication — newsletter, teacher email, principal announcement
3. **Extract per-type details.**
   - Academic: grades, teacher comments, specific scores or benchmarks
   - Activity: dates, location, equipment / fee requirements
   - Administrative: action required, deadline, who needs to sign
   - Communication: key information, action items if any
4. **Extract dates.** Anything with a future date becomes a candidate for the family calendar.
5. **Detect changes** from prior school docs — new teacher? schedule shift?

## Output

Append or create the appropriate page in `wiki/education/{child}/`:

**For report cards:**
Append to `wiki/education/{child}/academic.md`:
```markdown
## {Term} {YYYY-YYYY} — Report Card

**Source:** [[raw/{YYYY-MM-DD}-{child}-report-card.md]]
**School:** {School name} (current grade)
**Teacher(s):** {names}

### Grades
{Subject-by-subject grades or progress markers}

### Teacher Comments
{Verbatim or paraphrased}

### Action items
- {Things to follow up — meet with teacher, address subject area, etc.}
```

**For activities:**
Append to `wiki/education/{child}/activities.md` with dates, contacts, equipment needs.

**For administrative:**
Surface action items prominently. If something needs signing by a deadline:
```markdown
> [!important] Sign and return permission slip by 2026-04-30
> {What it's for, link to source}
```

**For newsletters:** brief summary in `wiki/education/{child}/correspondence.md`.

**Always:** save raw to `raw/{YYYY-MM-DD}-{child}-{slug}.md`. Companion page if PDF/photo.

## Side-effects

1. **Surface dates** for the family calendar (sports, performances, parent-teacher conferences, breaks).
2. **Update `wiki/education/{child}/overview.md`** if there are structural changes (teacher, schedule, school).
3. **Trigger [[follow-up-tracker]] visibility** for action-item callouts.
4. **Append to `log/changelog.md`**: "School doc ingested: [[education/{child}/{...}]]."

## Interactive Review

```
School doc ingested: Mia's report card, Spring 2026 term

Document type: Academic — report card
School: Riverdale Elementary, 6th grade
Teachers: Ms. Patel (homeroom), Mr. Lee (math), Ms. Singh (science)

Grades:
  Math: A    Science: A    English: B+    Social Studies: A    Art: A+
  PE: Pass    Music: A

Teacher comments:
  Patel: "Mia is a thoughtful student who participates well..."
  Lee: "Strong analytical skills; encouraged to attempt advanced problems"

Action items detected:
  - None requiring immediate action
  - Note: math teacher recommended summer math camp consideration

Append to Mia's academic page? Note the camp consideration in goals?
```

## Failure Modes

- **Child ambiguous** (multi-child documents like a school-wide newsletter). Save once at school-wide level if applicable.
- **Document is a PDF screenshot of a portal** with formatting that breaks OCR. Surface the extracted text; verify before saving.
- **Date stamp missing.** Use document's term context or ask the user.
- **Permission slip without clear action.** Surface for user — what's being permitted? What's the deadline? Don't silently file.

## Cadence

- **On demand:** Run when school documents arrive.
- **Bursty pattern:** Heavy at start of school year, quarter ends, end of school year.
- **No scheduling:** Reactive.
