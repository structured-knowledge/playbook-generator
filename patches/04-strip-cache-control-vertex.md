# Patch 4 — strip `cache_control` for gemini/Vertex

**File:** `openkb/agent/compiler.py` (new helper `_strip_cache_control_for_vertex`, ~line 264, called from `_llm_call` and `_llm_call_async`) · **Diff:** [`patch-04-strip-cache-control-vertex.diff`](patch-04-strip-cache-control-vertex.diff)

## Symptom

The overview/concepts compile step fails for a gemini/Vertex-routed model
with a 400 error like:

> The cached content is of 1592 tokens. The minimum token count to start
> caching is 4096.

PageIndex indexing succeeds first, so the failure leaves the document
**unregistered** with orphan `wiki/sources|summaries/<doc>` files — same
visible symptom as [Patch 3](03-propagate-extra-headers.md), different cause.
Only triggers when `model:` in `.openkb/config.yaml` is a gemini/Vertex model
(`litellm_proxy/gemini-...` or similar); the Qwen/llama.cpp backend never
trips this, since it ignores the marker entirely.

## Root cause

OpenKB's compile path tags the document block with an **Anthropic-style**
`cache_control: ephemeral` marker (`compiler._cached_text()`), intended for
Anthropic's prompt-caching feature. Routed through LiteLLM to Gemini via
Vertex, LiteLLM forwards that marker as a **Vertex context-caching request**
instead of silently ignoring it — and Vertex requires a minimum 4096 tokens to
start a cache, which most individual document blocks don't reach, so it 400s.

## Fix

A new helper, `_strip_cache_control_for_vertex(model, messages)`, drops the
`cache_control` key from message content blocks **only when the model name
contains `gemini` or `vertex`** (case-insensitive substring match). Called at
the top of both `_llm_call` and `_llm_call_async`, before the request is
built. Other providers (Anthropic, OpenAI-compatible, local backends) are
untouched and keep their caching behavior.

## Verified

`05-offers-and-lead-magnets.pdf` compiles and becomes queryable on
`gemini-3.1-flash-lite` after this patch (previously failed with the 400
above and left the doc orphaned).

## Upstreaming

This is really a LiteLLM/OpenKB compatibility gap — `cache_control` is an
Anthropic-specific hint that shouldn't be forwarded as a Vertex caching
directive without meeting Vertex's preconditions (token minimum, or just
not translating it for non-Anthropic providers at all). Worth filing against
either OpenKB (don't emit the marker for non-Anthropic models) or LiteLLM
(don't translate the marker into a Vertex caching request when the content is
under the minimum). Not yet filed.
