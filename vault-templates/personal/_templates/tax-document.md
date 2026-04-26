---
title: "{{Form Type}} — {{Issuer}} ({{Year}})"
type: tax-document
status: received         # received | reconciled | filed
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [tax, {{tax-year}}, {{form-type}}]
tax_year: {{YEAR}}
form_type: ""            # W-2 | 1099-DIV | 1099-INT | 1099-B | 1099-MISC | 1099-NEC | 1098 | K-1 | 5498 | 1095-A | etc.
issuer: ""               # employer / brokerage / bank / partnership name
amount: ""               # key headline amount (income, dividends, interest, etc.)
received_date: {{YYYY-MM-DD}}
filed_with: ""           # tax-prep service / accountant; empty until filed
---

## Synopsis

{{One sentence: what this form is and what it covers.}}

## Key Figures

<!-- Specific amounts that go on the return, per form type. -->

- {{Figure name}}: ${{value}}
- {{Figure name}}: ${{value}}

## Source Document

- File: [[raw/tax/{{tax-year}}/{{slug}}.pdf]]
- Issuer's contact: {{phone / portal URL if needed for corrections}}
- Form date / postmarked: {{YYYY-MM-DD}}

## Reconciliation Notes

{{Match against expected (year-end pay stub, brokerage records, prior-year comparison). Surface any discrepancies.}}

## SSN / Sensitive Data

<!-- The original PDF may contain SSN. The wiki page MUST NOT propagate it. Note "redacted" if applicable. -->

- {{SSN: redacted (kept on PDF only) | not present | flagged for user}}

## Cross-References

- Tax-year folder: [[finances/tax/{{tax-year}}/index]]
- Related holdings (for 1099-DIV / 1099-B): [[finances/holdings/{{...}}]]
- Filing artifact: [[finances/tax/{{tax-year}}/return]] *(after filing)*
