# Spike: validate the web-publish bets

Purpose: close the two load-bearing decisions (`design.md` **D-A**, **D-B**, and
the dials **D-C/D-D**) **before** writing `tasks.md`. Each probe below states a
hypothesis, a method, a **pass/fail gate**, and which decision it closes. Run the
probes, fill the **Results** block, then flip the matching `design.md` decision
from OPEN → RESOLVED and copy the one-line outcome there. Tasks are written only
against RESOLVED decisions.

Throwaway code only — nothing here lands in the package. Keep it in a scratch dir
outside the repo (or a `spike/` dir that is git-ignored / deleted after).

## Order: run Probe ② first

Probe ② is the kill-switch for the whole **topology** (D-A). If the gateway can't
be reached from a Vercel function, public-web is wrong and retrieval tuning is
moot. Probe ① is the dial; only worth turning once ② passes.

---

## Probe ② — Gateway reachable from a Vercel Python function  → Decides **D-A**

**Hypothesis:** a minimal Python serverless function on Vercel can make one chat
call to the LiteLLM gateway (with the `User-Agent: curl/8.4.0` workaround) and
return the response, within function size/cold-start limits.

**Method:**
1. Hello-world Vercel Python function `/api/ping` that reads `GATEWAY_BASE` +
   `GATEWAY_KEY` from env and makes one `openai/<model>` chat call via httpx,
   sending the `User-Agent` header workaround.
2. Deploy (git push). Hit the endpoint. Observe status, latency, cold-start.

**Pass/fail gate:**
- ✅ PASS: returns a valid completion; cold start tolerable (< ~3 s); no WAF block.
- ❌ FAIL: WAF/egress blocks the call, or the deps don't fit the function limit.

**If FAIL → the plan changes:** topology falls back from public-web to LAN/
self-host (revisit the earlier topology choice), OR the gateway must allowlist
Vercel egress IPs / front via a proxy. Record which.

### Results (2026-06-17)
- Date / model / gateway: 2026-06-17 · `gemini-3.5-flash` · **public** `https://litellm.tzetang.com/v1`
- ②a local precheck (this machine → public endpoint over internet): **PASS** — 200, reply `ok`, ~2.0 s.
- WAF behavior: UA `curl/8.4.0` accepted, no block. Endpoint reachable from an
  arbitrary internet client (no IP allowlist hit for this machine).
- Gateway facts learned:
  - **Two endpoints exist:** `http://tze-strix:13305` is **LAN-only** (Vercel could
    never reach it — would have failed D-A on topology); `https://litellm.tzetang.com`
    is the **public** path. Publish/query must target the public one.
  - Model name is **case-sensitive** (`gemini-3.5-flash`, not `Gemini-...`).
  - Per-key model allowlist: the virtual key is scoped to specific models (403 otherwise).
  - **Reasoning model** — 78 reasoning tokens to answer "ok" ⇒ generous `max_tokens`.
  - **TLS:** stdlib `urllib` fails cert verify on macOS; the function must use
    **certifi** (or httpx). Patched into the spike; Vercel's Linux runtime likely
    has system CAs but certifi is the safe default.
- ②b Vercel deploy: **DONE — PASS.** Deployed `web-publish` (project
  `prj_Ws7VhHZAHtg7mzFKB2p3p5Ql0vMV`), env vars encrypted in Vercel. The function
  (cold start) called the gateway and returned
  `{"ok":true,"status":200,"latency_ms":2239,"reply":"ok","cold_start":true}` —
  Vercel egress reaches the public gateway, UA workaround survives, certifi TLS
  works on Vercel's Linux runtime.
- Deploy-tooling notes (Vercel CLI 54.x): zero-config `api/*.py` is gone — needs a
  PEP 621 `pyproject.toml` with `[project]` (uv-locked) + `[tool.vercel] entrypoint`.
  **Deployment Protection (Vercel Authentication) is ON by default** → plain fetch
  got 401; reach it with `vercel curl` (or disable protection / set a bypass).
  This is Vercel-account auth, distinct from the shared-password end-user gate (S5).
- **Outcome → D-A:** **PASS** — Vercel function reaches the public gateway end to
  end. Public-web topology confirmed. Target `https://litellm.tzetang.com/v1`.

