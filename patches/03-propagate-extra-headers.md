# Patch 3 — propagate `extra_headers` into `litellm.headers`

**File:** `openkb/config.py` (inside `set_extra_headers()`, ~line 147) · **Diff:** [`patch-03-propagate-extra-headers.diff`](patch-03-propagate-extra-headers.diff)

## Symptom

`openkb add` reports successful PageIndex indexing, then the document is left
**unregistered** with orphan `wiki/sources|summaries/<doc>` files — it never
shows up in the registry, and `recompile` can't pick it up. Re-running
`openkb add` is required. The underlying error (visible in verbose/debug
output) is `litellm_proxyException - Your request was blocked`.

This only matters if your LiteLLM proxy sits behind a WAF/CDN that
fingerprints the default User-Agent. A Cloudflare WAF in front of the proxy
**403s the default `User-Agent: OpenAI/Python ...`** fingerprint that litellm
sends; a custom `User-Agent: openkb` clears it (verified: default UA → 403,
overridden UA → 200).

## Root cause

OpenKB itself already supports overriding outbound headers via
`extra_headers: {User-Agent: openkb}` in `.openkb/config.yaml`, and its own
call sites pass that through. But `pageindex.utils.llm_completion` /
`llm_acompletion` — used during indexing — call `litellm.completion()`
**directly, with no header pass-through** from OpenKB's config. So PageIndex's
requests were still hitting the WAF even with the config key set.

## Fix

`set_extra_headers()` now also writes the same headers into LiteLLM's global
`litellm.headers` dict, not just the process-local `_runtime_extra_headers`
OpenKB itself reads. LiteLLM merges `litellm.headers` into every
OpenAI/proxy-routed call (`main.py: headers = headers or litellm.headers`), so
setting it once globally covers PageIndex's direct calls too — no change
needed in `pageindex` itself.

**Depends on** the config key already being set in `.openkb/config.yaml`:

```yaml
extra_headers:
  User-Agent: openkb
```

Without that key, this patch is a no-op (the `if headers:` guard short-circuits).

## Verified

`05-offers-and-lead-magnets.pdf`-class documents (previously left orphaned)
compile and register correctly through a Cloudflare-fronted proxy with this
patch + the config key in place.

## Caveat

Global mutable state (`litellm.headers`) is shared process-wide — fine for
OpenKB's single-purpose CLI process, but would leak across unrelated litellm
calls in a process that uses litellm for other things alongside OpenKB.
