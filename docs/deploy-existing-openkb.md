# Agent runbook — publish & deploy a pre-generated OpenKB to the web

**Audience:** an AI agent (or operator) with shell access, asked to take an
**already-generated OpenKB wiki** and put it online as a readable site with the
grounded **Ask** (`/api/query`) function intact.

**What this does NOT require:** running OpenKB, re-ingesting sources, or any
play-shaped authoring. `playmaker publish` is **read-only** over the wiki files,
and the query function is generic over concept pages — playmaker's play
metadata (kind / maturity / tools) is optional and simply renders empty when
absent. See [precision-recall.md](precision-recall.md) for the play shape; none
of it is needed here.

**End state:** a Vercel deployment, password-gated, that serves the pages +
`plays.json` and answers questions via `/api/query`.

---

## 0. Preconditions (verify before starting)

Confirm all of these. Stop and ask the human if any is missing.

- [ ] **The KB exists on disk** with OpenKB's standard layout: a `<kb-root>/`
      containing **`.openkb/`** and **`wiki/concepts/*.md`**. The pages MUST be
      under `wiki/concepts/` — that is the only directory `playmaker` reads as
      pages (`paths.PLAYS_DIR = "concepts"`). If this OpenKB used a different
      concept-dir name, publish will find zero pages.
- [ ] **`playmaker` is installed** (`playmaker --version`). The `openkb` engine
      does **not** need to be installed just to publish.
- [ ] **Secrets are available** (the agent cannot invent these):
      - `GATEWAY_KEY` — an LLM gateway key the human provides.
      - `GATE_PASSWORD` — a site password the human chooses.
      - `GATEWAY_BASE`, `GATEWAY_MODEL` have sane defaults (below).
      - `GATE_SECRET` — the agent generates this.
- [ ] **`vercel` CLI is installed and logged in** (`vercel whoami`).

---

## 1. Locate & validate the KB

```bash
KB=/path/to/kb-root          # contains .openkb/ and wiki/concepts/
ls "$KB/.openkb" >/dev/null && echo "openkb marker ok"
ls "$KB/wiki/concepts/"*.md | wc -l    # must be > 0
```

If the page count is 0, do not proceed — the wiki is empty or pages live
elsewhere. Surface this to the human.

## 2. Publish the bundle

```bash
OUT="$KB/site"
playmaker publish --kb-dir "$KB" --out "$OUT"
# -> "Published N plays -> .../site"
```

This writes a self-contained deployable bundle: one HTML page per concept,
`data/plays.json`, the `/api/query` function, the password gate
(`middleware.js` + `login.html`), and `vercel.json` / `requirements.txt`.

## 3. Verify the bundle locally (before touching Vercel)

```bash
# a) plays.json has records
python3 -c "import json;d=json.load(open('$OUT/data/plays.json'));print('pages:',len(d['plays']))"

# b) the index rendered the command-bar UI
grep -o 'id="command-bar"' "$OUT/index.html" && echo "ui ok"

# c) (optional) eyeball it — the gate is a Vercel edge fn, so a local serve is UNGATED
python3 -m http.server -d "$OUT" 8765    # open http://localhost:8765, then Ctrl-C
```

