---
title: "{{Source Title}}"
type: research-source
status: current
provenance: extracted
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [research-source, {{topic-slug}}]
project: "[[research/{{slug}}/overview]]"
source_url: "{{URL or attribution}}"
source_kind: web                # web | paper | report | interview | document | conversation
fetched_via: defuddle           # defuddle | pure.md | docling | perplexity | semantic-scholar | manual
fetched_at: {{YYYY-MM-DD}}
pillar_contributions: []        # subset of [entities, attributes, mental-model, verdict]
verification_strength: secondary  # primary | secondary | hearsay
citations: []                   # for sources that themselves cite other works
published_at: ""                # when the source itself was published
events_described: ""            # date or range the source describes; affects currency
---

## Synopsis

{{One sentence: what this source contributes to the research project.}}

## Provenance

- **Author / publisher:** {{}}
- **Published:** {{YYYY-MM-DD}}
- **Accessed:** {{YYYY-MM-DD}}
- **URL / file:** {{}}

## Pillar Contributions

For each pillar this source contributes to, summarize and quote the supporting passage.

### Entities
{{What entities does this source name? Any new entities not yet in [[entities]]?}}

### Attributes
{{What measurable attributes does this source provide? Quote and cite passage location.}}

### Mental Model
{{Does this source advance or contradict the mental model? Quote.}}

### Verdict
{{Does this source support a specific verdict? Quote.}}

## Key Claims

Direct extractions, with passage citation. These feed the artifact's verification trail.

- "{{Claim}}" — {{location in source — section number, page, timestamp}}
- "{{Claim}}" — {{location}}

## Adversarial Read

What's missing, biased, or possibly misleading. The Two-Source Rule check.

- {{Concern}}
- {{Counter-source needed: {{...}}}}

## Chronology

- **Source published:** {{date}}
- **Events described happened:** {{date or range}}
- **Currency:** {{is this stale? superseded? still valid?}}
