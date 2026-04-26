---
type: index
folder: subscriptions
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, subscriptions, inventory]
---

## Synopsis

Subscription inventory — every recurring charge the household pays. Each entry is a small file with `type: subscription` frontmatter; the live filtered view is `subscriptions.base`.

## How this folder works

Each subscription is a `.md` file with the schema declared by `_templates/subscription.md` (provider, billing cycle, next billing, amount, account holder, review-by date). Add entries by copying the template; browse via `subscriptions.base`.

## Common access patterns

- "What's coming up for renewal?" → sort by next_billing
- "Which subscriptions should we re-evaluate?" → sort by review_by
- "All streaming subscriptions" → filter by category: streaming
- "Family-plan vs individual" → check account_holder + seats / sharing notes

## Related

- [[follow-up-tracker]] surfaces subscriptions due for renewal
- [[ingest-receipt]] occasionally produces subscription entries from billing receipts
- Annual review is a natural cadence for sweeping the subscription list
