# efforts/projects/

The **project** container registry. One container per project — the
durable, named pieces of work you steer. A project is a **hub-mode**
container: each project is a single page `efforts/projects/<project>.md`,
and its material (decisions, stakeholder updates, meeting notes) lives in
its own role folder and points back with the `parent:` relation.

## Hub mode, not a folder of pages

Unlike a trip (a folder of exclusive material), a project's material is
*shared* — a decision belongs to the project but is also a `library/`
capture in its own right. So the project page is a **hub**: a one-page
overview that its members link to.

- **One page per project.** `efforts/projects/<short-name>.md` in
  kebab-case (`migrate-billing.md`, `apollo-revamp.md`). Codenames are
  fine when the public name is ambiguous.
- **Members join by `parent:`.** A decision in `library/` that belongs to
  this project declares `parent: [[wiki/efforts/projects/migrate-billing]]`.
  The project page does not move them; it links to them.
- **Frontmatter.** The project page declares its `genre`/`subtype` and the
  baseline fields. There is no `projects/<project>/` subfolder.

## What goes on a project page

Short, durable framing — not a running journal:

- One-line summary of the goal; the DRI (wikilink to `wiki/people/`).
- Key stakeholders, linked customers (`wiki/people/`), recent decisions
  and updates (`wiki/library/`, joined by `parent:`).
- Open risks and current status (high-level); out-of-scope items.

Avoid duplicating content that already lives on a capture or
status-synthesis page — wikilink instead.

## Created by other primitives

Most project pages are *created on first reference* by content-type
ingesters. A stakeholder-update ingester that sees a new project name
stubs a hub page (with `status: draft`, `provenance: synthesized`) and
links to it. `status-synthesis` produces a *separate* digest page; it does
not edit the project hub.
