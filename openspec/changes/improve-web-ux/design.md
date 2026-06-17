# Design — improve-web-ux

Read-side UX refinements over the `add-web-publish` snapshot. **Front-end only**;
all state reads from the `plays.json` the existing `publish` emits.

## Settled decisions

- **D1 — One command bar, not two boxes.** The header search box and the
  standalone Ask form merge into a single input on the index. Rationale: the
  primary-mode question resolved as *both, equally*, so neither browse nor ask
  should be demoted. A single bar serves both.
- **D2 — Ask is a visible action, not a hidden mode.** Typing filters the list
  live; an explicit "Ask the playbook: «query»  [Ask →]" row sits above the
  filtered results whenever the bar is non-empty. This is the key fix for the
  classic command-bar trap (*when does Enter filter vs. ask?*) — the ask path is
  always on screen, so there is nothing to guess. Enter triggers the visible Ask
  action; clicking a play navigates.
- **D3 — Facets reuse the CLI's filters verbatim.** `kind` / `maturity` / `tool`
  chips map 1:1 to `--kind/--tool/--maturity`, and the list sorts maturity-first
  — the ordering already computed in `cli.py:plays_cmd`. Port it; don't invent a
  new taxonomy. All filtering is client-side over `plays.json`.
- **D4 — Seeded questions are build-time, derived from real plays.** Emit a few
  example questions into `plays.json` at build (from play titles/whys) so the
  empty bar is primed and the examples never drift from the corpus.
- **D5 — Honest wait, not streaming.** Keep the single-JSON `/api/query`
  response. Replace the static "Asking…" with an elapsed-timer + phase line. This
  captures most of the *perceived* latency win at zero backend risk.

## Explicitly dropped

- **Token streaming of the Ask answer.** It crosses three buffering/failure
  boundaries — the gateway (`stream:true` support), the Vercel Python function
  (chunked/SSE output instead of one blob), and the edge gate (may buffer the
  body) — and forces incremental parsing of partial `[[key]]` citations. Any one
  failing degrades below today's honest spinner. If pursued later it needs its
  own spike (does the gateway stream? does the gate pass chunks?), mirroring how
  `add-web-publish` spiked its open bets before committing.

## Wireframes

### ① Landing — empty bar: browse + prime in one view
```
┌────────────────────────────────────────────────────────────┐
│ playbook · 28 plays                                          │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ ⌕  Search plays or ask a question…                     │ │  ← ONE input (D1)
│ └────────────────────────────────────────────────────────┘ │
│  [all] [procedure 9] [concept 12] [pattern 7] ·             │  ← facet chips, live counts (D3)
│        [established] [emerging] [experimental] · [⚠ 2]      │
│                                                              │
│  Ask anything ▸ "How should I review AI-written code?"       │  ← seeded questions (D4)
│                 "When is TDD worth it with a coding agent?"  │
│                                                              │
│  ── plays · by maturity ───────────────────────────────────  │  ← maturity-first sort (D3)
│  • Review AI-generated code        [procedure][established]  │
│    why: trust, but verify — agents drift on intent           │
│  • Sandboxed execution             [pattern][experimental]   │
│    why: run untrusted agent output without blast radius      │
│  • …                                                         │
└────────────────────────────────────────────────────────────┘
```

### ② Typing "review" — filter and ask coexist, no hidden mode (D2)
```
┌────────────────────────────────────────────────────────────┐
│ ┌────────────────────────────────────────────────────────┐ │
│ │ ⌕  review▍                                             │ │
│ └────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ ↵  Ask the playbook: "review"                  [Ask →] │ │  ← always visible
│ └────────────────────────────────────────────────────────┘ │
│  matching plays · 3                                          │
│  • Review AI-generated code        [procedure][established]  │
│  • Code-review checklists          [pattern][emerging]       │
│  • Adversarial review of specs     [procedure][emerging]     │
└────────────────────────────────────────────────────────────┘
```