---

## Probe ① — Cheap retrieval gives good answers  → Decides **D-B** (dials **D-C/D-D**)

**Hypothesis:** BM25-prefilter + top-k play bodies + one gateway chat call yields
answers comparable to `playmaker query` (full OpenKB retrieval), good enough that
embeddings are unnecessary for v1.

**Method (purely local — no Vercel):**
1. Point at a real playbook's `wiki/`. Build `plays.json` (reuse
   `wiki.list_plays`) + a quick BM25 index over play text.
2. For ~5 representative questions: BM25 → top-k plays → send their bodies to the
   gateway with a "answer from these plays, cite them" prompt.
3. Run the same questions through `playmaker query`. Compare side by side.

**Pass/fail gate:**
- ✅ PASS: BM25+top-k answers are on par with `playmaker query` on ≥4/5 questions,
  and cite the right plays.
- ❌ FAIL: misses relevant plays or answers materially worse.

**If FAIL → the plan changes (D-B):** escalate retrieval — (a) whole-playbook
context if the corpus is small enough, (b) embeddings/vector top-k, or (c) keep
`playmaker query` as a fat function (which reopens D-A's cold-start question).

**Dials to record (D-C / D-D):**
- **D-C:** good `k`; send brief vs. full body; token budget per call.
- **D-D:** does the model cite the passed plays correctly / stay grounded?

### Results (2026-06-17) — ran BM25 top-5 AND whole-playbook context, vs baseline
- Corpus: 28 plays (ai-swe), ~86.9k body chars ≈ **21.7k tokens total**.
- Baseline `playmaker query` (full OpenKB): excellent, ~39 s/query.
- **BM25 top-5: FAIL as the mechanism.** Generation was great and reliably ignored
  irrelevant retrieved plays, but BM25 **recall missed key plays on vocabulary
  mismatch** — Q1 "improve retrieval quality" missed hybrid-search / rerank / HyDE
  (the 3 most central plays; "quality/retrieval" lexically matched the *eval*
  plays); Q5 missed sandboxed-execution; Q2 missed critique-shadowing. ~3.5/5 on
  par, flagship question materially worse.
- **Whole-playbook context (send all 28, brief-truncated ~1200 chars each): PASS,
  beats BM25 and matches/exceeds baseline.** Recovered every play BM25 missed,
  on all 5 questions. And **~8–15 s/query — ~3× faster than the 39 s baseline**,
  with no index to build.
- **Outcome → D-B:** **BM25 FAIL → whole-playbook context PASS.** For a small
  playbook, skip the prefilter entirely; send the whole playbook. (Reverses the
  earlier "keyword prefilter" choice — exactly what the spike was for.)
- **Outcome → D-C:** whole-playbook, no prefilter, bodies truncated ~1200 chars,
  `max_tokens` generous (reasoning model). **Add retrieval only above a size
  threshold** — 28 plays ≈ 21.7k tok (~775 tok/play); whole-context stays cheap
  to ~100–150 plays, then switch. When retrieval is needed, prefer **embeddings**
  over BM25 (BM25's recall was the failure mode here).
- **Outcome → D-D:** **strong PASS.** Citations accurate in both modes; the model
  ignored irrelevant plays and did not fabricate keys. Grounding is reliable.

---

## Deferred — Probe ③ (D-C scaling): when does whole-playbook context degrade?

**Run only if/when a playbook approaches ~80 plays.** Not a v1 blocker.

**Hypothesis:** whole-playbook context holds quality until lost-in-the-middle bites
somewhere ~100–250 plays (model-dependent); brief-routing (Stage 2) restores it.

**Method:** grow/synthesize the corpus to 50/100/200 plays; run the same question
set in (a) whole-bodies, (b) brief-routing 2-call, (c) embeddings top-k; compare
answer precision + latency. **Gate:** find the play count where whole-context
answer precision drops below brief-routing → that's the Stage 1→2 switch point.

## After the spike

1. For each Results block, edit `design.md`: flip the decision OPEN → RESOLVED and
   paste the one-line outcome + any chosen params.
2. If any FAIL forced a fork, update `proposal.md` (topology or retrieval) to match.
3. Write `tasks.md` and `specs/` against the now-RESOLVED decisions only.
