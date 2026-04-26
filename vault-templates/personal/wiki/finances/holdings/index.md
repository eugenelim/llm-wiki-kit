---
type: index
folder: holdings
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, holdings, inventory, finances]
---

## Synopsis

Investment-portfolio holdings inventory. Tracks every position across brokers, account types, and asset classes. Each holding is a file with `type: holding` frontmatter; the live filtered view is `holdings.base`.

## How this folder works

Each holding is a `.md` file with the schema declared by `_templates/holding.md` (ticker, asset class, broker, account type, shares, cost basis, acquired date, sector). Add entries by copying the template; browse via `holdings.base`.

## Common access patterns

- "What do I hold at Schwab?" → filter by broker
- "Roth-IRA composition" → filter by account_type
- "Total exposure to {sector}" → group by sector
- "Holdings due for review" → sort by last_review (ascending)
- "Tax lots for {ticker}" → individual holding page; cross-references the relevant 1099-B

## Privacy posture

Holdings data is **highly sensitive**. The cloud drive's at-rest encryption is the baseline. Do NOT route holdings questions to external research providers — abstract queries only ("what's the cap-gains rate for long-term ETF holdings" is fine; "should I sell X" with personal context is NOT). The personal-variant CLAUDE.variant.md privacy section spells out this rule.

If using Git-backed sync, keep the repository private.

## Related

- Tax records (`wiki/finances/tax/`) reference holdings for 1099-B and 1099-DIV
- Decision log captures buy/sell decisions; cross-link to relevant holdings
- Career narrative may reference compensation structure, but holdings details should stay in this folder (more sensitive than narrative)
