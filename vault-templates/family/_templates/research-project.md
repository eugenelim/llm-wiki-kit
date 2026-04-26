---
title: "{{Research Project Title}}"
type: research-project
status: active
provenance: synthesized
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [research, {{topic-slug}}]
central_claim: "{{One sentence stating the bet — what you expect to be true}}"
verdict_shape: matrix       # matrix | shortlist | blueprint — declared upfront, drives the synthesize artifact
phase: capture              # capture | sieve | synthesize | feedback
verdict_status: open        # open | crystallizing | clear | challenged
verification_count: 0       # number of verdict claims with ≥2 corroborating sources
---

## Synopsis

{{One- to two-sentence summary: what this research is trying to decide; current phase and verdict status.}}

## Central Claim

> {{One sentence. The Bet. Without a claim, research is just browsing.}}

## The Four Pillars

- [[entities]] — the catalog (the "nouns" being studied)
- [[attributes]] — measurable specs that enable objective comparison
- [[mental-model]] — rules of how this domain works (cause-and-effect)
- [[verdict]] — the actionable selection plus verification trail

## Sources

Raw ingested material lives in `sources/`. Each source page tags its `pillar_contributions:` so [[research-sieve]] knows where each fragment belongs.

## Artifact

The synthesized output. Shape is declared upfront in `verdict_shape:`. Lands at [[artifact]] when [[research-synthesize]] runs.

## Stop Conditions

Run [[research-verdict-check]] on demand (passive — surfaces a recommendation when run; does not interrupt captures or auto-progress phases). Stop and move to `phase: feedback` when:

- Each load-bearing verdict claim has ≥2 corroborating sources (Two-Source Rule)
- The artifact's shape is stable across the last 3 sources reviewed
- Marginal new sources reinforce rather than shift the verdict

## Phase Log

- {{YYYY-MM-DD}}: research-start (phase = capture; central claim defined; verdict_shape = {{matrix | shortlist | blueprint}})
