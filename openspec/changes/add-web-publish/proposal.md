## Why

A playmaker playbook is only as useful as it is *readable*. Today the plays live
as Obsidian-compatible markdown in `wiki/concepts/` — great for the engine and
for power users, but not a pleasant, shareable reading surface, and the only way
to "ask the playbook" is the `playmaker query` CLI.

This change adds a **read-side UI layer**: a triggered `publish` step that turns
the current vault into a readable, web-accessible site, plus an AI query box. The
UI is **not** synchronized with the vault — it is a snapshot produced on demand,
which keeps reading fast, cacheable, and fully decoupled from OpenKB's compile
cycle.

> ✅ **Spike complete (2026-06-17, see `spike.md`).** Both load-bearing bets are
> resolved: **D-A** (public-web topology) PASS — a Vercel function reached the
> public gateway end to end; **D-B** (retrieval) REVERSED from BM25 to
> **whole-playbook context** (simpler, faster, better for this corpus). Design
> decisions D-A…D-D are RESOLVED; this change is ready for `specs/` + `tasks.md`.

## What Changes

- **New** `playmaker publish`: a triggered, local build (the vault + secret live
  locally) that renders the vault to a deployable static bundle.
- **Static read site** (Python/Jinja): one readable page per play, rendering the
  *play shape* — Why callout, `Kind` + maturity badges, when/how/outcome/caveats,
  category-first tools, typed-links vs. wikilinks, sources — plus an index.
- **AI query** via a **thin serverless function** (`/api/query`, Python on
  Vercel) that sends the **whole playbook** (all plays, brief-truncated) → one
  gateway chat call with a "cite by [[key]]" prompt. No prefilter, no embeddings,
  no OpenKB, no live vault — validated by spike to match the `playmaker query`
  baseline at ~3× the speed for a ~28-play corpus (D-B). Add retrieval only above
  ~100–150 plays.
- **Public-web topology** (Vercel + git-push deploy), **password-gated** for both
  the site and the query endpoint via edge middleware. ⚠️ D-A
- The publish bundle is the deploy artifact: static HTML + `plays.json` +
  `bm25.json` + the query function + gating. The gateway secret is a Vercel env
  var, never in the bundle. The deploy repo must be **private**.

## Capabilities

### New Capabilities
- `web-publish`: the `publish` command and the snapshot artifact contract
  (HTML + `plays.json`), built locally from `wiki/` + sidecar.
- `web-query`: the thin AI query function — whole-playbook context + one gateway
  call, returning a grounded, play-citing answer.
- `web-gating-deploy`: the public-web topology — edge-middleware password gate,
  private deploy repo, git-push → Vercel, secret-as-env-var.

### Modified Capabilities
<!-- None — additive read-side layer; the engine/curation specs are untouched. -->

## Impact

- **Read-only over the vault:** reuses `wiki.parse_play` + `Sidecar`; writes
  nothing into `wiki/` or `.openkb/`. New output lives under a publish out-dir.
- **New deploy surface:** a private deploy repo + a Vercel project (static +
  one Python function + edge middleware). One JS file (the middleware) in an
  otherwise Python/Jinja change.
- **Secret reaches the cloud:** the query function calls the gateway directly, so
  the WAF `User-Agent` workaround travels with it (D-A verifies this works from
  Vercel egress).
- **Spike first:** `spike.md` validates D-A and D-B before tasks are written.
