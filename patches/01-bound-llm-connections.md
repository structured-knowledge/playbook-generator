# Patch 1 — bound outbound LLM connections + timeouts

**File:** `openkb/cli.py` · **Diff:** [`patch-01-bound-llm-connections.diff`](patch-01-bound-llm-connections.diff)
**Where:** inserted right after `litellm.suppress_debug_info = True`.

## Symptom

Backend connection count to the LLM endpoint climbs into the hundreds during
ingest (ESTABLISHED + CLOSE_WAIT), eventually hanging the LLM server. Observed
~883 never-draining sockets against a single-slot backend.

Separately, with no effective request timeout, a single wedged/half-closed
connection could stall an entire run for ~100 minutes before retrying.

## Root cause

OpenKB's bundled `pageindex` library fans out **unbounded**
`asyncio.gather()` LLM calls (one per node/TOC-item) with no HTTP-client
cleanup. `litellm` caches its async client per event loop, so nothing bounds
how many concurrent connections accumulate. Against a single-slot backend
(`llama.cpp --parallel 1`) behind a LiteLLM proxy, this both leaks sockets and
— with litellm's ~6000s default request timeout — leaves a hung connection
stalling the pipeline for a very long time before anything fails and retries.

## Fix

Sets bounded module-level httpx clients that litellm honors for
OpenAI-compatible providers (`litellm/llms/openai/common_utils.py`), so the
limits below govern every compile + PageIndex call:

- `httpx.Limits(max_connections=2, max_keepalive_connections=0)` —
  `max_keepalive_connections=0` means a server-closed (CLOSE_WAIT) socket is
  never handed back to the pool for reuse; each call gets a fresh connection
  that's closed when done, so there's nothing to leak. `max_connections=2`
  means one wedged connection no longer starves the whole pipeline — a second
  slot is available while the bad one is reaped.
- `httpx.Timeout(connect=30, read=300, write=300, pool=60)` — `pool=60` (not
  `None`) bounds the wait to *acquire* a connection from the pool; without it,
  a wedged connection that fills the pool makes the next request wait forever
  (event loop idle in kqueue, no timer). Now it raises `PoolTimeout` after 60s
  and litellm retries.
- `litellm.request_timeout = 300` — bounds each individual call to 5 minutes.
  **Must be a plain float** — litellm coerces this via `float()`, so an
  `httpx.Timeout` object raises. The OpenAI SDK path inside litellm applies
  its own per-request timeout that overrides the http client's timeout, so
  this setting is required even with the client-level timeout above.

## Caveats

- A float `request_timeout` also bounds httpx's pool-wait, so PageIndex's
  deep TOC fan-out (many calls queued behind few connections) may
  pool-timeout on a slow backend. Raise the 300 if that phase thrashes.
- Tuned for a single-slot backend. A backend with real concurrency headroom
  could raise `max_connections` accordingly.

## Verified

Socket count to the backend stays at 2 max instead of climbing to the
hundreds.

## Upstreaming

The proper fix belongs in `pageindex`: bound its `asyncio.gather` fan-out with
a `Semaphore` and close litellm async clients in a `finally` block. That would
make `pool=None` safe again with a tight `request_timeout`, removing the need
for this patch. Not yet filed upstream.