### ③ Facet active — chip filters the list (browse path)
```
┌────────────────────────────────────────────────────────────┐
│ ┌────────────────────────────────────────────────────────┐ │
│ │ ⌕  Search plays or ask a question…                     │ │
│ └────────────────────────────────────────────────────────┘ │
│  [all] [procedure 9] ▸[concept 12]◂ [pattern 7] ·           │  ← "concept" selected
│        [established] [emerging] [experimental] · [⚠ 2]      │
│  concept · 12 plays                                          │
│  • Rerank retrieved documents      [concept][emerging]       │
│  • Context windows & lost-in-middle[concept][established]     │
│  • …                                                         │
└────────────────────────────────────────────────────────────┘
```

### ④ Ask in progress — honest elapsed timer + phase (NOT streaming, D5)
```
┌────────────────────────────────────────────────────────────┐
│ ┌────────────────────────────────────────────────────────┐ │
│ │ ⌕  how should I review AI-written code?                │ │
│ └────────────────────────────────────────────────────────┘ │
│  ◂ back to plays                                             │
│ ┌────────────────────────────────────────────────────────┐ │
│ │  ◌ Reading 28 plays… · 6s                              │ │  ← timer ticks; one
│ └────────────────────────────────────────────────────────┘ │    JSON response still
└────────────────────────────────────────────────────────────┘
```

### ⑤ Ask answer — rendered, citations linked (unchanged from today)
```
┌────────────────────────────────────────────────────────────┐
│  ◂ back to plays                                             │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Run the agent in a sandbox first, then review the diff │ │
│ │ as adversarial input — assume intent drift. Gate merge │ │
│ │ on tests you wrote, not the agent's [[sandboxed-exec]] │ │
│ │ [[review-ai-generated-code]].                          │ │
│ │ ───────────────────────────────────────────────────── │ │
│ │ Cited: Sandboxed execution · Review AI-generated code  │ │  ← links to play pages
│ └────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### ⑥ No-answer — honest "not covered" becomes a next step
```
┌────────────────────────────────────────────────────────────┐
│ ┌────────────────────────────────────────────────────────┐ │
│ │ The playbook doesn't cover "kubernetes autoscaling".   │ │
│ │ Closest topic ▸ Sandboxed execution                    │ │
│ │ ┌──────────────────────────────────────────────────┐  │ │
│ │ │ This needs a source:                             │  │ │
│ │ │   playmaker ingest <url>                  [copy] │  │ │
│ │ └──────────────────────────────────────────────────┘  │ │
│ └────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```
Cheapest "closest topic": the function already returns `cited`/empty; when empty,
the client may show the first play whose facets match the query tokens, or omit
the suggestion entirely and keep only the `ingest` CTA. No backend change required
for the CTA; a closest-topic hint is optional polish.

### ⑦ Mobile — facets collapse to a sheet, bar stays primary
```
┌─────────────────────────────┐
│ playbook · 28 plays         │
│ ┌─────────────────────────┐ │
│ │ ⌕ Search or ask…        │ │
│ └─────────────────────────┘ │
│ [ Filters ▾ ]   by maturity │  ← chips behind a sheet
│                             │
│ Ask ▸ "How should I review  │
│        AI-written code?"    │
│ ─────────────────────────── │
│ • Review AI-generated code  │
│   [procedure][established]  │
│ • Sandboxed execution       │
│   [pattern][experimental]   │
└─────────────────────────────┘
```

## Open threads (not blocking)

- **Mobile facet density.** With many tool categories the chip row gets tall; a
  collapsible "Filters ▾" sheet (⑦) handles narrow screens.
- **Closest-topic source for ⑥.** Optional; the `ingest` CTA stands alone if no
  cheap closest-topic signal is available client-side.

## Out of scope

- Token streaming of the answer (dropped above; future, spiked separately).
- Anything touching `api/query.py`, the gateway call, retrieval, or the edge gate.
- The v1 out-of-scope set still holds: graph view, web editing, comments, live
  sync, multi-user.
