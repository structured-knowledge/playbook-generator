# Tasks — improve-web-ux

Scope: **front-end only**, over the `plays.json` the existing `publish` emits.
Streaming is out (design.md "Explicitly dropped"). No backend, no new dependency.

## 1. Unified command bar (search + ask)

- [x] 1.1 Replace the header search box and the standalone Ask form with one command bar on the index (base.html + index.html)
- [x] 1.2 Typing filters the play list live (port the scoring from `static/search.js`); the default list shows when the bar is empty
- [x] 1.3 Render an always-visible "Ask the playbook: «query» [Ask →]" row above the filtered results whenever the bar is non-empty (design.md D2); Enter triggers Ask, clicking a play navigates
- [x] 1.4 Merge `search.js` + `ask.js` into the command-bar controller; keep the `[[key]]→link` rewrite and minimal markdown renderer

## 2. Faceted browse

- [x] 2.1 Emit per-facet counts (kind/maturity/tool) into `plays.json` at build (`builder.py`, additive — existing fields unchanged)
- [x] 2.2 Render kind/maturity/tool facet chips with live counts; clicking narrows the list (client-side, combinable with the text filter)
- [x] 2.3 Sort the list maturity-first, porting the ordering from `cli.py:plays_cmd`; show the active facet + result count
- [x] 2.4 Mobile: collapse facets into a "Filters ▾" sheet (design.md ⑦)

## 3. Seeded questions

- [x] 3.1 Derive a few example questions at build time from play titles/whys; emit into `plays.json`
- [x] 3.2 Show them on the empty command bar; clicking one fills the bar and runs Ask

## 4. Honest Ask feedback (no streaming)

- [x] 4.1 Replace the static "Asking…" with an elapsed-timer + phase line ("Reading N plays… · 6s"); response stays a single JSON blob
- [x] 4.2 No-answer affordance: when the answer is "not covered" / `cited` is empty, show the copyable `playmaker ingest <url>` CTA (+ optional closest-topic hint)

## 5. Validate & document

- [x] 5.1 Rebuild a real instance with `playmaker publish` and verify: facet filtering, text filter, Ask action, seeded questions, timer, no-answer CTA, mobile layout
- [x] 5.2 Confirm the Ask network path is byte-for-byte unchanged (same POST to `/api/query`, same JSON response) — no backend/deploy change
