# OpenKB local patches

Four runtime patches to the pinned **OpenKB v0.4.1** engine
(`openkb @ git+https://github.com/VectifyAI/OpenKB.git@v0.4.1`, see
`pyproject.toml`). They fix a socket leak, a permanent-hang failure mode, a
Cloudflare WAF block, and a Vertex/Gemini 400 — all hit running OpenKB against
a real deployment (single-slot local LLM backend behind a Cloudflare-fronted
LiteLLM proxy, plus a Gemini/Vertex route).

**Status: not upstreamed.** These are not forked into this repo's dependency
tree (`pyproject.toml` still pins stock `v0.4.1`) — they're documented here so
they can be re-applied to an installed `openkb` package after `pip install` /
`uv pip install`, since `playmaker` consumes OpenKB as an installed dependency,
not a vendored copy.

| # | File | Diff | Doc | Fixes |
|---|------|------|-----|-------|
| 1 | `openkb/cli.py` | [`patch-01-bound-llm-connections.diff`](patch-01-bound-llm-connections.diff) | [doc](01-bound-llm-connections.md) | socket leak from unbounded LLM fan-out |
| 2 | `openkb/agent/compiler.py` | [`patch-02-compile-concurrency.diff`](patch-02-compile-concurrency.diff) | [doc](02-compile-concurrency.md) | compile phase overwhelming a single-slot backend |
| 3 | `openkb/config.py` | [`patch-03-propagate-extra-headers.diff`](patch-03-propagate-extra-headers.diff) | [doc](03-propagate-extra-headers.md) | Cloudflare WAF blocking PageIndex's direct LLM calls |
| 4 | `openkb/agent/compiler.py` | [`patch-04-strip-cache-control-vertex.diff`](patch-04-strip-cache-control-vertex.diff) | [doc](04-strip-cache-control-vertex.md) | Vertex 400 on small cached blocks (gemini routes only) |

Patches 2 and 4 both touch `compiler.py` but are independent, non-overlapping
hunks — apply in any order.

## When you need these

Only if your deployment hits the symptoms below. None of these are required
for a normal OpenKB run against a roomy/cloud-hosted LLM endpoint — they exist
because of a **single-slot backend** (e.g. `llama.cpp --parallel 1`) and/or a
**Cloudflare-fronted** LiteLLM proxy. If neither applies to your setup, skip
this folder.

- Patch 1 — LLM backend connection count climbs into the hundreds during
  ingest, or the backend hangs requiring a restart.
- Patch 2 — same symptom as Patch 1 but specifically during the compile phase
  (concept/entity generation), even with Patch 1 applied.
- Patch 3 — `openkb add` succeeds at PageIndex indexing but the document is
  left unregistered with orphan `wiki/sources|summaries/<doc>` files, and your
  LiteLLM proxy is behind a WAF/CDN.
- Patch 4 — compile fails with a Vertex error like *"The cached content is of
  N tokens. The minimum token count to start caching is 4096"* — only relevant
  if `model:` in `.openkb/config.yaml` is a gemini/Vertex model.

## How to apply

Against an installed `openkb` 0.4.1 (e.g. in a venv created by
`scripts/install.sh`):

```bash
SITE_PKGS=$(python3 -c "import openkb, os; print(os.path.dirname(os.path.dirname(openkb.__file__)))")
cd "$SITE_PKGS"
patch -p1 < /path/to/playbook-generator/patches/patch-01-bound-llm-connections.diff
patch -p1 < /path/to/playbook-generator/patches/patch-02-compile-concurrency.diff
patch -p1 < /path/to/playbook-generator/patches/patch-03-propagate-extra-headers.diff
patch -p1 < /path/to/playbook-generator/patches/patch-04-strip-cache-control-vertex.diff
```

Apply only the patches your symptoms call for — they're independent (Patches
2 and 4 share a file but not a hunk, so any subset applies cleanly).

**These are silently lost on every reinstall** (`pip install -U`, a fresh
`scripts/install.sh` run, a new venv, a new machine) since they edit the
installed package in place rather than forking the dependency. Re-apply after
any reinstall, or — for the proper long-term fix — see "Upstreaming" in each
patch doc.

## Verifying patches are active

```bash
python3 -c "
import openkb.cli, litellm
from openkb.agent.compiler import DEFAULT_COMPILE_CONCURRENCY as C
p = litellm.aclient_session._transport._pool
t = litellm.aclient_session._timeout
print('compile_concurrency', C)
print('request_timeout', litellm.request_timeout)
print('max_connections', p._max_connections, 'keepalive', p._max_keepalive_connections, 'pool_timeout', t.pool)
"
# expect: compile_concurrency 1 / request_timeout 300 / max_connections 2 keepalive 0 pool_timeout 60.0
```

## Provenance

Diffs were generated against a pristine `openkb==0.4.1` sdist (downloaded via
`pip download openkb==0.4.1 --no-deps --no-binary :all:`) and verified to
apply cleanly with `patch -p1` and reproduce the patched install byte-for-byte.