Local serve shows **browse / search / facets**, but **Ask will not answer**
(`/api/query` is a Vercel function and the gateway secret isn't present) — that
is expected; it degrades to a friendly "could not reach the endpoint" note.

> **Expectations for a plain OpenKB wiki:** concept pages usually carry no
> `**Kind:**` / maturity / `## Tools`, so kind/maturity/tool **facet chips will
> be empty or absent** and list items show titles only. Text search, ordering,
> seeded example questions (derived from titles), and Ask all still work.

## 4. Deploy to Vercel

### 4a. Link the project (first time only)

```bash
vercel link --yes --cwd "$OUT" --project <project-name>
```

### 4b. Set the five env vars (production)

The agent has `GATEWAY_*` defaults + can generate `GATE_SECRET`; it needs
`GATEWAY_KEY` and `GATE_PASSWORD` from the human.

```bash
cd "$OUT"
printf '%s' "$GATEWAY_KEY"               | vercel env add GATEWAY_KEY   production
printf 'https://your-gateway.example/v1' | vercel env add GATEWAY_BASE  production   # MUST include scheme + /v1
printf 'gemini-3.1-flash-lite'           | vercel env add GATEWAY_MODEL production
printf '%s' "$GATE_PASSWORD"             | vercel env add GATE_PASSWORD production
printf '%s' "$(openssl rand -hex 32)"    | vercel env add GATE_SECRET   production
vercel env ls production    # confirm all five are present
```

### 4c. Deploy

```bash
vercel deploy --prod --cwd "$OUT"
```

> **Gotcha — set env vars BEFORE deploying, and redeploy after any change.**
> Env var edits do **not** apply to existing deployments. A deploy with
> `GATE_SECRET` unset makes the edge gate crash (empty HMAC key) and the whole
> site returns **`500 MIDDLEWARE_INVOCATION_FAILED`** — it fails *closed* (no
> content leaks) but is unusable until you set the vars and redeploy.

## 5. Disable Vercel's built-in protection (human step)

The agent **cannot** toggle this. Tell the human:

> Vercel dashboard → the project → **Settings → Deployment Protection →
> Vercel Authentication = Disabled.**

Otherwise the site is double-gated and password-gate invitees without Vercel
accounts can't get in. The bundle's own gate already covers `/api/query` for
cost control.

## 6. Verify live

```bash
U=https://<project>.vercel.app
curl -sI "$U/"          | head -1           # expect 307 -> /login.html (NOT 500)
curl -sI "$U/login.html"| head -1           # expect 200
# static assets bypass the gate — handy to confirm the right bundle is live:
curl -sI "$U/static/command-bar.js" | head -1   # expect 200

# full round-trip: login -> cookie -> authed page -> Ask
curl -s -c /tmp/c.txt -X POST --data "password=$GATE_PASSWORD" "$U/login.html" -o /dev/null
curl -s -b /tmp/c.txt "$U/" | grep -o 'id="command-bar"' && echo "authed page ok"
curl -s -b /tmp/c.txt -X POST -H 'Content-Type: application/json' \
     --data '{"question":"<a question your corpus covers>"}' "$U/api/query" | head -c 300
```

Success = `307` on `/`, `200` on login, and a JSON answer with `cited` keys
from `/api/query`.

---

## Failure modes (quick reference)

| Symptom | Cause | Fix |
|---|---|---|
| `Published 0 plays` | pages not in `wiki/concepts/` | point `--kb-dir` at the true KB root, or the wiki uses a non-standard dir |
| `500 MIDDLEWARE_INVOCATION_FAILED` everywhere | `GATE_SECRET`/`GATE_PASSWORD` unset | set the 5 env vars, `vercel deploy --prod` again |
| `/api/query` → `500` / gateway error | `GATEWAY_*` wrong (missing scheme, bad key, wrong model id) | `GATEWAY_BASE` needs `https://…/v1`; verify key/model |
| Login always rejected | `GATE_PASSWORD` unset/mismatched | (re)set it, redeploy |
| Invitees blocked despite correct password | Vercel Deployment Protection still on | disable it (step 5) |
| Ask is slow / costly on a big corpus | the function sends the **whole corpus** per query | fine <~100 pages; swap `select_plays` for retrieval beyond that |

## Updating later

`playmaker publish` overwrites `$OUT` but preserves `$OUT/.vercel/`, so the
update loop is just:

```bash
playmaker publish --kb-dir "$KB" --out "$OUT" && cd "$OUT" && vercel deploy --prod
```

> **Note on CLI deploys:** a CLI-only project has no Git connection, so
> `vercel deploy` (even without `--prod`) targets **production** directly — there
> is no preview stage. Connect the project to a Git repo if you want preview URLs
> per push.
