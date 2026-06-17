## Context

playmaker is a self-hosted, single-user playbook, one instance per domain. After evaluating a from-scratch build, we found [VectifyAI OpenKB](https://github.com/VectifyAI/OpenKB) already implements ~80% of the LLM-wiki plumbing we'd specced (Python, LiteLLM, markitdown, trafilatura, PageIndex, no vector DB, ingest/query/lint, cross-doc enrichment, contradiction synthesis, `[[wikilinks]]`, Obsidian-compatible, Apache-2.0). The decision is therefore to build playmaker as a **non-invasive superset over OpenKB**, tracked as an upstream dependency.

A code review established the hard boundary: OpenKB's page ontology (`summaries/concepts/entities`) and its frontmatter handling are hardwired in Python; its compiler prompts are concept/entity-shaped; and `AGENTS.md` is injected as the **system prompt** across compilation. A spike (2026-06-16) then **validated** that a custom `AGENTS.md` reshapes output into plays, and that a second overlapping source enriches in place without duplication. This design encodes that validated approach.

## Goals / Non-Goals

**Goals:**
- Inherit OpenKB's ingest/compile/query/lint/enrich/dedup engine and bump it for free improvements.
- Make compiled pages play-shaped (WHY-led, when/how/outcome/caveats, category-first tools) via configuration only — no OpenKB code changes.
- Own the playbook-specific concerns OpenKB lacks: human-set maturity, manual typed links, explicit conflict flagging, a richer changelog.
- Keep the layer non-invasive so upstream tracking stays clean.

**Non-Goals (v1):**
- Forking OpenKB or changing its compiler/ontology.
- git-as-truth, and an embeddings/vector DB (use OpenKB's state model + PageIndex).
- Multi-tenancy/auth, multi-page crawling, a rich web UI (Obsidian is the free browse UI).
- A Firecrawl fetcher, a play-tuned skill export, and an upstream page-type PR (all deferred).

## Decisions

### D1 — OpenKB as an upstream dependency (superset, not fork)
Install OpenKB from source, pin a version, and build playmaker around it. **Why:** the reusable plumbing is OpenKB's strength; the parts playmaker needs differently (play ontology, maturity, typed links) can be added *around* it without touching its core, preserving upstream tracking. *Alternatives:* fork-and-bend (rejected — fights its hardwired ontology + non-git state, the rewrite hits its core) and build-fresh (rejected — re-implements ~80% that already works).

### D2 — Plays via a custom `AGENTS.md` (concept pages = plays)
Ship an `AGENTS.md` that redefines concept pages as PLAYS. OpenKB injects it as the compilation **system prompt**, so it steers summary, concepts-plan, and every concept-page call. **Validated:** the spike produced WHY-led pages with `Kind`, when/how/outcome/caveats, and category-first tool categories, and skipped non-actionable content (high precision). *Trade-off:* pages still physically live in `wiki/concepts/` and are internally "concepts" — cosmetic naming only.

### D3 — Sidecar metadata store for maturity + typed links
OpenKB manages frontmatter in code and forbids LLM-authored frontmatter, so playmaker keeps a **sidecar store** (e.g. `.playmaker/plays-meta.*`, outside OpenKB's dirs) for human-set `maturity` and manual typed links (`prerequisite`/`alternative`/`counters`), keyed by page path. Prose-shaped fields (`Kind`, tool categories) live in the page body, which the spike showed works well. **Why:** non-invasive, survives OpenKB version bumps. *Risk handled in D5/tasks:* reconciliation when OpenKB renames/removes a page.

### D4 — Adopt OpenKB's state model; drop git-as-truth
Use OpenKB's SHA-256 hash registry (source-level dedup) + append-only `log.md`. **Why:** consistent with not forking the state layer; the spike confirmed enrichment/dedup work on it. *Note:* undo is OpenKB's `remove`/`recompile`, not `git revert` — accepted trade-off (weaker undo, far simpler).

### D5 — Conflict flagging + richer changelog as the playmaker layer
The spike showed OpenKB **reconciles** contradictions into coherent, cross-linked plays (good) but does **not** flag them for a human, and its `log.md` is just `ingest | filename`. playmaker adds: detection/surfacing of contested plays, and a per-changeset summary ("+N plays, enriched M, linked K") derived from compile results. **Why:** the human-in-the-loop curation playmaker promises needs visibility OpenKB doesn't provide.

### D6 — LLM via a LiteLLM gateway, with explicit integration config
Route through a LiteLLM-compatible gateway using `model: openai/<name>`, `api_base` via `OPENAI_API_BASE`, key via `LLM_API_KEY`. **Spike gotcha encoded:** the gateway WAF blocked LiteLLM's default User-Agent → set `extra_headers: {User-Agent: …}` in `config.yaml` (OpenKB's compiler forwards `extra_headers` to LiteLLM). Reasoning models also need an adequate `max_tokens` budget (reasoning tokens consume it).

### D7 — Defer Firecrawl, play-skill export, upstream page-type PR
Use OpenKB's built-in trafilatura/markitdown ingest and its Skill Factory as-is for v1. Revisit a Firecrawl fetcher (JS-heavy pages), a play-tuned skill export, and an upstream pluggable-page-type contribution later.

## Risks / Trade-offs

- **Upstream coupling / version drift** (OpenKB changes break the layer) → pin a version, keep the layer non-invasive (config + sidecar + wrapper only), bump deliberately with a smoke test.
- **Concept-page naming/ontology mismatch** (pages are "concepts" not "plays" under the hood) → cosmetic; the body shape is what matters and is validated.
- **Recall misses** (high precision can drop borderline practices — observed with the incident-postmortem case) → tune `AGENTS.md`; accept precision bias for a clean playbook.
- **Conflict reconciliation may blur nuance** (LLM merges viewpoints) → playmaker conflict-flagging surfaces it; git-free undo means rely on `remove`/`recompile` + the changelog.
- **Sidecar ↔ page key drift** (OpenKB renames/removes a page) → reconcile sidecar entries against current pages on each operation; orphan/repair rather than lose metadata.

## Migration Plan

Greenfield. Deploy = init an OpenKB KB, drop in playmaker's `AGENTS.md` + `config.yaml` (model/api_base/extra_headers) + `.env`, initialize the sidecar, and run via the playmaker CLI. Rollback of a bad ingest is OpenKB `remove`; the wiki remains a valid Obsidian-browsable playbook on its own.

## Open Questions

- Sidecar format (single JSON vs per-play YAML) and exact page-key strategy.
- How aggressively `AGENTS.md` should push recall vs precision, and where related-links should consistently live.
- Whether/when to introduce explicit conflict flagging via `lint` vs at ingest.
- OpenKB version pin and upgrade cadence.
