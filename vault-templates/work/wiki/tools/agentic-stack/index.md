---
type: index
folder: agentic-stack
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, cloud-tool, agentic-stack, inventory]
---

## Synopsis

Cloud-software inventory for agentic systems. Tracks the tools we run (or evaluate) per cloud provider per role in the stack. Each entry is a small file with `type: cloud-tool` frontmatter; the live filtered view is `agentic-stack.base`.

## How this folder works

Each tool is a `.md` file with the schema declared by `_templates/cloud-tool.md` (cloud provider, role in stack, install status, maintainer). Add entries by copying the template; browse via `agentic-stack.base`.

## Common access patterns

- "What do we use on AWS for vector storage?" → filter by cloud_provider + role
- "What's currently in production vs. POC?" → filter by install_status
- "Who owns Modal?" → filter or search by tool name; check maintainer
- "Alternatives we considered" → filter by status: rejected

## Related

- The `tool` page type at `wiki/tools/{tool}.md` covers individual tool *evaluations* (deep dives, ADR-grade analysis); this `cloud-tool` inventory is the catalog of what we actually run, lighter-weight per entry
- [[cross-project-synthesis]] reads tool inventory entries as part of domain page refreshes
- [[adr-review-queue]] flags pending ADRs that affect tool selection

## Roles in our agentic stack

Common values for the `role:` field:
- `llm` — language model providers (Anthropic, OpenAI, Bedrock, Vertex)
- `vector-db` — vector storage / similarity search
- `orchestrator` — agent / workflow orchestration
- `agent-runtime` — execution environment for agents
- `observability` — tracing, eval, monitoring
- `rag` — retrieval / context-augmentation
- `tracing` — distributed tracing / debugging
- `eval` — evaluation, regression testing
- `data` — datasets, labeling, curation
- `security` — guardrails, prompt-injection defense, secrets
