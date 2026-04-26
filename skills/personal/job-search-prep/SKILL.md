---
name: job-search-prep
description: "Given target role + company, assemble target-tailored resume, cover letter / pitch, selected portfolio pieces, and a scaffolded application page. The kit's most-used personal-OS operation during active job search. Use when a new role or referral surfaces, or on request: \"prep an application for {Company} {Role}\". For ongoing narrative maintenance (not application-specific) use career-narrative-refresh."
license: MIT
metadata:
  variant: personal
---

# Job Search Prep Skill (Personal Variant)

Given a target role + company, assemble target-tailored resume + cover letter / pitch + selected portfolio pieces + a scaffolded application page. The kit's most-used personal-OS operation during active job search.

## When to Use

- A new role appears that you want to apply to
- A referral opportunity opens at a company you've been watching
- On request: "Prep an application for {Company} {Role}"

This is a crisis-responding operation in the report's framing — when the right opportunity surfaces, having tailored materials within an hour beats "I'll get to it next weekend."

## Inputs

User provides:
- Target company name
- Role title
- Job posting URL or pasted job description (will route through [[ingest-application]] if not yet ingested)
- Optional: target compensation range
- Optional: deadline

Reads:
- The current career narrative — `wiki/career/narrative/` most recent version
- Portfolio pieces — `wiki/portfolio/*.md` with `status: active`
- Recent projects — `wiki/projects/*/overview.md`
- Network connections at the company — `wiki/network/relationships/*.md` filtered for company match
- Existing resume drafts — `wiki/career/resume/`
- Skills tracking — `wiki/career/skills/*.md`

## Algorithm

1. **Ingest the application** if not already done. Route through [[ingest-application]] which extracts company / role / location / comp / requirements / deadline / source from the URL or posting.
2. **Read the role's requirements.** What signals do they want? Years of experience, specific stacks, scope of impact, location flexibility.
3. **Match narrative angles.** From the career narrative's `## Tailoring Hints`, pick the angle most relevant to the role's signals.
4. **Compose tailored resume.** Take the most recent resume version; emphasize projects matching the role's requirements; reorder bullets for relevance; trim irrelevant content. Save as new versioned resume.
5. **Select 3-5 portfolio pieces.** Choose the strongest evidence pieces matching the role. Prefer public-facing work (links, not behind-NDA descriptions).
6. **Surface network leverage.** Anyone at the company in `wiki/network/relationships/`? If yes, propose: "Reach out to {person} for a referral or context before applying?"
7. **Compose application page** using `_templates/application.md`. Cross-link the tailored resume, the selected portfolio pieces, and the network connections.
8. **Surface gaps.** What does the role require that current materials don't address? Flag for the user — they may need to produce something (a writing sample, a code project) before applying.

## Output

A bundle of files written / updated:

1. `wiki/career/applications/{company-slug}-{role-slug}.md` — the application page (using `_templates/application.md`):
   ```yaml
   ---
   title: "{Company} — {Role}"
   type: application
   status: active
   created: {today}
   modified: {today}
   tags: [application, job-search, {company-slug}]
   company: "{Company}"
   role: "{Role}"
   ...
   ---
   ```
2. `wiki/career/resume/{target-slug}-{YYYY-MM-DD}.md` — tailored resume version
3. *(Optional)* `wiki/career/applications/{company-slug}-{role-slug}-pitch.md` — cover letter / pitch draft if the role wants one

The application page links to all the artifacts produced so they can be retrieved together later.

## Side-effects

1. **Update `wiki/career/applications/index.md`** with the new application listed and active.
2. **Update or note network-relationship pages** if outreach is suggested ("Reached out to {person} on {date} re: {company} referral").
3. **Append to `log/changelog.md`**: "Application prepped: [[career/applications/{...}]]."

## Interactive Review

```
Application prep for: {Company} — {Role}

Job posting summary:
  Location: {city / remote}
  Comp range: {$X-$Y}
  Key requirements: {3-5 from posting}
  Deadline: {date}

Network leverage:
  ✓ {Person} works at {company} (last contact: {date})
    → Recommend: reach out before applying for context + potential referral
  ✓ {Person} formerly at {company} (left {year})
    → Recommend: ask for cultural / interview-process context

Tailored materials proposed:
  Resume: career/resume/{target}-2026-04-25.md
    Emphasizing: distributed systems, observability, technical writing
    De-emphasizing: management experience (this is an IC role)
  Portfolio pieces (3 selected):
    - [[portfolio/kafka-observability-talk]] (most relevant — talks about exactly the systems they build)
    - [[portfolio/personal-site-event-loops]] (writing sample showing technical depth)
    - [[portfolio/{...}]]

Gaps surfaced:
  - Posting wants Go experience; portfolio is mostly Java + Python
    → Consider: write a small Go project, or address in cover letter

Save application bundle? Reach out to {Person} first?
```

## Failure Modes

- **No career narrative exists.** Block: "career narrative is missing — author one (`wiki/career/narrative/`) or run [[career-narrative-refresh]] before prepping applications. The narrative is what makes tailoring possible."
- **No portfolio pieces match the role.** Surface explicitly. Ask whether to apply anyway with a stronger cover letter, or hold the application until evidence is built.
- **Multiple resume versions and no obvious base.** Ask the user which to start from; default to the most-recently-modified.
- **Job posting URL is paywalled or expired.** Ask the user to paste the description directly.

## Cadence

- **Per application:** Run for each role you decide to apply to.
- **No scheduled runs:** Job search is bursty by nature.
