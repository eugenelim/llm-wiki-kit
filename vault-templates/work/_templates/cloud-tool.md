---
title: "{{Tool Name}}"
type: cloud-tool
status: in-use           # in-use | evaluating | rejected | deprecated
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [cloud-tool, {{provider}}, {{role}}]
cloud_provider: ""       # aws | gcp | azure | cloudflare | vercel | self-hosted | multi-cloud
role: ""                 # llm | vector-db | orchestrator | agent-runtime | observability | rag | tracing | etc.
url: ""
docs_url: ""
pricing: ""              # free-tier | pay-per-use | seat-based | enterprise
install_status: ""       # production | staging | poc | not-installed
maintainer: ""           # team member who owns this
adoption_date: ""        # YYYY-MM-DD when started
notes_keywords: []       # daily-driver | reference | high-leverage | risky-dependency | etc.
---

## Synopsis

{{One sentence: what this tool does and why it's in our agentic stack (or evaluation pipeline).}}

## What It Does

{{Specific capability the tool provides. Where in the stack it sits. What it replaces or complements.}}

## Trade-offs

{{Pros, cons, tensions vs. alternatives. Be honest about what's annoying or risky.}}

## Setup Notes

{{Install steps, key config, common gotchas. Anything that took the team time to figure out.}}

## Cross-References

- Related projects: [[projects/{{...}}]]
- Related ADRs: [[decisions/{{...}}]]
- Alternatives evaluated: [[tools/agentic-stack/{{alternative}}]]
- Domain page: [[domains/{{topic}}]]
