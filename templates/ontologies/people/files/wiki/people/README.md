# people/

The **entity-node** role folder: one page per person *or* organization
you interact with often enough to want a single durable note for. This is
the only folder for nodes you link to by name — meetings, interviews,
stakeholder updates, receipts, contracts, and follow-ups all wikilink here.

## One folder, many subtypes

People, organizations, vendors, and customers are **not** separate
folders — they are all node pages here, distinguished by the `subtype`
facet, never by location:

- `subtype: person` — an individual (`jane-doe.md`, `j-park.md`).
- `subtype: org` — a company, team, school, or other group.
- `subtype: vendor` — a business the household transacts with (the
  plumber, the clinic, the brokerage). A vendor is an org you pay.
- `subtype: customer` — an account you sell to or serve.

Filing by role (an entity node) rather than by kind (customer vs. vendor)
is the whole point: a vendor who becomes a customer changes a `subtype`
value, not a folder. Filter the views by `subtype` (the `_index.md` map
groups by it); never mint a `customers/` or `vendors/` folder.

## Conventions

- **One page per node.** Filename is the display name in kebab-case:
  `jane-doe.md`, `acme-corp.md`. Initials are fine when a full name would
  be ambiguous or sensitive.
- **Frontmatter.** Every node page declares `genre: profile`, a `subtype`
  from the list above, and the baseline fields (`status`, `provenance`,
  `created`, `modified`, `tags`).
- **Aliases as wikilinks.** If a node is known by multiple names ("Jane
  Doe", "JD"), pick the canonical filename and reference the aliases in
  the body. The vault-side `wiki-search` skill resolves common aliases.
- **Sensitive details.** Personal information beyond what's needed to do
  your work belongs in a separate, gitignored vault or out of the vault
  entirely. Default to the minimum useful page.

## What goes on a node page

Short, durable framing — not a chat log:

- Role / affiliation, how you know them, the `subtype` that applies.
- Stable preferences, constraints, recurring topics.
- Links to the meetings, interviews, or threads that mention them.

Avoid duplicating content that already lives on a capture page in
`library/` — wikilink instead.

## Created by other primitives

Most node pages are *created on first reference* by content-type
ingesters. A meeting ingester that sees a new attendee name stubs a
person page (with `status: draft`, `provenance: synthesized`) and links
to it; a customer-feedback ingester stubs a `subtype: customer` node the
same way. You promote the stub to a real page when you have something
worth writing.
