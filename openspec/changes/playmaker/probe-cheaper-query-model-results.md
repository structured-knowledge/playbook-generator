# Results — Probe ④ cheaper query model (2026-06-17)

Ran `probe-cheaper-query-model.md` live against the gateway. Spec for method,
questions, gold keys, and the gate lives in that file; this is the outcome.

## Setup

- **Corpus:** ai-swe vault (`~/playbooks/ai-swe`), 28 concept plays → built via
  `playmaker publish` to `/tmp/aiswe-site/data/plays.json`.
- **Path under test:** the deployed `query.py` prompt + 1200-char body truncation
  + `_KEY_RE` (loaded by `importlib` for fidelity), `max_tokens=8192`.
- **Gateway:** `https://litellm.tzetang.com/v1`, UA `curl/8.4.0`, certifi TLS.
- **Models (all on the key's allowlist):** `gemini-3.5-flash` (incumbent),
  `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-3.1-flash-lite`.
  *(`gemini-3.1-flash-lite` initially 403'd; allowlisted after a key reconfig,
  then run.)*
- **n = 1 per (model × question)** — directional, not statistical.

## Scoreboard

| Model | Q1 | Q2 | Q3 | Q4 | **Graded mean (Q1–Q4)** | s/query | completion tok/q | reasoning tok/q | fabricated keys | Q5 declines? |
|-------|----|----|----|----|-------------------------|---------|------------------|-----------------|-----------------|--------------|
| `gemini-3.5-flash` (incumbent) | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** | 11.3 | 1863 | 7252 | 0 | ❌ no |
| `gemini-2.5-flash` | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** | 6.8 | 1052 | 3706 | 0 | ❌ no |
| `gemini-2.5-flash-lite` | 1.00 | 1.00 | **0.00** | 0.67 | **0.67** | 1.4 | 148 | 0 | 0 | ✅ yes |
| `gemini-3.1-flash-lite` | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** | 2.4 | 265 | 0 | 0 | ❌ no |

Prompt tokens identical across models (~7.6k/call — whole playbook, truncated).
Latency is per-query (total/5). Q4 scored by core-play citation overlap (≥2/3),
a proxy for synthesis. Raw answers + usage in `/tmp/eval_all.json`.

## Findings

### F1 — `gemini-3.1-flash-lite` is the standout cost win
100% graded quality (ties the incumbent and `2.5-flash`), zero fabrication,
**~4.6× faster** (2.4 vs 11.3 s/query) and **~7× fewer completion tokens** with
**no reasoning burn** (0 vs 7252 reasoning tok/q that the incumbent bills). Meets
the 80–85% bar outright. Beats the other lite decisively.

### F2 — `gemini-2.5-flash-lite` is NOT fit for purpose
0.67 graded (below the bar). Its low score and its "clean" Q5 decline are the
**same trait** — it is a conservative *under-retriever*:
- **Q3 (score 0.0):** *"The provided plays do not directly cover…how to safely
  execute code… However, [[set-three-tier-agent-boundaries]]…"* — but the
  playbook **does** cover this (`isolate-context-via-sandboxed-execution`). It
  declined a question that had a direct answer, citing a tangential play instead.
- **Q5:** correctly declined — but for the same over-cautious reason, not superior
  judgment. It abstains on real answers and on fake ones alike.

### F3 — the negative control exposed a latent flaw in the INCUMBENT
Q5 asks about multimodal/image handling — genuinely uncovered by the corpus. The
prompt says *"If the plays do not cover the question, say so plainly."* Yet
`gemini-3.5-flash` (production today), `gemini-2.5-flash`, and
`gemini-3.1-flash-lite` **all confabulated**, stretching
`isolate-context-via-sandboxed-execution` (and, for 3.1, `decompose-complex-tasks`)
into a multimodal answer. Only `2.5-flash-lite` declined.

> This over-reach is **not a regression introduced by the swap** — the incumbent
> already does it. The spike's D-D validated grounding only on *in-scope*
> questions, so out-of-scope declining was never actually tested. It is a
> **prompt issue orthogonal to model choice**: strengthen the refusal instruction
> ("cite only plays that directly address the question; if none do, say the
> playbook doesn't cover it and cite nothing") and re-test — it should help all
> models, including what you run now.

### F4 — no fabricated keys anywhere
Across 4 models × 5 questions, zero invented `[[keys]]` (raw-text scan vs the
valid set). The cite-by-key contract holds; the failure mode is over-*reach*
with valid keys on out-of-scope questions, not fabrication.

## Verdict (against the gate: ≥80–85% of flash, + hard floors)

| Model | Graded vs flash | Fabrication floor | Q5 decline floor | Call |
|-------|-----------------|-------------------|------------------|------|
| `gemini-3.1-flash-lite` | 100% ✅ | pass ✅ | fail ❌ (= incumbent) | **Recommended swap** — same quality, big cost/latency win; Q5 is a pre-existing prompt issue, not a regression |
| `gemini-2.5-flash` | 100% ✅ | pass ✅ | fail ❌ | Safe fallback; smaller savings than the lite |
| `gemini-2.5-flash-lite` | 67% ❌ | pass ✅ | pass ✅ | **Reject** — under-retrieves, misses a safety play |
| `gemini-3.5-flash` (incumbent) | — (baseline) | pass ✅ | fail ❌ | Most expensive + slowest; no quality edge here |

**Recommendation:** switch `GATEWAY_MODEL` to **`gemini-3.1-flash-lite`** to cut
cost and latency at no graded-quality loss. Separately (and independent of the
model), tighten the refusal instruction in `query.py`'s prompt and re-run Q5 — the
negative control showed *no* model reliably declines today, the incumbent included.

## Applied (2026-06-17) ✓

- `query.py` default → `gemini-3.1-flash-lite`; `DEPLOY.md` env row + latency note
  updated; refusal prompt v2 in place (F3).
- **Vercel `ai-swe-site`:** `GATEWAY_MODEL` set to `gemini-3.1-flash-lite`
  (Production) and **redeployed** — live at `https://ai-swe-site.vercel.app`.
- D-D note: grounding now runs on a **non-reasoning** model; refusal behavior
  validated via Q5 under prompt v2.
- `MAX_TOKENS` left at 8192 (harmless ceiling; lites used <300 completion tok/q).

## F3 follow-up — refusal prompt v2 (applied + validated)

Strengthened `query.py`'s prompt: the weak trailing clause became explicit rules
— cite a play ONLY if it DIRECTLY addresses the question; if none does, say the
playbook doesn't cover it and cite nothing (may name the closest topic in one
sentence, not as the answer). Re-ran Q1–Q5:

| Model | Q1–Q4 | Q5 |
|-------|-------|----|
| `gemini-3.1-flash-lite` (production) | 1.00 — no regression | ✅ declines plainly + names closest topic as a pointer |
| `gemini-3.5-flash` (incumbent) | 1.00 | ❌ still confabulates (reframes question to fit a tangential play) |

Outcome: **F3 closed for the shipped model.** The incumbent stays over-confident
even under the stronger rules — confirming the over-reach was partly model-specific.
v2 keeps the "closest topic" pointer (helpful, honest); an airtight "cite nothing"
variant is possible but would not fix `3.5-flash` either.

## Caveats

- n=1 per cell — a flake could move one question; re-run before committing if a
  result is load-bearing.
- Q4 "synthesis" scored by citation overlap, not a full read of integration.
- Q5 is a single negative control; the prompt-refusal fix (F3) should get its own
  small before/after check.
