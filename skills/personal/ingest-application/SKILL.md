---
name: ingest-application
description: "Capture a job posting or application into a structured wiki/career/applications/{company}-{role}.md page with stage tracking and tailored-material slots. Use when the user says \"track this application\" / \"save this job posting\" / \"ingest this opportunity\", a URL matches a job-board pattern (LinkedIn jobs, company careers, AngelList), a paste identifies as a job posting, or a recruiter email is forwarded."
license: MIT
metadata:
  variant: personal
---

# Ingest Application Skill (Personal Variant)

Specialized content-type ingester for job postings and applications. Composes a source-type ingester for cleanup, then applies application-tracking schema. Output: a structured `wiki/career/applications/{company}-{role}.md` page using the application template, with stage tracking and tailored-material slots.

## When to Use

The orchestrator (`skills/shared/ingest.md`) routes here when:

- The user says "track this application" / "save this job posting" / "ingest this opportunity"
- A URL matches a job-board pattern (LinkedIn jobs, company careers page, AngelList, etc.)
- A pasted text identifies as a job posting (role title + responsibilities + requirements structure)
- A recruiter email is forwarded for tracking

## Composition (two-axis routing)

| Source | Source-type cleanup | Result |
|---|---|---|
| Job posting URL | [[ingest-website]] (defuddle; pure.md fallback if site is JS-heavy or bot-blocked) | clean markdown of posting |
| PDF posting / role description | [[ingest-document]] (Docling) | clean markdown |
| Pasted text (job description from email or chat) | none — handle directly | raw text |
| Recruiter email | none — handle directly | raw text |

After cleanup, this skill applies the application schema regardless of source.

## Inputs

After source-type cleanup:

1. **The cleaned-up posting / description** — role title, company, responsibilities, requirements, comp range if listed
2. **`wiki/network/relationships/`** — to identify connections at the company
3. **Existing applications** in `wiki/career/applications/` — to detect duplicates (already applied, or applied in the past)
4. **Application template** at `_templates/application.md`

## Algorithm

1. **Extract company + role + posting metadata.** Company name, role title, location, comp range (if listed), key requirements (3-7), application deadline, source (where the posting was found).
2. **Slugify.** `{company-slug}-{role-slug}` for the filename.
3. **Detect duplicates.** Search `wiki/career/applications/` for the same company + role. If found, surface and ask whether to update the existing or create a new entry (e.g., re-applying after a year).
4. **Surface network leverage.** Search `wiki/network/relationships/` for current and former employees of the company. Tag for outreach if found.
5. **Surface readiness gaps.** Compare role requirements to the most recent career narrative; flag explicit mismatches that the user should address (cover letter framing or skill development).

## Output

Write `wiki/career/applications/{company-slug}-{role-slug}.md` using `_templates/application.md`:

```yaml
---
title: "{Company} — {Role}"
type: application
status: active            # active | offered | rejected | withdrawn | accepted
created: {today}
modified: {today}
tags: [application, job-search, {company-slug}]
company: "{Company}"
role: "{Role}"
location: "{location}"
source: "{URL or referral source}"
target_compensation: "{if listed or known}"
deadline: "{date if listed}"
---
```

Body sections (per the template): Synopsis, Stage tracking, Why This Role, Tailored Materials slots, Network connections at company, Notes from each stage, Decision Notes (filled at outcome).

## Side-effects

1. **Update `wiki/career/applications/index.md`** with the new application.
2. **Surface network connections** at the company. If found, propose: "Reach out to {person} for context or referral before applying?"
3. **Trigger [[job-search-prep]] readiness check.** The application page is scaffolded; tailored materials are next.
4. **Append to `log/changelog.md`**: "Application tracked: [[career/applications/{slug}]]."

## Interactive Review

```
Application ingested: Acme Corporation — Senior Platform Engineer

Posting summary:
  Location: Remote (US)
  Comp range: $180-220k base + equity
  Key requirements:
    - 7+ years distributed systems
    - Production experience with Kafka or equivalent
    - Strong written communication
    - Some leadership / mentorship experience
  Deadline: 2026-05-15 (3 weeks out)
  Source: company careers page (clean ingest via defuddle)

Network leverage detected:
  ✓ [[network/relationships/sarah]] — works there (joined 2025-08); last contact 2026-04-15
    → Recommend: reach out for context + potential referral before applying
  ✓ [[network/relationships/priya]] — formerly there (left 2024-12); last contact 2025-12-04
    → Recommend: ask for interview-process / culture context

Readiness check:
  Strong match: distributed systems + Kafka + written communication
  Weak match: leadership / mentorship experience (current narrative is heavy IC)
    → Cover letter should address: how IC depth + writing-as-mentorship counts

Track this application? Reach out to Sarah first?

Next: run [[job-search-prep]] when ready to assemble tailored resume + portfolio.
```

## Failure Modes

- **Duplicate detected (same company + role applied within 12 months).** Surface; ask whether this is a re-application (rare; usually wait period applies) or a different posting (different team / level). Don't silently overwrite.
- **Posting is paywalled / requires login (LinkedIn).** Recommend: paste the description directly rather than relying on URL ingest.
- **Comp range absent.** Don't fabricate; leave the field empty and surface as a "research before applying" item — Perplexity can lookup market benchmarks if [[research]] is enabled.
- **Role description is vague (consultant- / generalist-style postings).** Flag for the user; ask for clarification on what the actual scope is before tailoring materials.

## Cadence

- **On demand:** Run for each role you decide to track. Capture liberally; the application page is cheap to create. Withdraw or archive applications you decide not to pursue.
- **No scheduled runs:** Job search is bursty.
- **Pairs with [[job-search-prep]]:** ingest scaffolds; job-search-prep tailors materials.
