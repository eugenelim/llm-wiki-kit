---
type: index
folder: vendors
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, saas-contract, vendors, inventory]
---

## Synopsis

SaaS / vendor contract registry. Tracks every paid vendor relationship — observability, source control, comms, CRM, analytics, security, etc. Each entry is a small file with `type: saas-contract` frontmatter; the live filtered view is `vendors.base`.

## How this folder works

Each vendor / contract is a `.md` file with the schema declared by `_templates/saas-contract.md` (vendor, category, contract dates, billing cycle, amount, seats, account owner). Add entries by copying the template; browse via `vendors.base`.

## Common access patterns

- "What's coming up for renewal in the next 90 days?" → sort by renewal_date
- "Who owns the {tool} relationship?" → filter or search; check account_owner
- "What categories of SaaS spend do we have?" → group by category
- "How many seats are we paying for vs. using?" → renewal-time review

## Related

- [[adr-review-queue]] surfaces vendor-selection decisions in flight
- [[cross-project-synthesis]] reads vendor entries when refreshing a domain page (e.g., observability domain reads observability vendors)
- Renewal-readiness is a quarterly cadence; surface upcoming renewals in [[weekly-digest]]

## Why this is separate from agentic-stack

`saas-contract` tracks the *commercial relationship* (contract terms, renewal timing, account ownership). `cloud-tool` tracks the *technical fit and operational role*. Many tools have both an agentic-stack entry (technical) AND a saas-contract entry (commercial); cross-link them.
