---
name: research-verdict-check
description: "Passive stop-signal for research. Run on demand during the Capture phase to get a recommendation about whether the research is converging, plateauing, or still incomplete. Does NOT interrupt captures or auto-progress phases — decision authority stays with the human. Use every few days during Capture, before deciding whether to invoke research-sieve, when sources accumulate without obvious new insight, or on request: \"check the research progress\" / \"should I keep capturing?\"."
license: MIT
metadata:
  variant: shared
---

# Research Verdict Check Skill

Passive stop-signal operation. Run on demand during the Capture phase to get a recommendation about whether the research is converging, plateauing, or still incomplete. Does NOT interrupt captures or auto-progress phases — decision authority stays with the human.

## When to Use

- During Capture, every few days, to gauge progress
- Before deciding whether to invoke [[research-sieve]]
- When you've added several sources without obvious new insight (diminishing-returns check)
- On request: "Check the research progress" or "Should I keep capturing?"

The framework's most useful discipline is "stop the moment the verdict becomes clear." This skill encodes that **passively** — surfacing a recommendation, not blocking action.

## Inputs

User provides:

- Project slug or path. If absent, defaults to the most-recently-modified research project.

Reads:

- `wiki/research/{slug}/overview.md` — phase, verdict_status, central claim, verdict_shape
- `wiki/research/{slug}/sources/*.md` — count, recency, pillar contributions
- `wiki/research/{slug}/{entities,attributes,mental-model,verdict}.md` — pillar fullness
- `wiki/research/{slug}/artifact.md` — if present, the current verdict

## Algorithm

1. **Compute source statistics.**
   - Total source count
   - Sources added in the last 7 days vs. prior
   - Per-pillar contribution count (how many sources contribute to each pillar)
   - **Diminishing-returns signal:** of the most recent 3 sources, are they adding *new* pillar contributions, or just confirming existing ones? If confirming, signal "diminishing."

2. **Compute verification status.**
   - Read pillar pages, count distinct claims
   - For each claim, count corroborating sources (≥2 = corroborated, 1 = single-source, 0 = unsupported)
   - **Verification ratio** = corroborated / total claims

3. **Compute pillar fullness.**
   - Each pillar's claim count vs. an expected minimum:
     - Matrix: 3+ entities, 5+ attributes, 2+ mental-model rules
     - Shortlist: 3+ candidates in verdict, 3+ anchors in mental-model
     - Blueprint: 3+ zones in entities, 2+ flow rules in mental-model
   - Flag pillars that are under-populated for the declared `verdict_shape`

4. **Determine verdict_status:**

   | Status | Conditions |
   |---|---|
   | `open` | Early phase, pillars sparse, verdict ambiguous |
   | `crystallizing` | Pillars filling, top candidates emerging, verification building |
   | `clear` | Pillars full, top candidate stable across recent sources, verification ratio > 80% |
   | `challenged` | Recent sources contradict the leading verdict; needs investigation |

5. **Generate recommendation:**

   - `open` + sparse pillars → continue capture; target the most-empty pillar
   - `crystallizing` + low verification ratio → continue capture, focus on corroborating single-sourced claims
   - `clear` AND diminishing-returns signal → stop capture; run [[research-sieve]] then [[research-synthesize]]
   - `challenged` → investigate the contradiction before more capture

## Output

A markdown summary printed inline (does NOT write a wiki page — this is conversational, not archival):

```
Research verdict check for {project}:

Phase: capture
Verdict status: crystallizing
Sources: 12 (3 added in last 7 days)
Diminishing-returns signal: confirming (recent sources mostly corroborate existing claims)

Pillar fullness:
  Entities:     6 ✓ (matrix needs 3+)
  Attributes:   7 ✓ (matrix needs 5+ for meaningful comparison)
  Mental model: 3 ✓
  Verdict:      4 candidates with leader: Claude Code

Verification:
  Claims: 12 total
  Corroborated (≥2 sources): 8 (67%)
  Single-source (flag): 4 — "agentic capabilities" (Claude Code), "plugin ecosystem"
    (Cursor), "long-context handling" (Cursor), "team adoption pattern" (Aider)

Recommendation: capture 2-3 more sources targeting the 4 single-source claims, then sieve.
The verdict is crystallizing but not yet clear. After targeted capture, expect verification
ratio to exceed 80% and verdict_status to move to clear.
```

## Side-effects

1. **Optionally update `verdict_status`** on the project overview if the computed status has changed materially. (Light side-effect; doesn't block forward progress.)
2. **No wiki page is written.** This is a conversational report. Run-history isn't archived — it would be noise; the verdict trail in the artifact suffices.

## What it doesn't do (passive design)

- Doesn't block further captures
- Doesn't auto-progress the phase
- Doesn't autonomously stop research

The user reads the recommendation and decides. The discipline is the user's; the skill informs.

## Failure Modes

- **No active project.** Surface: "No research project found. Run [[research-start]] first or specify a project slug."
- **Project has 0 sources.** Recommendation: "Capture before checking. Aim for 5-10 sources before first verdict-check."
- **Verdict_shape declared but pillar shape mismatches.** E.g., shape = matrix but entities pillar has 1 entity. Flag: "Verdict shape may need to switch to {alternative} given the pillar shape so far."

## Cadence

- **On demand:** Run as often as you find useful — every 2-3 days during active capture is a reasonable rhythm
- **Before invoking sieve:** Get a final recommendation before committing to phase progression
- **No scheduled runs:** Passive operations don't push reports — pull them
