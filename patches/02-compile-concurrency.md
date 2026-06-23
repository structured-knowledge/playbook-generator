# Patch 2 — compile concurrency 5 → 1

**File:** `openkb/agent/compiler.py` (line ~1382) · **Diff:** [`patch-02-compile-concurrency.diff`](patch-02-compile-concurrency.diff)
**Change:** `DEFAULT_COMPILE_CONCURRENCY = 5` → `= 1`

## Symptom

Same hang/leak symptom as [Patch 1](01-bound-llm-connections.md) but
specifically during the compile phase (concept/entity generation), even with
Patch 1's connection bounding applied.

## Root cause

The compile phase defaults to `concurrency=5`
(`asyncio.Semaphore(max_concurrency)` at `compiler.py:1612`). All four call
sites (`cli.py:366/382/1278/1298`) use this default, so five compile tasks run
concurrently at the application level — on top of, not instead of, the
httpx-level connection cap from Patch 1. Against a single-slot backend, five
queued tasks behind a 2-connection pool meant that when one connection wedged
on a CLOSE_WAIT, the whole batch deadlocked waiting on it.

## Fix

Change the constant so the whole compile run executes one call at a time,
matching the single-slot backend at the application level — not just the
connection-pool level.

## Verified

Compile no longer deadlocks under the single-slot backend; matches the
connection cap in Patch 1 instead of fighting it.

## Notes

- Independent of Patch 4 even though both touch `compiler.py` — different
  line ranges, no overlap, apply in either order or alone.
- If your backend has real concurrency headroom, this constant (and Patch 1's
  `max_connections`) can both be raised together — they should move in
  lockstep with backend capacity.
