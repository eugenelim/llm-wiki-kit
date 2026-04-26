---
name: follow-up-tracker
description: "Scan health, vehicle, home maintenance, AND people pages for follow-up callouts; surface medical rechecks, vehicle service, home maintenance items, and follow-ups owed to people (doctors, teachers, contractors, friends) due in the next 60 days. Use weekly, before scheduling appointments for the next month, after a medical visit logs a new follow-up, or on requests like \"what follow-ups are due?\". Reads `wiki/people/*.md` follow-up callouts in addition to health/home/vehicle pages."
license: MIT
metadata:
  variant: family
---

# Follow-up Tracker Skill (Family Variant)

Reminding operation. Scan health, vehicle, and home maintenance pages for follow-up callouts; surface items due in the next 60 days. Keep the household ahead of medical recheck windows, vehicle service, and home maintenance schedules.

## When to Use

- Weekly (default cadence)
- Before scheduling appointments for the next month
- After a medical visit (a new follow-up was just logged)
- On request: "What follow-ups are due?"

## Inputs

User provides:
- Optional: window (default 60 days)
- Optional: filter (e.g., "medical only," "for Jake only")

Reads:
- All `wiki/health/{person}-medical.md` pages — scan for `> [!important] Follow-up due by {date}` callouts
- `wiki/home/maintenance/schedule.md` — recurring maintenance items
- All `wiki/home/vehicles/{vehicle}.md` pages — service due based on mileage / time
- `wiki/health/medications.md` — refills due
- All `wiki/people/*.md` pages — `> [!important] Follow-up due by {date}` callouts owed to/from family contacts (doctors, teachers, contractors, friends, extended family)
- `wiki/health/insurance.md` — open enrollment, annual checkpoints

## Algorithm

1. **Scan for callouts.** Find every `> [!important] Follow-up due by {date}` callout across health pages.
2. **Compute time-based dues.**
   - Vehicle: last-service-date + recommended-interval; flag if approaching
   - Maintenance: per `home/maintenance/schedule.md` cadence
   - Medications: refills based on prescription duration
3. **Filter to window.** Keep items due in the next 60 days; flag overdue separately.
4. **Group by category.** Medical / Vehicle / Home / Insurance / Other.
5. **Cross-reference providers.** For each medical follow-up, surface the relevant provider from `health/providers.md`.

## Output

Write `wiki/log/follow-ups-{YYYY-MM-DD}.md` (overwritten each run):

```yaml
---
type: follow-up-report
created: {today}
modified: {today}
tags: [follow-ups, reminding]
status: current
window_days: 60
---
```

Body sections:
- `## Synopsis` — count of due / overdue / coming-up items
- `## Overdue` — items past their date; surface most prominently
- `## Due in 30 days` — near-term items
- `## Due 30-60 days` — coming up
- `## By Person / Domain` — grouped view: per-person medical, per-vehicle, per-home-system

Each item includes the source page (wikilink), the due date, and recommended action (call provider, schedule service, refill).

## Side-effects

1. **Update `wiki/log/follow-ups-index.md`** with link to this run.
2. **Append to `log/changelog.md`**: "Follow-up tracker: {N} due / {M} overdue."

## Interactive Review

```
Follow-up tracker — {YYYY-MM-DD} (60-day window):

OVERDUE (1):
  - Jake's allergy panel recheck (was due 2026-04-10)
    → Source: [[health/jake-medical]]
    → Provider: [[health/providers#riverdale-pediatrics]]
    → Action: call to schedule

DUE IN 30 DAYS (3):
  - Jake's annual physical (due 2026-05-15)
  - Honda CR-V 60k service (due ~2026-05-08 based on current mileage)
  - HVAC filter replacement (due 2026-05-01 per maintenance schedule)

DUE 30-60 DAYS (2):
  - Sarah's mammogram (due 2026-06-12 per annual cadence)
  - Insurance open enrollment (window 2026-06-15 to 2026-06-29)

Schedule the overdue and 30-day items?
```

## Failure Modes

- **No follow-up callouts found.** Either the household is fully caught up, or callouts haven't been logged. If history medical pages exist but no callouts, suggest: "consider adding `> [!important] Follow-up due by ...` callouts when ingesting medical records to make tracking work."
- **Vehicle service-interval data missing.** Skip vehicle section; flag: "no recent service date logged for {vehicle}; ingest the latest receipt to enable mileage-based reminders."
- **All items overdue.** Healthy systems shouldn't accumulate overdue. Surface as a hygiene concern.

## Cadence

- **Manual:** Run weekly on review day.
- **Scheduled:** A Cowork weekly task on Sunday morning, output to the follow-ups page, ready for the maintainer to review.
