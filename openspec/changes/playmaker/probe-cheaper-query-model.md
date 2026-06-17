# Probe ④ — Cheaper query model fitness (`gemini-2.5-flash-lite`)

Purpose: decide whether the published `/api/query` function can run on
`gemini-2.5-flash-lite` instead of `gemini-3.5-flash` to cut cost, **without**
regressing the grounding/citation quality that decision **D-D** validated
(see archived `add-web-publish/design.md`). Same shape as `spike.md`: a
hypothesis, a method, a pass/fail gate, and the decision it closes.

Throwaway eval code only — nothing lands in the package. The query function
already does the work; the model is a pure runtime knob.

## What is (and isn't) changing

The model is `GATEWAY_MODEL` env only — `playmaker/publish/api/query.py:80`:

```python
model = os.environ.get("GATEWAY_MODEL", "gemini-3.5-flash")
```

No code changes. "Experiment" = flip the env var and re-run the candidate path
`query.answer(question, load_plays())`, which already returns
`{answer, cited, play_count}`. This is an **evaluation**, not an implementation.

## Premise check (do this before trusting any saving)

`design.md` **D-C** already concluded cost is **not** the binding constraint:
~21.7k input tok/query ≈ **1–4¢ on full flash**, negligible for a single user;
the real constraints are latency + lost-in-the-middle. So quantify the actual
flash bill first — if it is sub-dollar/month, flash-lite optimizes pennies while
risking grounding. Run this probe only if the saving is real, OR purely to get
the empirical fitness answer (latency may itself be a win).

## Prerequisites (spike-learned gateway facts)

1. **Allowlist.** The virtual key is model-scoped (403 otherwise). Confirm
   `gemini-2.5-flash-lite` is on the key before any eval.
2. **Exact, case-sensitive id.** Spike learned `gemini-3.5-flash` (not
   `Gemini-…`). Confirm the real lite id against the gateway's model list — not
   the `gemini.2.5-flash-lite` (dot) typo from the original request.
3. **Reasoning vs. lean.** flash was a *reasoning* model (78 reasoning tokens to
   say "ok" → `MAX_TOKENS=8192`). flash-lite has thinking off/minimal — likely
   faster and cheaper, but D-D grounding was validated *on a reasoning model*.
   That gap is the whole risk.

## Method

1. Corpus: the **ai-swe** vault (`/Users/everest/playbooks/ai-swe`), 28 concept
   plays. Build `plays.json` via `playmaker publish` (or `wiki.list_plays`).
2. Harness: an env-swap loop around the **shipped** function —
   for `model in {gemini-3.5-flash, gemini-2.5-flash-lite}`, set `GATEWAY_MODEL`,
   call `query.answer(q, plays)` for each question; record `cited`, raw answer
   text, and wall-clock latency. Add `playmaker query <q>` as the baseline.
3. **Fabrication catch:** `answer()` silently filters `cited` to valid keys
   (`query.py:109`), so invented keys are invisible there. The scorer MUST
   re-run `_KEY_RE.findall(raw_text)` and diff against the valid key set.

## The eval set — 5 failure axes, real ai-swe keys

| # | Axis | Question | Gold keys (under `concepts/`) | Trap / distractors |
|---|------|----------|------------------------------|--------------------|
| Q1 | Vocabulary-mismatch recall | "How do I improve retrieval quality in my RAG system?" | **≥2 of:** `implement-hybrid-search`, `rerank-retrieved-documents`, `generate-hypothetical-document-embeddings` (acceptable extras: `implement-recursive-retrieval`, `compress-retrieved-context`, `use-just-in-time-retrieval`) | "quality" lexically pulls the **eval** plays `isolate-rag-components-for-evaluation`, `stress-test-rag-pipelines` — the trap that broke BM25 |
| Q2 | One central play among distractors | "My LLM-as-judge disagrees with my domain experts — how do I align it?" | `critique-shadowing` (acceptable adjacent: `use-pairwise-comparison-for-subjective-evals`, `design-binary-evaluation-criteria`, `deploy-panel-of-llms`) | the full 6-play eval cluster |
| Q3 | Safety / operational | "How do I safely execute code or tool calls an AI agent generates?" | `isolate-context-via-sandboxed-execution` (adjacent: `set-three-tier-agent-boundaries`, `design-defensive-ux`) | — |
| Q4 | **Multi-play synthesis** (reasoning-off probe) | "My agent runs out of context on long multi-step tasks — how should I manage its context?" | **core, weave ≥2 of 3:** `compact-conversation-history`, `use-just-in-time-retrieval`, `implement-agentic-memory`; **bonus:** `compress-retrieved-context` (more RAG-specific, ok to omit) | scored on *integration into the answer*, not just citing — side-by-side vs baseline read is decisive |
| Q5 | **Negative control** (clean — no adjacency) | "How should my agent handle image / multimodal inputs?" | **∅ — the corpus is entirely text-LLM / agent / RAG; nothing covers vision or multimodal. Correct = decline plainly** | none — no play is even thematically adjacent, so *any* citation here is a pure fabrication signal |

