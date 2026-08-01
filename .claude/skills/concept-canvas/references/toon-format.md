# TOON format used by concept-canvas

TOON (Token-Oriented Object Notation) is a compact, indentation-based serialization
format optimized for LLM consumption: uniform arrays are written as a header with
field names once, followed by CSV-like rows — roughly 40–60 % fewer tokens than the
equivalent JSON.

concept-canvas uses a small, flat subset. One document per annotation round:

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
| `target` | Machine id: `section:<id>`, `diagram:<id>`, or `node:<mermaid-node-id>` |
| `label` | Human-readable label the user saw when annotating |
| `comment` | The user's free-text comment (may contain `\n` escapes) |

## Parsing tips

- Split the array rows with a CSV parser that honors double quotes, or with this
  logic: walk the line char by char, toggle in-quote state on unescaped `"`.
- `target` tells you *where* to act: `section:`/`diagram:` map to `data-annot`
  attributes in the HTML; `node:` maps to a Mermaid node id inside some diagram.
- Unescape `\n` in comments before reasoning about multi-line feedback.
