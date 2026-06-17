## Why

Knowledge about how to do something well never compounds — it stays scattered across articles, PDFs, and notes, re-read from scratch, duplicated, and quietly contradictory. **playmaker** turns a stream of sources into a living, self-maintaining **playbook** of discrete, actionable "plays." It is deployed **one instance per domain** (e.g. "How to use AI in Software Product Engineering").

Rather than build the whole LLM-wiki engine from scratch, playmaker is a **thin, non-invasive superset over [VectifyAI OpenKB](https://github.com/VectifyAI/OpenKB)** — an Apache-2.0 implementation of the Karpathy LLM-wiki pattern. OpenKB already provides ingest→compile→query→lint, cross-document enrichment, contradiction synthesis, dedup, `[[wikilinks]]`, PageIndex long-PDF handling, a pluggable LiteLLM provider, and Obsidian-compatible markdown. playmaker tracks it as an upstream dependency (inheriting its improvements) and adds only what makes it a *playbook*.

This approach was **validated by spike (2026-06-16)**: a custom `AGENTS.md` steered OpenKB's compiler into genuinely play-shaped pages (WHY-led, `Kind`, when/how/outcome/caveats, category-first tool categories) with high precision; and a second overlapping source **enriched the existing play in place** (no duplicate), accumulated provenance, and reconciled a contradiction into linked plays.

## What Changes

- **New** `playmaker` system: a self-hosted, single-user, one-instance-per-domain playbook, implemented as a superset layer over OpenKB. No multi-tenancy/auth.
- **OpenKB as the engine** (installed from source — it is *not* the `openkb` package on PyPI): provides the ingest/compile/query/lint loop, enrichment, dedup, PageIndex, watch, skill export, and the markdown-wiki store. State model is **OpenKB's** (SHA-256 hash registry + append-only `log.md`); **git-as-truth and a vector DB are explicitly dropped/deferred.**
- **Plays via a custom `AGENTS.md`**: OpenKB injects `AGENTS.md` as the system prompt for compilation, so playmaker ships an `AGENTS.md` that defines concept pages as PLAYS — leading with WHY, an auto-detected `Kind`, when-to-use/how/outcome/caveats, and **category-first tool categories** — with high-precision extraction.
- **Sidecar metadata store** (playmaker-owned, outside OpenKB's directories): because OpenKB manages page frontmatter in code, playmaker keeps human-set **maturity** and **manual typed links** (prerequisite / alternative / counters) in a sidecar keyed to pages, resilient to OpenKB renames/removes.
- **Explicit conflict flagging + a richer changelog**: OpenKB reconciles contradictions silently and writes a thin `ingest | filename` log; playmaker surfaces contested plays for human attention and produces a per-changeset summary ("+2 plays, enriched 1, linked 3").
- **A thin playmaker CLI** wrapping OpenKB operations plus play-specific curation (set maturity, assert typed link, resolve conflict) and a play-shaped query/view.

## Capabilities

### New Capabilities
- `openkb-foundation`: install/pin/configure OpenKB as the underlying engine — KB layout, the LiteLLM gateway wiring (`api_base` + `extra_headers`), version tracking, and the inherited operations playmaker relies on.
- `play-schema`: the custom `AGENTS.md` that steers OpenKB's compiler to emit play-shaped pages (WHY-led, `Kind`, when/how/outcome/caveats, category-first tool categories) with high precision.
- `play-metadata-sidecar`: the playmaker-owned store for human-set maturity and manual typed links, keyed to OpenKB pages and reconciled across renames/removes.
- `conflict-and-changelog`: explicit contradiction flagging and a human-readable per-changeset changelog layered over OpenKB's thin log.
- `playmaker-cli`: the command surface that wraps OpenKB ingest/query/lint and adds play curation + the play-shaped query/view.

### Modified Capabilities
<!-- None — greenfield project, no existing main specs. -->

## Impact

- **External dependency:** OpenKB (Apache-2.0), installed from GitHub source; brings markitdown, trafilatura, PageIndex, LiteLLM. playmaker pins a version and bumps deliberately.
- **LLM access:** via a LiteLLM-compatible gateway. Integration note from the spike: some gateways' WAFs block LiteLLM's default User-Agent — set `extra_headers: {User-Agent: …}` in `config.yaml` and supply `api_base` via `OPENAI_API_BASE` with an `openai/<model>` model id.
- **Storage:** OpenKB wiki (markdown) + OpenKB hash registry/log + playmaker sidecar file(s). No git dependency, no vector DB.
- **Deferred (future, not specced here):** a Firecrawl source fetcher, a play-tuned Skill Factory export, and a possible upstream PR adding a pluggable page-type to OpenKB.
