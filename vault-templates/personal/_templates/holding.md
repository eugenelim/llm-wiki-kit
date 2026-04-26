---
title: "{{Holding Name}}"
type: holding
status: active           # active | sold | partial-sold
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [holding, {{asset-class}}]
ticker: ""               # AAPL | VTI | BTC | etc.
asset_class: ""          # stock | etf | mutual-fund | bond | crypto | reit | private | cash | etc.
broker: ""               # Fidelity | Schwab | Vanguard | Robinhood | Coinbase | Kraken | etc.
account_type: ""         # taxable | ira | roth-ira | 401k | sep-ira | hsa | trust | crypto-wallet | etc.
shares: ""               # quantity
cost_basis: ""           # total $ cost basis
acquired: ""             # YYYY-MM-DD; first acquisition date
last_review: ""          # YYYY-MM-DD; portfolio rebalance review
target_allocation: ""    # % target if part of an allocation strategy
sector: ""               # technology | financials | healthcare | international | bonds | etc.
---

## Synopsis

{{One sentence: what this holding is and its role in your portfolio.}}

## Thesis

{{Why you hold this. The reason you bought; conditions under which you'd sell. The decision-check operation reads this when revisiting.}}

## Tax Lots

<!-- Each acquisition with cost basis, for tax purposes. Critical for cap-gains calc when selling. -->

- {{YYYY-MM-DD}}: {{shares}} @ ${{price}} = ${{cost-basis}} ({{account-type}}, {{broker}})

## Performance Notes

{{Dividend / distribution history, ex-dividend dates. Update annually or after major events. Cross-reference 1099-DIV / 1099-B forms.}}

## Notes

{{Sector concentration concerns, intended hold period, conviction level, regulatory exposure.}}

## Cross-References

- Related decisions: [[decisions/{{...}}]]
- Related notes / topics: [[notes/{{...}}]], [[topics/{{...}}]]
- Tax-year forms: [[finances/tax/{{year}}/{{1099-form}}]]
- Allocation strategy: [[finances/allocation]] *(if maintained)*
