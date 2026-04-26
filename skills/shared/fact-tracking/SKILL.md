---
name: fact-tracking
description: "Optional. Enable append-only fact tracking for high-traffic entity pages that accumulate information from many sources over weeks or months, preserving an audit trail and the ability to rebuild the entity page from raw facts. Use only for entities where multiple sources contribute facts, synthesis quality matters, and full provenance matters. Do NOT use for meeting notes, project status pages, one-off research, or pages mostly authored rather than synthesized."
license: MIT
metadata:
  variant: shared
---

# Fact Tracking Skill (Optional)

Enable append-only fact tracking for high-traffic entity pages that
accumulate information from many sources over time.

## When to Use

This skill is optional. Enable it for entities where:
- Multiple sources contribute facts over weeks or months
- Synthesis quality matters (the entity page drives decisions)
- You want a full audit trail of every observation
- You need the ability to rebuild the entity page from raw facts

Good candidates: core technologies (Kafka, Kubernetes), domain concepts
(ERISA compliance, event sourcing), key system components, vendors/tools
under active evaluation.

Do NOT use for: meeting notes, project status pages, one-off research,
pages that are mostly authored rather than synthesized.

## How It Works

### 1. Enable Fact Tracking for an Entity

When asked to enable fact tracking for a wiki page, create a companion
fact log file alongside the entity page:

```
wiki/domains/
├── kafka.md                # The wiki page (synthesized from facts)
└── kafka.facts.md          # Append-only fact log
```

### 2. Fact Log Format

The fact log is an append-only markdown file. Each fact is a list item
with a date, the fact itself, and a source reference:

```markdown
---
type: fact-log
entity: kafka
created: 2026-04-15
modified: 2026-04-25
tags: [kafka, fact-tracking]
provenance: extracted
---

## Synopsis

Append-only fact log for [[kafka]]. Contains 12 observations
from 5 sources. Last updated 2026-04-25.

## Facts

- **[2026-04-15]** Kafka consumer groups require unique group IDs
  per logical consumer.
  Source: [[raw/order-platform/design-review-2026-04-15.md]]

- **[2026-04-15]** Default replication factor is 1 (not suitable
  for production).
  Source: [[raw/order-platform/design-review-2026-04-15.md]]

- **[2026-04-20]** KRaft mode (Kafka 3.3+) eliminates ZooKeeper
  dependency for metadata management.
  Source: [[raw/research/papers/kafka-kraft-migration.pdf]]

- **[2026-04-20]** Exactly-once semantics require both idempotent
  producers AND transactional consumers.
  Source: [[raw/research/papers/kafka-exactly-once.pdf]]

- **[2026-04-25]** Schema Registry supports backward, forward, and
  full compatibility modes. Team prefers backward compatibility.
  Source: [[raw/order-platform/meeting-2026-04-24.md]]
  Context: Decision made during sprint planning. See [[adr-007]].
```

### 3. Recording Facts During Ingest

When ingesting a new source that mentions a fact-tracked entity:

1. Extract facts about the entity from the source
2. Check each fact against the existing fact log:
   - **New fact:** Append to the fact log with date and source
   - **Confirms existing fact:** Append with note "Confirms: [prior fact date]"
   - **Contradicts existing fact:** Append with `⚠️ CONTRADICTS` prefix
     and flag on the wiki page with a `> [!danger]` callout
3. After appending facts, decide if the wiki page needs resynthesis
   (see step 4)

### 4. Resynthesizing the Wiki Page

The entity's wiki page is a **synthesized view** of the fact log.
Resynthesize when:
- 5+ new facts have been added since last synthesis
- A contradiction has been flagged
- A human requests it
- The wiki page is explicitly queried and the facts are stale

Resynthesis process:
1. Read the complete fact log
2. Group facts by theme/category
3. Resolve any contradictions (prefer newer, higher-authority sources)
4. Rewrite the wiki page with:
   - Updated `modified:` date
   - `provenance: synthesized`
   - Footnotes linking to specific facts by date
   - `> [!note] Inferred` callouts for any conclusions drawn
5. Note the resynthesis in `log/changelog.md`

**The fact log is never modified during resynthesis.** It is append-only.
The wiki page is the mutable synthesis; the fact log is the immutable
source of truth.

### 5. Fact Log Metadata in the Wiki Page

When a wiki page has fact tracking enabled, add a frontmatter field:

```yaml
---
title: "Apache Kafka"
type: domain
fact_log: "[[kafka.facts.md]]"
facts_count: 12
last_synthesis: 2026-04-25
---
```

This tells other agents and humans that this page is backed by a
fact log and when it was last rebuilt from facts.

## Disabling Fact Tracking

If an entity no longer needs fact tracking (e.g., the evaluation is
complete and the page is stable), simply stop appending to the fact
log. The log remains as an audit trail. Remove the `fact_log:` field
from frontmatter if you want to signal that tracking is inactive.

## Interaction with Provenance

Fact log entries are always `provenance: extracted` — they are
source-faithful observations. The wiki page synthesized from the
log is `provenance: synthesized`. This distinction is automatic
when using this skill.
