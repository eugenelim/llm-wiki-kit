# The organizing philosophy: link, map, synthesize

> Understanding-oriented. This explains *why* vaults the kit produces are
> shaped the way they are. For the rules a contributor follows, see the
> frontmatter schema and the relevant spec; for how to do a specific
> task, see the how-to guides.

A vault the kit produces is not a filing cabinet. It is a **thinking
space** an LLM keeps in good order on your behalf. Two lineages shape it,
and they layer cleanly:

- **The LLM-Wiki pattern** (Karpathy, 2025) is the *maintenance model* —
  an agent compiles sources into a durable markdown knowledge base and
  keeps it current, instead of re-deriving everything per query. This is
  *what the vault is*.
- **Linking Your Thinking** (LYT, Nick Milo) is the *organizing
  philosophy* — knowledge is structured by connection and synthesis, not
  by where a file is filed. This is *how the vault is shaped*.

We adopt LYT's vocabulary and principles and credit it as the lineage —
the synthesis layer is the **Atlas**, its hubs are **MOCs**. We are not
affiliated with LYT and depend on no LYT tool or product.

## Link, don't file. Map, don't bury. Synthesize, don't hoard.

Five tie-breakers put that into practice — the first three are the
headline above; the last two guard the synthesis layer. Together they
settle any vault-structure question.

### 1. Linking over filing

The weakest way to find something in a markdown vault is to remember which
folder you put it in. A folder forces a single home, but most real things
belong to several places at once — a meeting belongs to a project *and* the
people in it *and* a decision it produced. Force it into one folder and you
have lost the other three connections.

So connection is the primary structure: **wikilinks, relations, and
frontmatter facets**. Folders remain — they are a thin, browsable
convenience — but they never carry the classification. You find things by
links, maps, and queries, not by navigating a tree. A page's *kind*
(`genre`), its *area* (`workspaces`, RFC-0008's lens axis), and its *form*
(`subtype`) are facets it declares, not folders it is trapped in.

### 2. MOCs are the navigation layer

A **Map of Content (MOC)** is a note whose job is to link to other notes —
an index, a hub, a table of contents for a topic. It is "a meta-note": you
open it and immediately see the landscape of an area and everything related
to it, without clicking through folders.

MOCs are how both you and the agent enter the vault:

- `index.md` is the vault's root MOC — the dashboard.
- An **area MOC** (e.g. a "Health" page) gathers everything in a workspace
  (RFC-0008's `workspaces:` area axis), usually by an embedded query.
- Each **container** carries an `_index.md` MOC that groups its contents.

A MOC is itself a kind of note — its `genre` is `moc`. When you see a page
marked `genre: moc`, it is a map, not source material.

### 3. Structure is emergent, not pre-imposed

You do not design the whole taxonomy up front. The vault ships a small,
fixed **spine** — a handful of generic genres, the role folders, the facet
keys — and everything else *grows from use*: new facet values, new MOCs,
new connections. The agent may *propose* additions (a recurring tag worth
promoting to a controlled `subtype` value), but a human accepts them before
they enter the controlled vocabulary. Workspaces are composed from recipe
primitives, not grown emergently (RFC-0008). The structure earns its shape
from your actual material instead of a guess made on day one.

### 4. Protect the synthesis peak

Not all notes are equal. **Captured and ingested material** — meeting
notes, lab results, clippings, literature notes — is high-volume and
individually low-value. **Synthesized notes** — decisions, summaries,
evergreen concepts, MOCs — are low-volume and high-value; they are where
understanding actually lives.

If you mix them, the flood of capture buries the synthesis, and you stop
working at the level that matters. So the vault separates them:

- `library/` holds capture and reference. It is allowed to be a big pile;
  you navigate it by query. The agent fills it freely.
- `atlas/` holds synthesis (LYT's term for the knowledge space). It is kept
  small and deliberate. New synthesized notes are *gated* — the agent
  proposes them rather than spawning them at will — so neither capture
  volume nor an over-eager LLM can erode the peak.

A captured source and the synthesis drawn from it are **two linked notes**,
never one mixed document: the lab result lives in `library/`, the health
summary that cites it lives in `atlas/`.

### 5. The vault is for thinking, not storage

The point of all of the above is note-*making*, not note-*taking*:
connected understanding that you — and the people around you who only ever
read the vault — can actually use. Every structural choice serves that, or
it is wrong.

## How the structure embodies it

```
raw/                          # source files (immutable)
wiki/
  index.md                    # root MOC
  people/                     # nodes: people, orgs, vendors, customers
  efforts/<type>/<instance>/  # bounded containers: trips, cases, projects, studies
  library/                    # capture & reference (high-volume; agent-filled)
  atlas/                      # synthesis (low-volume; gated; where you work)
```

- **Folders key only stable, single-valued roles** (node, container,
  capture, synthesis) — never a topic or a changing status.
- **Containers** (a trip, a medical case, a research study) are *instances*
  with their own identity and lifecycle. Their contents sit *flat* inside,
  grouped by an `_index.md` MOC — never re-siloed into per-kind subfolders.
- **Lifecycle is a facet** (`status`), not a folder: archiving a note sets
  its status; it never loses its home.
- **An "area"** (Health, Finances) is not a folder — it is a workspace
  (RFC-0008's `workspaces:` lens) with an optional `genre: moc` page that
  queries everything in it.

The deeper rationale for the facet model, the container rules, and the
emergent-growth mechanics is recorded in the RFC that introduced them.
