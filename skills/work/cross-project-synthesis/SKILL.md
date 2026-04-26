---
name: cross-project-synthesis
description: "Refresh a domain page (wiki/domains/{topic}.md) with learnings drawn from recent project work tagged with the topic. Synthesizing operation. Use after a project ships work touching a cross-project domain (e.g., order-platform finishes a Kafka design — refresh domains/event-driven-architecture.md), quarterly to keep domain pages fresh, or on request: \"synthesize what we've learned about {topic} across projects\"."
license: MIT
metadata:
  variant: work
---

# Cross-Project Synthesis Skill

Refresh a domain page with learnings drawn from recent project work. Synthesizing operation; on-demand or after major project milestones.

## When to Use

- After a project ships work that touches a cross-project domain (e.g., the order-platform team finishes a Kafka design — refresh `domains/event-driven-architecture.md` with new learnings)
- Quarterly, to keep domain pages from going stale
- On request: "Synthesize what we've learned about {topic} across projects"

The output is what makes the wiki actually compound across projects rather than siloing knowledge into dead project folders.

## Inputs

User specifies a topic. The skill maps the topic to a domain page and gathers source material:

1. **The target domain page.** `wiki/domains/{topic-slug}.md`. If absent, propose creation.
2. **All wiki pages tagged with the topic.** Pages whose frontmatter `tags:` includes `{topic-slug}` — could span specs, ADRs, meeting syntheses, design pages, research briefs across multiple projects.
3. **Recent activity.** Of those pages, prioritize the ones modified in the last quarter (or whatever window the user specifies).
4. **Existing domain page content.** Read in full — synthesis layers onto existing knowledge rather than overwriting it.
5. **Fact log if active.** If `domains/{topic-slug}.facts.md` exists (per [[fact-tracking]]), read all facts and check which are new since last synthesis.

## Algorithm

1. **Inventory the source material.** List every page touching the topic. For each: title, project, last modified, what it covers (synopsis-level).
2. **Cluster by sub-topic.** Within the domain, what aspects do the source pages cover? (e.g., for `kafka`: schema management, consumer groups, exactly-once semantics, monitoring, operations.)
3. **Identify novel learnings.** What's in the source pages that's NOT in the current domain page? — new patterns, contradicting recommendations, additional caveats, specific gotchas.
4. **Identify outdated content.** What in the current domain page contradicts or is superseded by recent source pages?
5. **Compose updates.** For each section of the domain page, decide: keep, augment, replace, deprecate.

## Output

Update `wiki/domains/{topic-slug}.md` in place. Don't overwrite — augment. Frontmatter:

- Update `modified:` to today.
- If `provenance` was `mixed`, keep; otherwise upgrade to `mixed` or `synthesized` as appropriate.
- If `last_synthesis:` field exists (per [[fact-tracking]]), update.

Body — preserve the existing structure where possible, but:

- For each newly added or revised paragraph, add an inline footnote linking to the source page(s):

  ```markdown
  KRaft mode (Kafka 3.3+) eliminates the ZooKeeper dependency for
  metadata management[^1].

  [^1]: From [[wiki/projects/order-platform/design/kafka-architecture-v2]],
        confirmed by [[wiki/research/2026-04-12-kafka-kraft-migration]]
  ```
- Mark any inferences (claims drawn across multiple sources but not stated in any single one) with `> [!note] Inferred` callouts.
- Preserve the `## Synopsis` at top; rewrite if the synthesis significantly changes the domain's center of gravity.

After updating: write a brief `wiki/log/synthesis-{topic}-{date}.md` summarizing what was added / changed and which source pages contributed:

```yaml
---
type: synthesis-log
topic: {topic-slug}
date: {today}
tags: [synthesis-log, {topic-slug}]
provenance: synthesized
---
```

## Side-effects

1. **Update the domain page's outbound links.** Fresh synthesis usually creates new wikilinks to project pages and research briefs.
2. **Append to `log/changelog.md`** with a one-line entry.
3. **Surface any contradictions found.** If two source pages disagree about the same fact, flag with `> [!danger] Contradiction` callout on the domain page rather than picking one silently.

## Interactive Review

Synthesis is opinionated by nature; always review with the user before saving the domain page changes. Present:

```
Synthesis for {topic} — proposed changes to wiki/domains/{topic-slug}.md:

Novel claims (added):
- {claim 1} — from {sources}
- {claim 2} — from {sources}

Updated claims:
- {existing claim} → {revised claim} — supersede reason: {reason}

Contradictions surfaced:
- {claim A from source X} vs {claim B from source Y}
  → flagging both with > [!danger] callout for human resolution

Save these changes?
```

The user can accept all, accept selectively, or redirect specific claims.

## Failure Modes

- **Topic not yet in `domains/`.** Either propose creating the page (with the user's confirmation) or stop and ask the user to author the seed.
- **Few or zero source pages.** The topic isn't well-represented in the wiki yet; synthesis would invent rather than synthesize. Stop and surface this.
- **Source pages contradict each other.** Don't try to pick a winner — flag with `> [!danger]` for human resolution.
- **Domain page has rich existing content.** Be conservative — augment rather than rewrite. Synthesis's job is to add new learnings, not refactor the domain page's structure.

## Cadence

- **Per major milestone:** When a project ships work touching a domain, run synthesis for that domain.
- **Quarterly:** Run for each major domain page to catch slow drift.
- **On request:** Whenever someone asks "what do we know about X?" and the answer might be stale.
