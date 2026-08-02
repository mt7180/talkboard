---
name: talkboard
description: Turn a complex, multi-part explanation into an interactive, annotatable HTML document with Mermaid diagrams and editable graphs — instead of a long text reply, even when the user never mentions HTML (e.g. just "explain X to me"). Trigger for architectures, processes, data flows, trade-off comparisons, or any topic with real internal structure, and on explicit requests for a "talkboard" (or its old name "concept canvas"), an "interactive explanation", or an "annotatable doc" — or when the user wants to leave feedback that flows back to you as TOON.
---

# Talkboard

Explain complex concepts as an interactive HTML document the user can read in the browser, annotate with free-text comments, and send back. Annotations return to you as **TOON** (Token-Oriented Object Notation) — on stdout and as a `.toon` file — so you can process the feedback and iterate.

The loop:

1. You build an HTML canvas (content sections, plus a Mermaid diagram or an editable graph section only where one genuinely helps) from the template.
2. `scripts/serve_and_collect.py` serves it locally and opens the browser.
3. The user clicks any section or diagram node, writes comments, hits **"An Claude senden"**.
4. The script prints the annotations as TOON to stdout, writes `<name>.annotations.toon`, and exits.
5. You read the TOON, address every comment, revise the canvas, and re-serve if useful.

## When to trigger

Use this skill when a reply would otherwise be a long, structured explanation: architectures, protocols, algorithms, org/data flows, migration plans, "how does X work", comparisons with real trade-offs. Don't use it for short factual answers, code reviews, or when the user explicitly wants plain text. If in doubt and the topic has ≥3 distinct parts or an inherent structure (flow, hierarchy, states), prefer the canvas — that's exactly what it's for.

## Step 1 — Structure the explanation

Before touching HTML, outline the concept for a human reader:

