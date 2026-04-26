---
name: skill-gap-analysis
description: "Compare declared goals against current skill state; surface underdeveloped skills the goals require and recommend learning priorities (typically books / courses / projects). Use quarterly after quarterly-review surfaces theme shifts, after annual-review proposes next-year goals, before reading-queue prioritization, or on request: \"what skills should I be developing?\"."
license: MIT
metadata:
  variant: personal
---

# Skill Gap Analysis Skill (Personal Variant)

Compare declared goals against current skill state; surface underdeveloped skills that the goals require. Recommend learning priorities — typically books / courses / projects that would close the gap.

## When to Use

- Quarterly (after [[quarterly-review]] surfaces theme shifts)
- After [[annual-review]] proposes next-year goals
- Before [[reading-queue]] prioritization (skill gaps inform what's worth reading)
- After a target role surfaces that requires unfamiliar skills
- On request: "What skills should I be developing?"

## Inputs

User provides:
- Optional: a target role or context to analyze against (e.g., "for the Acme platform-engineer role")
- Optional: time horizon (e.g., "skills to develop in the next 6 months")

Reads:
- `wiki/career/skills/*.md` — current skill state, self-assessed level per skill
- `wiki/goals/*.md` — declared goals (each goal implies skill requirements)
- Recent projects `wiki/projects/*/overview.md` — what skills the user is already exercising
- Recent atomic notes in `wiki/notes/` — implicit skill development through engagement
- `wiki/career/narrative/` most recent — what the user wants to be known for
- `wiki/books/` with status `done` — what's been studied

## Algorithm

1. **Inventory current skills.** For each declared skill in `wiki/career/skills/`:
   - Self-assessed level (e.g., novice / intermediate / advanced)
   - Date of last evidence (project, talk, note, application)
   - Active development or maintenance mode
2. **Derive required skills from goals.** For each active goal, decompose into the skills it requires. This step is the most subjective; surface the decomposition for user review.
3. **Compute gaps.** Required skills the user lacks or is underdeveloped in. Categorize:
   - **Critical** — gates a near-term goal (3-6 month horizon)
   - **Strategic** — supports a longer-arc goal (12+ months)
   - **Adjacent** — would compound existing strengths but not blocking
   - **Drift** — skills the user has but isn't using; quietly atrophying
4. **Recommend learning priorities.** For each critical / strategic gap, recommend: a book in the queue (or to add), a course, a project that would build the skill, a person to talk to.
5. **Surface drift.** Skills declared as core to the career narrative but not exercised in 6+ months.

## Output

Inline markdown report (does NOT write a wiki page; pairs with [[reading-queue]] which DOES persist):

```
Skill gap analysis — current goals + 6-month horizon:

CRITICAL ({count}):
  Distributed systems design (intermediate → advanced)
    Required by: "Senior platform engineer track" goal
    Current evidence: 3 projects + 7 atomic notes (active mode)
    Gap: lacking depth on consistency models; no production experience with
         consensus systems
    → Recommendations:
      - Book in queue: [[books/designing-data-intensive-applications]] (in progress)
      - Project: contribute to {open-source consensus library} or build a small Raft impl
      - Person: talk to [[network/relationships/diego]] who works on consensus

STRATEGIC ({count}):
  Technical writing (intermediate → advanced)
    Required by: "Build public-facing portfolio" goal
    Current evidence: 2 talks + personal site (active)
    Gap: long-form pieces (none > 2000 words this year)
    → Recommendations:
      - Project: write a 5000-word post on event-driven thinking
      - Person: ask [[network/relationships/sarah]] for editorial feedback

ADJACENT ({count}):
  Public speaking (intermediate)
    Would compound: current writing focus + visibility goals
    Gap: no formal speaking practice
    → Recommendations: add to skill list as active development; pair with talk
      drafts already in flight

DRIFT ({count}):
  Backend Go (was advanced; last evidence 2025-Q2)
    Listed in narrative but not exercised in 12 months.
    → Decision: re-engage (with a project) OR remove from narrative claims

Recommend: prioritize CRITICAL gaps; queue Strategic for next quarter; address
DRIFT explicitly (re-engage or remove from narrative).
```

## Side-effects

1. **Update `wiki/career/skills/{skill}.md`** for any skills where the analysis surfaces drift — note the date of the analysis.
2. **Feed [[reading-queue]]** — skill priorities inform queue prioritization.
3. **Surface `wiki/career/narrative/` claims** that may need updating if drift is significant.
4. **Append to `log/changelog.md`**: "Skill gap analysis: {N} critical, {M} strategic, {K} drift."

## Interactive Review

```
Skill gap analysis (against current goals):

Critical gaps surfaced (2):
  1. Distributed systems design — depth at consensus layer
  2. {Other}

Strategic gaps surfaced (1):
  1. Long-form technical writing

Drift surfaced (1):
  1. Backend Go — declared in narrative but not exercised in 12 months
     → Decision needed: re-engage or remove the claim?

Add critical and strategic priorities to wiki/career/skills/*.md?
Refresh narrative to address the drift?
```

## Failure Modes

- **No goals declared.** Block: "Skill gap analysis requires declared goals. Author goals first; ([[goals/{quarter}.md]]) or run [[quarterly-review]] which produces the next-quarter goals."
- **No skill pages.** Bootstrap: propose creating an initial set based on the career narrative's claims.
- **Gap analysis shows no critical gaps.** Healthy alignment — current goals match current strengths. Surface as positive signal; consider whether goals are ambitious enough.

## Cadence

- **Quarterly:** Run alongside quarterly review.
- **On demand:** Before defining new goals; before pursuing target roles; when reading queue feels arbitrary.
- **No scheduled runs:** Skill development is deliberate.
