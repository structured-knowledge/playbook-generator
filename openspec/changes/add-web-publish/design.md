# Design — add-web-publish

Decisions for the read-side UI layer. **D-A** and **D-B** are OPEN until the
spike (`spike.md`) closes them; **D-C/D-D** are dials the spike tunes. Do not
write `tasks.md` against an OPEN decision.

## Settled decisions

- **S1 — Snapshot, not sync.** The UI is a triggered `publish` snapshot, not a
  live view. Reading never depends on a running engine; the snapshot is the
  contract between vault and site.
- **S2 — Build is local, deploy is the artifact.** The vault is private instance
  data holding a secret, so `publish` runs locally and deploys the *output*
  (static HTML + `plays.json` + `bm25.json` + function + middleware). The deploy
  repo is **private**; the gateway secret is a Vercel env var, never bundled.
- **S3 — Read-only over the vault.** Reuse `wiki.parse_play` + `Sidecar`; write
  nothing into `wiki/`/`.openkb/`. Sidecar fields become visual signal (maturity
  badge, `contested` banner, typed-links panel distinct from wikilinks).
- **S4 — Python/Jinja static gen + one Python function.** One language end to
  end; the only JS is the edge-middleware gate.
- **S5 — Gating model.** Edge middleware checks a signed cookie set by a `/login`
  page that verifies a shared password (hashed env var); gates both the site and
  `/api/query`. (Vercel native Password Protection is the paid alternative.)

## Open decisions (closed by the spike)

### D-A — Public-web topology is viable (gateway reachable from Vercel)
**Status: RESOLVED ✓ — 2026-06-17 (Probe ②a + ②b both PASS).**
Intended: a Vercel Python function calls the gateway directly (UA workaround).
**Resolution:** Confirmed end to end — a deployed Vercel function reached the
**public** gateway `https://litellm.tzetang.com/v1` and returned a 200/`ok`
(`latency_ms` 2239, cold start). Use the public gateway, NOT the LAN-only
`http://tze-strix:13305` (Vercel cannot reach it). Public-web topology holds.
**Deploy/runtime facts:** Vercel CLI 54.x needs a PEP 621 `pyproject.toml`
(`[project]` + `[tool.vercel] entrypoint`); Deployment Protection is ON by
default (account-level, separate from the S5 shared-password gate).
**Constraints captured for the query spec:**
- Model id is case-sensitive (`gemini-3.5-flash`); the virtual key is model-scoped.
- Reasoning model → set a generous `max_tokens`.
- TLS trust: use **certifi** in the function (stdlib urllib has no bundled CAs).

### D-B — Retrieval mechanism for the AI query
**Status: RESOLVED ✓ — 2026-06-17 (Probe ①). Decision REVERSED from BM25.**
**Resolution:** **Whole-playbook context, no prefilter.** BM25 top-k was tested
and FAILED as the mechanism — its recall missed the most central plays whenever
the question's vocabulary didn't match the play titles (Q1 missed hybrid-search/
rerank/HyDE; Q5 missed sandboxed-execution). Sending all 28 plays (brief-
truncated) to one gateway call recovered every miss, matched/beat the
`playmaker query` baseline, and ran ~3× faster (~10 s vs ~39 s) with no index to
build or ship. The publish artifact therefore needs only `plays.json` (no
`bm25.json`).

### D-C — Retrieval parameters + the scaling seam (dial)
**Status: RESOLVED ✓ — 2026-06-17.** v1 sends the whole playbook, bodies
truncated to ~1200 chars/play (~300 tok/play sent); generous `max_tokens`
(reasoning model). **Build for the small case and evolve.**

**Binding constraints at scale are latency + lost-in-the-middle, NOT cost**
(150k input tok ≈ ~1–4¢/query on flash — negligible for a single user). Past
~100 plays the model gets slower and *less precise* picking the relevant few from
many distractors — the exact failure their own `rerank-retrieved-documents` play
documents. So the query function MUST isolate retrieval behind a swappable seam:

```
select_plays(question, plays) -> list[Play]      # v1: return all
```

**Evolution ladder (only climb when the corpus forces it; each rung is a drop-in
swap of `select_plays`, additive to the publish artifact):**
- **Stage 1 (now, ≤~100):** return all — validated.
- **Stage 2 (~100–several hundred):** brief-routing, 2 calls — send every play's
  title+Why (~50 tok each) so the LLM picks relevant keys, then send full bodies
  of just those. Keeps whole-playbook recall, bounded context, **no embeddings**.
- **Stage 3 (large/unbounded):** embeddings (or hybrid+rerank) → top-k. Prefer
  embeddings over BM25 (BM25 recall was the v1-rejected failure mode).

Stage 2/3 are **reasoned, not spiked** — the lost-in-the-middle threshold is
empirical; see deferred **Probe ③** in `spike.md`, to run if/when plays approach
~80. v1 keeps the publish artifact at `plays.json` only.

### D-D — Answer grounding / citation (dial)
**Status: RESOLVED ✓ — 2026-06-17.** Strong. With a "use only these plays, cite
by [[key]]" prompt, gemini-3.5-flash cited accurately, ignored irrelevant plays,
and did not fabricate keys. Keep the cite-by-key instruction in the query prompt;
render the `[[key]]` citations as links back to the published play pages.

## Out of scope (v1)

- Live/auto sync with the vault (S1 is deliberate).
- Multi-user accounts (single shared password only, S5).
- Graph view, editing from the web, comments.
