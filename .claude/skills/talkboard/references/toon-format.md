# TOON format used by talkboard

TOON (Token-Oriented Object Notation) is a compact, indentation-based serialization
format optimized for LLM consumption: uniform arrays are written as a header with
field names once, followed by CSV-like rows — roughly 40–60 % fewer tokens than the
equivalent JSON.

talkboard uses a small, flat subset. One document per annotation round:

```
doc: oauth2-flow
title: OAuth2 verständlich
exported: 2026-07-31T14:22:09Z
annotations[3]{id,target,label,comment}:
  1,section:overview,Überblick,Gute Einführung
  2,node:gateway,API Gateway,"Warum sitzt Rate Limiting hier, nicht im LB?"
  3,diagram:auth-flow,Auth-Flow Diagramm,"Zwei Punkte:\n1. Refresh fehlt\n2. Fehlerpfad?"
```

## Rules

- **Top-level scalars**: `key: value`, one per line.
- **Tabular array**: `name[N]{field1,field2,…}:` declares an array of `N` uniform
  objects; each following line (indented two spaces) is one row, fields joined by `,`.
- **Quoting**: a cell is wrapped in double quotes when it contains a comma, a double
  quote, a newline, leading/trailing whitespace, is empty, or starts with `#` or `-`.
  Escapes inside quotes: `\\`, `\"`, `\n`. Everything else is written bare.
- Row count in the header (`[N]`) always matches the number of rows — use it as an
  integrity check when parsing.

## Field semantics

| Field | Meaning |
|---|---|
| `id` | 1-based row number of the annotation |
| `target` | Machine id: `section:<id>`, `diagram:<id>`, `graph:<id>`, or `node:<mermaid-node-id>` |
| `label` | Human-readable label the user saw when annotating |
| `comment` | The user's free-text comment (may contain `\n` escapes) |

## Parsing tips

- Split the array rows with a CSV parser that honors double quotes, or with this
  logic: walk the line char by char, toggle in-quote state on unescaped `"`.
- `target` tells you *where* to act: `section:`/`diagram:`/`graph:` map to `data-annot`
  attributes in the HTML; `node:` maps to a Mermaid node id inside some diagram.
- Unescape `\n` in comments before reasoning about multi-line feedback.

## Editable graph sections (optional tables)

A canvas may contain **graph sections** — freeform, directly editable node/edge
diagrams (built with cytoscape.js), distinct from the read-only Mermaid diagrams
above. When at least one graph section exists, three extra tables follow the
`annotations` table; a canvas with no graph section omits them entirely — the
document above is unaffected either way.

```
graphs[1]{id,label}:
  auth-flow,Auth Flow (edited)
graph_nodes[3]{graph,id,label}:
  auth-flow,client,Client
  auth-flow,gateway,API Gateway
  auth-flow,cache,Cache
graph_edges[2]{graph,from,to,label}:
  auth-flow,client,gateway,
  auth-flow,gateway,cache,"cache lookup"
```

| Table | Field | Meaning |
|---|---|---|
| `graphs` | `id` | The graph section's bare id — same string as the `<id>` part of its `data-annot="graph:<id>"`, **without** the `graph:` prefix |
| `graphs` | `label` | The section's human-readable label |
| `graph_nodes` | `graph` | Foreign key into `graphs.id` |
| `graph_nodes` | `id` / `label` | The node's id and current (possibly user-renamed) label |
| `graph_edges` | `graph` | Foreign key into `graphs.id` |
| `graph_edges` | `from` / `to` / `label` | Edge endpoints (node ids) and optional edge label |

Two things worth being deliberate about when reading these:

- **Full state, not a diff.** Every row reflects the graph's *current* structure at
  submit time — nodes/edges the user added, removed, renamed, or rewired are all
  folded together. Diff it yourself against what you originally authored if you
  need to know specifically what changed.
- **Prefix mismatch with `annotations.target`.** If the user also left a whole-figure
  comment on the same graph (via its caption/padding, same as any other diagram),
  that comment's `target` in the `annotations` table is `graph:auth-flow` — with the
  prefix — while `graphs`/`graph_nodes`/`graph_edges` use the bare id `auth-flow`.
  Strip the prefix (or add it back) when cross-referencing between the two.
