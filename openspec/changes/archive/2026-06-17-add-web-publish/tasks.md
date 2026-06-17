# Tasks — add-web-publish

Scope: **Stage 1, small playbook** (whole-playbook context, validated by spike).
The `select_plays` seam keeps Stage 2/3 a future drop-in (design.md D-C).

## 1. Publish command & snapshot artifact

- [x] 1.1 Add `playmaker publish [--out DIR]` (CLI + `playmaker/publish/` module) that loads plays via `wiki.list_plays` + the sidecar, read-only over the vault
- [x] 1.2 Emit `plays.json`: per play — key, title, why, kind, maturity, body, tool_categories, wikilinks, typed_links, sources (the snapshot contract)
- [x] 1.3 Render static HTML via packaged Jinja templates: one page per play + an index/listing page — _wikilinks rewritten to page links / non-play targets flattened; Tools+Related rendered structured (not duplicated from body)_
- [x] 1.4 Build a client-side search index over `plays.json` (instant, no backend call) — _static/search.js, lazy-loads plays.json_

## 2. Readable play pages

- [x] 2.1 Play-page template: Why callout, `Kind` + maturity badges, When/How/Outcome/Caveats body, category-first Tools
- [x] 2.2 Related panel: typed links (prerequisite/alternative/counters) labeled and distinct from automatic `[[wikilinks]]`; resolve both to play pages
- [x] 2.3 Sidecar signals: contested banner, maturity badge, sources + last-updated — _added `updated` (file mtime) to plays.json + play footer_
- [x] 2.4 Readability pass: serif prose reading column (~40rem measure), tuned type scale, dark mode, mobile layout

## 3. AI query function

- [x] 3.1 `/api/query` serverless function (Python, stdlib urllib + certifi) → public gateway with the `User-Agent` workaround + generous `max_tokens` — _validated live: 28 plays → cited hybrid-search/rerank/HyDE, matching the spike_
- [x] 3.2 `select_plays(question, plays)` seam — v1 returns all plays (whole-playbook, bodies truncated ~1200 chars)
- [x] 3.3 Prompt: "use only these plays, cite by `[[key]]`"; return answer + cited keys (validated against real keys); ask.js renders `[[key]]` citations as links to play pages
- [x] 3.4 Gateway key from a deployment env var (`GATEWAY_KEY`); never bundled
- [x] 3.5 Query UI: ask box on the index posting to `/api/query`, rendering the grounded answer + cited links (minimal client-side markdown, no dep)

## 4. Gating & deploy

- [x] 4.1 Edge middleware: signed-cookie (HMAC) gate over the site + `/api/query`; `/login` checks the shared `GATE_PASSWORD` — _`middleware.js` + `login.html`, valid JS; static left open for login styling; live-verify at 5.1_
- [x] 4.2 Local build → git-push deploy to a **private** repo; private-repo requirement documented — _`DEPLOY.md` runbook_
- [x] 4.3 Host project config: `vercel.json` (`maxDuration: 60` for the slow query) + `requirements.txt` (certifi) + documented env vars — _api/query.py as a serverless function (handler), not the app entrypoint; confirm routing at 5.1_
- [x] 4.4 Deployment Protection vs custom gate — **chose the custom shared-password gate** (works for non-Vercel invitees + gates the API); disable native Vercel Auth; rationale in `DEPLOY.md`

## 5. Validate & document

- [x] 5.1 End-to-end on a real instance — _LIVE at https://ai-swe-site.vercel.app: GET / → 307 /login.html, API 401 unauthed, password → cookie, authed query → 200 cited answer (play_count 28). Fixes found & backported: `framework:null` in vercel.json; login served at `/login.html`. Native Vercel protection disabled so the custom gate is the only gate._
- [x] 5.2 Runbook `DEPLOY.md` — private repo, env vars, 4.4 protection decision, framework:null + login.html notes, Stage-1 scope + `select_plays` ladder (deferred Probe ③)
