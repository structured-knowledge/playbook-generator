# Deploying this playbook snapshot

This directory is a **self-contained, deployable bundle** produced by
`playmaker publish`: static play pages + `data/plays.json` + the `/api/query`
function + a password gate. Build it **locally** (where your vault and gateway
secret live) and deploy the *output* — the host never sees your vault.

## 1. Push to a PRIVATE repo

The rendered pages and `data/plays.json` **are your playbook content**. The
deploy repo must be **private**, or the password gate is moot.

```bash
git init && git add -A && git commit -m "publish"
git remote add origin git@github.com:<you>/<playbook>-site.git   # PRIVATE
git push -u origin main
```

Then import the repo in Vercel (git integration auto-deploys on push).

## 2. Set environment variables in the Vercel project

| Var | What |
|-----|------|
| `GATEWAY_BASE` | `https://litellm.tzetang.com/v1` (the **public** gateway) |
| `GATEWAY_KEY` | the LiteLLM virtual key (`sk-…`) |
| `GATEWAY_MODEL` | `gemini-3.1-flash-lite` (lowercase, case-sensitive) |
| `GATE_PASSWORD` | the shared password users type at `/login` |
| `GATE_SECRET` | a random string that signs the session cookie |

None of these live in the bundle — they are host env vars only.

## 3. The access gate (task 4.4 decision)

This bundle ships a **custom edge-middleware shared-password gate**
(`middleware.js` + `/login`) so you can share one password with people who do
**not** have Vercel accounts, and so it also gates `/api/query` (cost control).

> **Turn OFF Vercel's built-in Deployment Protection** for this project
> (Settings → Deployment Protection → Vercel Authentication = Disabled).
> Otherwise it double-gates behind your Vercel account and invitees can't reach
> the site. The alternatives to the custom gate are Vercel-native and were
> **not** chosen: *Vercel Authentication* (account-only, no shared password) and
> *Password Protection* (a real shared password, but a paid Pro feature).

## 4. Notes

- **`vercel.json` sets `"framework": null`** — required. Without it Vercel
  "Detects Python" and tries to build the whole project as a single Python app
  (which fails: it can't find one entrypoint). `framework: null` selects the
  static-site + `api/` serverless-function model that this bundle needs.
- The login page is served at **`/login.html`** (no clean-URL rewrite), and the
  gate redirects there; the form posts there too.
- The `/api/query` function usually answers in ~2–4 s on `gemini-3.1-flash-lite`
  (non-reasoning); `vercel.json` keeps `maxDuration: 60` as headroom for cold
  starts or a slower/reasoning model set via `GATEWAY_MODEL`.
- Static assets under `/static/*` are intentionally left open so the `/login`
  page can style itself; all content and the API are gated.
- Re-publishing overwrites this directory; commit and push to redeploy.