Q1–Q3 are retrieval sanity (flash already passed). **Q4 and Q5 are where
flash-lite earns or loses the swap** — the two things a non-reasoning model
degrades on: weaving multiple plays, and declining instead of confabulating +
fabricating a citation.

### Fairness check (body-confirmed 2026-06-17)

- **Q4 fair:** the 3 core plays share the "context rot / attention budget /
  long-horizon" theme and cross-link (`implement-agentic-memory` wikilinks
  `[[concepts/compact-conversation-history]]`) — they are meant to be used
  together, so weaving them is legitimate. `compress-retrieved-context` is
  RAG-chunk-specific → demoted to bonus.
- **Q5 reworked:** the original "fine-tune on my own labeled data" question was
  **rejected** — `distill-llm-outputs` literally includes *"Fine-tune the student
  model…"*, so citing it is a defensible partial match, not a fabrication. That
  ambiguity makes it a bad control. Multimodal/vision is genuinely absent with
  **zero** adjacency → clean decline test. *Optional adjacency-stress variant:*
  "how do I prevent prompt-injection attacks?" — adjacent to `design-defensive-ux`
  / `set-three-tier-agent-boundaries` / `isolate-context-via-sandboxed-execution`
  but covered by none; swap in if you want to stress fabrication-under-temptation.

## Scoring (per model × question)

Graded quality, per question Q1–Q4 — a 0–1 score:

```
Q1,Q2  quality = |cited ∩ gold| / |gold core|       # recall of the central plays
Q4     quality = (core plays integrated into the answer) / 3   # synthesis, not just citing
Q3     quality = cites the gold play (1) else 0
quality is confirmed by a side-by-side read vs `playmaker query` baseline (D-D human check)
```

Trust signals (NOT graded on a curve — see gate):

```
fabricated = _KEY_RE.findall(raw_text) − valid_keys   # invented [[keys]] — MUST be ∅
declines   = (Q5) refuses + cites nothing on the uncovered topic
latency_s  = wall clock per call                      # flash-lite may WIN here
```

> **Why `fabricated` re-scans raw text:** `answer()` silently drops invalid keys
> from `cited` (`query.py:109`), so a fabricated key is invisible unless the
> scorer re-runs `_KEY_RE.findall()` on the raw answer and diffs against `valid`.

## Pass/fail gate — viability at the 80–85% bar

Cost-leniency is intentional: graded **quality** may degrade gracefully (missing
one of three retrieval plays still answers usefully). But fabrication and
not-declining are **trust violations**, not quality dips — they cannot be averaged
into a percentage, so they stay hard floors regardless of the cost saving.

- ✅ **VIABLE** when **all** hold:
  1. **Graded quality** — `mean(Q1..Q4 lite) ≥ 0.80–0.85 × mean(Q1..Q4 flash)`
     (≈ within 80–85% of flash; flash is the practical gold here).
  2. **Hard floor — zero fabricated keys** across all 5 questions.
  3. **Hard floor — Q5 declines** (no confabulated answer to the uncovered topic).
  - Latency logged: a quality-tie + latency win is a clean upgrade, not just viable.
- ❌ **NOT VIABLE** if quality falls below ~80% of flash, OR *any* fabricated key,
  OR it answers Q5 instead of declining. Keep `gemini-3.5-flash`.

## On pass → what to change

Nothing in code. Update `DEPLOY.md` (`GATEWAY_MODEL` row) and the Vercel env var
to `gemini-2.5-flash-lite`; optionally lower `MAX_TOKENS` (no reasoning budget
needed). Note the outcome against D-D so the grounding claim stays traceable to
the model it was validated on.
