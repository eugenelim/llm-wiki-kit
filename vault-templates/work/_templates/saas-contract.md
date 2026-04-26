---
title: "{{Vendor / Service Name}}"
type: saas-contract
status: active           # active | paused | cancelled | up-for-renewal
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [saas, {{category}}]
vendor: ""               # company
category: ""             # observability | source-control | comms | crm | analytics | security | productivity | etc.
url: ""
contract_start: ""       # YYYY-MM-DD
contract_end: ""         # YYYY-MM-DD
renewal_date: ""         # YYYY-MM-DD; trigger renewal review 60-90 days before
billing_cycle: ""        # monthly | annual | multi-year
amount: ""               # $X /period
seats: ""                # number of seats / users
account_owner: ""        # team member who owns the relationship
admin_contact: ""        # vendor-side AE / CSM (name + email)
---

## Synopsis

{{One sentence: what this vendor / service provides and why we use it.}}

## Capabilities Used

{{Specific features we rely on. Helps with renewal evaluation — features we don't use are the cancellation case.}}

## Renewal Considerations

{{What to evaluate at renewal time: alternatives, usage patterns, price changes, seat utilization, contract terms to renegotiate.}}

## Notes

{{Login coordination, how seat allocation works, key contacts on vendor side, last review summary, upgrade / downgrade history.}}

## Cross-References

- Related projects: [[projects/{{...}}]]
- Related cloud-tools: [[tools/agentic-stack/{{...}}]]
