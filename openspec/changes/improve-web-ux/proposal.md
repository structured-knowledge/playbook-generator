## Why

The published site (`add-web-publish`, archived) reads well at the *play page*
level, but the **home / browse and ask surfaces** don't yet pull their weight:

- **Three competing entry points** — a corner search box, an Ask box, and a flat
  A→Z list — that don't know about each other. Search and Ask look identical (a
  box + button) but do completely different things, and the user has to *know*
  the difference.
- **The list ignores the metadata it shows.** Plays carry `kind`, `maturity`,
  `tool_categories`, and `contested` — and the page renders them as badges — but
  there is no way to *filter or group* by them. The CLI already filters by
  `--kind/--tool/--maturity` and sorts maturity-first; the web throws both away
  and sorts alphabetically. This breaks past ~20 plays.
- **The Ask box is a blank page**, then a blind wait. No example questions to
  prime it; the only feedback during a 10–40s gateway call is a static
  "Asking…", which reads as broken.

This change improves the **read-side UX** so a reader can browse *and* ask from
one coherent surface. The primary-mode question was settled as **both, equally**,
which points at a single unified command bar rather than picking a side.

> **Scope is deliberately front-end-only.** Every item reads from the `plays.json`
> the existing `publish` already emits. `api/query.py`, the gateway call, and the
> edge gate are **untouched**. The Ask answer stays a single JSON response —
> token **streaming was explicitly dropped** (it crosses the function, gateway,
> and edge-gate boundaries and needs its own spike; see Out of scope).

## What Changes

- **Unify search + ask into one command bar.** One input on the index. Typing
  filters the play list live; an **"Ask the playbook: …"** action is *always
  visible* alongside the filtered results, so asking is an explicit action, not a
  hidden Enter-mode. Replaces the separate header search box and the standalone
  Ask form.
- **Faceted browse.** Render `kind` / `maturity` / `tool` as selectable facet
  chips (with live counts) over `plays.json`; clicking narrows the list. Sort the
  list **maturity-first** (port the ordering already in `cli.py:plays_cmd`),
  matching the CLI. All client-side.
- **Seeded questions.** Show a few example questions on the empty command bar,
  derived from real play titles/whys at build time so they never go stale.
- **Honest Ask feedback (not streaming).** Replace the static "Asking…" with an
  elapsed-timer + phase line ("Reading N plays… · 6s"). The response is still one
  JSON blob.
- **No-answer becomes a next step.** When the answer reports the playbook doesn't
  cover the question, surface the closest related play (if any) and a copyable
  `playmaker ingest <url>` call, instead of a dead end.

## Capabilities

### New Capabilities
<!-- None — this refines the existing read-side surfaces. -->

### Modified Capabilities
- `web-publish`: the index gains a unified command bar (search + ask entry),
  faceted browse (kind/maturity/tool chips + maturity-first sort), and seeded
  example questions. Supersedes the standalone header search box.
- `web-query`: the Ask UI gains elapsed-timer/phase feedback during the call and
  a next-step affordance for the no-answer case. The endpoint, retrieval seam,
  and gateway behavior are unchanged.

## Impact

- **Front-end only.** Changes live in `playmaker/publish/templates/` and
  `playmaker/publish/static/` (`search.js` + `ask.js` merge into the command
  bar), plus a small build-time addition in `builder.py` to emit seeded
  questions and per-facet counts into `plays.json` (additive — existing fields
  unchanged). No backend, no new dependency, no deploy-surface change.
- **No new failure modes.** Can't break `ingest`, `query`, or deploy; worst case
  is a layout bug. The Ask path's network behavior is byte-for-byte unchanged.
- **Reliability rationale:** the dropped item (streaming) was the only one with
  cross-boundary failure points; everything kept here is pure client-side work
  over data already published.
