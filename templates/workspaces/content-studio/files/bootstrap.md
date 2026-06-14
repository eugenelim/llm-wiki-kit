# Content Studio — workspace bootstrap

You are working inside the **content-studio** lens of this vault: the notes
you draft, edit, and publish. This is one lens over a single knowledge bank —
not a separate vault. The same journal, frontmatter schema, and pages back
every lens.

## Scope

This lens covers notes whose `workspaces:` frontmatter contains
`content-studio`. To bring a note into the studio, add the lens to its
frontmatter:

```yaml
workspaces: [content-studio]
```

A note can belong to several lenses at once (e.g.
`workspaces: [research, content-studio]`) with no duplication on disk.

Open `content-studio.base` in Obsidian to see the lens as a Bases table.

## Working here

- Keep drafts and published pieces tagged into this lens so the `.base`
  view stays the single place you see studio work.
- The `personal-coordinator` agent is the default companion for this lens.
- Cross-cutting operations still run vault-wide; this lens filters *what you
  look at*, not *what the kit maintains*.