- **3–7 sections**, each one idea, ordered so understanding builds up (overview → parts → interactions → trade-offs/pitfalls → summary is a good default, not a law).
- **Diagrams only when they earn their place — zero is a valid answer.** There is no minimum. Add a Mermaid diagram *only* when a picture conveys structure that prose genuinely struggles with; if a short paragraph or a list says it just as clearly, skip the diagram. A canvas that is all well-structured text is completely fine.
- **When you do add one, pick whichever Mermaid diagram type actually matches the shape of the concept — don't default to flowchart.** The template renders any valid Mermaid syntax; nothing in it favors one type. Match the type to the thing you're depicting, e.g.: `flowchart` (branching flow/architecture), `sequenceDiagram` (interactions over time between actors), `stateDiagram-v2` (lifecycles), `classDiagram` (structure/relationships between entities), `erDiagram` (data relationships), `journey` (a user's path with satisfaction), `quadrantChart` (a 2x2 trade-off), `mindmap` (a hierarchy of ideas), `timeline` (events over time), `gantt` (scheduling/overlap), `pie` (simple proportions). If the concept doesn't move or branch, a diagram usually isn't the right call at all. Keep each diagram ≤ ~12 elements; split rather than cram.
- **A Mermaid diagram is *yours* to author and revise — the reader can only comment on it, not restructure it.** For the rarer case where the point is to let the reader actually build or rearrange a node/edge structure themselves (e.g. "sketch out our service boundaries with me", "lay out your team's reporting lines"), use an **editable graph section** instead (see Step 2). It's a materially different interaction — the user drags, adds, deletes, and rewires nodes directly, and the edited structure comes back as data, not prose — so reach for it deliberately, not as a fancier default flowchart.
- Write for understanding, not completeness: short paragraphs, concrete examples, name the "why" not just the "what". Use analogies where they genuinely carry weight.
- **Keep it scannable, not condensed.** A section shouldn't read as a wall of prose. Open with one short orienting sentence, then break out enumerable content — steps, properties, options, pitfalls — into a `<ul>`/`<ol>` instead of folding it into a paragraph. Don't over-compress: a bullet still gets a full clause if it needs one, not just a keyword. Not every section needs a list — a section that's genuinely one continuous idea can stay prose; force a list only where the content is actually a set of parallel items.
- Give every section and every flowchart/state node a **stable, meaningful id** (`overview`, `token-exchange`, `gateway`) — these ids become annotation targets and come back to you in the TOON, so you must be able to recognize them later.

## Step 2 — Build the HTML

Copy `assets/template.html` and fill it in. The template already contains the full annotation UI, Mermaid loading, styling, and the submit/fallback logic — **do not rewrite those parts**. You only edit the marked regions:

- `<title>`, the `CANVAS_META` object (`doc` slug + `title`), and the header block.
- The content inside `<main>`: sections follow this exact pattern:

```html
<section class="annot" data-annot="section:token-exchange" data-label="Token Exchange">
  <h2>Token Exchange</h2>
  <p>Ein Satz Kontext: worum geht's, warum passiert das hier.</p>
  <ul>
    <li>Ein Punkt pro Zeile — parallele Dinge (Schritte, Eigenschaften, Optionen), nicht Fülltext.</li>
    <li>Volle Teilsätze statt Stichwörter, sonst wird's zu kryptisch.</li>
  </ul>
</section>
```

(`<p>`/`<ul>`/`<ol>` frei mischen — nicht jede Section braucht eine Liste, nur die mit echt paralleler Struktur.)

- Diagrams live inside a section, wrapped like this (the `pre.mermaid` content is normal Mermaid syntax):

```html
<figure class="diagram annot" data-annot="diagram:auth-flow" data-label="Auth-Flow Diagramm">
  <pre class="mermaid">
flowchart LR
  client[Client] --> gateway[API Gateway]
  gateway --> auth[Auth Service]
  </pre>
  <figcaption>Der Weg eines Requests durch die Auth-Schicht.</figcaption>
</figure>
```

**`flowchart` and `stateDiagram-v2` nodes are individually clickable** — their Mermaid ids (`gateway`, `auth`) become targets like `node:gateway`. This is a rendering detail, not a reason to prefer those types: any other Mermaid diagram type is annotated via its wrapping `figure` only (Mermaid's SVG output for `sequenceDiagram`, `classDiagram`, `erDiagram`, etc. doesn't expose the same per-element id convention), so give those figures descriptive labels — the reader can still comment on the diagram as a whole, just not on one bar/actor/slice inside it.

- An **editable graph section** looks like this instead — you author the starting nodes/edges as JSON, the reader can then add/remove/rename/rewire directly in the browser (drag from a node's edge-handle to connect, double-click to rename, select + Delete to remove):

```html
<figure class="graph-figure annot" data-annot="graph:service-map" data-label="Service Map" tabindex="0">
  <div class="graph-mount" data-graph-id="service-map"></div>
  <script type="application/json" class="graph-data">
    {"nodes":[{"id":"web","label":"Web App"},{"id":"api","label":"API"}],
     "edges":[{"from":"web","to":"api","label":""}]}
  </script>
  <figcaption>Grober Entwurf — bau die Struktur mit mir zusammen aus.</figcaption>
</figure>
```

  cytoscape.js (plus its edgehandles/dagre plugins) loads lazily from `esm.sh` only if a `.graph-mount` exists on the page, so canvases without one pay nothing for it. Node/edge ids follow the same rule as everywhere else: stable and meaningful, since they come back to you in the TOON. Use this sparingly — it changes the interaction contract for that one diagram from "comment on it" to "restructure it", so reserve it for cases where that's actually the point (see Step 1).

Theming: the template exposes `--accent` and friends as CSS custom properties at the top. Adjust the accent to fit the subject if you like; keep the rest unless the user asks for a different look (then consult the frontend-design skill).

Save the file in the working directory as `<topic-slug>-canvas.html`.

## Step 3 — Serve and collect

Launch the collector with the Bash tool's **`run_in_background: true`** option — not a trailing shell `&`. That option is what makes this automatic: the harness notifies you the moment the process exits, instead of you having to poll a log file or wait for the user to say "done".

```bash
python <skill-path>/scripts/serve_and_collect.py <topic>-canvas.html \
  --timeout 1800 > canvas-run.log 2>&1
```

(Bash tool call: `run_in_background: true`. Omit the trailing `&` — the tool backgrounds it for you.)

The script prints the URL almost immediately (flushed), well before it finishes waiting — read `canvas-run.log` right after launching to get it, and tell the user: the canvas is open at that URL, click any section or diagram node to leave comments, then press **"An Claude senden"**.

From here, don't poll and don't ask the user to tell you when they're done — just continue the conversation or wait; a task-completion notification arrives on its own the moment the process exits (submitted, timed out, or the user hit "Server beenden"). When it arrives, check the exit code before reading anything:

- **`0`** — either annotations were submitted, or the user ended the session via "Server beenden" with nothing sent. Read `<topic>-canvas.annotations.toon` — if it doesn't exist or is empty, treat this as "session ended, no feedback" rather than an error.
- **`2`** — timeout; the user didn't respond in time. Ask if they want more time or want to skip this round.
- **`3`** — bad payload; something broke in the annotation submission. Check `canvas-run.log` for the error.

The TOON itself is available in two identical places once submitted: stdout (in `canvas-run.log`, between `-----BEGIN TOON-----` / `-----END TOON-----`) and the `.annotations.toon` file — prefer the file, it's the reliable channel.

**No local browser available** (e.g. you're not on the user's machine): create the HTML as an artifact/output file instead. The template detects the missing server and its send button turns into **"Als .toon herunterladen"** — ask the user to paste the file contents back into the chat. Same TOON, different transport.

## Step 4 — Process the TOON and iterate

The format is documented in `references/toon-format.md` (read it if you need to parse anything beyond the shape below). A typical payload:

```
doc: oauth2-flow
title: OAuth2 verständlich
exported: 2026-07-31T14:22:09Z
annotations[3]{id,target,label,comment}:
  1,section:overview,Überblick,Gute Einführung
  2,node:gateway,API Gateway,"Warum sitzt Rate Limiting hier, nicht im LB?"
  3,diagram:auth-flow,Auth-Flow Diagramm,Refresh-Token-Pfad fehlt
```

Rules for processing:

- **Address every annotation explicitly**, in order, referencing the label so the user can follow ("Zum API Gateway: …").
- Questions → answer them in chat **and** judge whether the answer belongs in the canvas; usually it does — a confused reader means the document was incomplete.
- Requested changes → revise the relevant section/diagram in the HTML.
- If you changed the canvas, offer another round: bump the small version note in the header, re-run the collector, same loop. Stop when a round comes back empty or the user is satisfied.

If the canvas has an editable graph section, three more tables (`graphs`, `graph_nodes`, `graph_edges`) follow `annotations` — present only when at least one graph section exists. They carry the graph's *full current structure* at submit time, not a diff, so compare it yourself against what you originally authored to see what the user actually changed. Note the id-prefix mismatch: a whole-figure comment on the graph shows up in `annotations` as `graph:service-map` (with the prefix), while the graph tables reference the bare id `service-map` (without it). When you revise the canvas, update that section's `graph-data` JSON to match the returned structure — don't silently discard the user's edits by re-authoring from scratch.
