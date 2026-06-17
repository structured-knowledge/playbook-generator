#!/usr/bin/env python3
"""Smoke test (tasks 1.4 / 6.3): one tiny LLM call through the gateway, then a
one-source end-to-end ingest.

This needs live gateway credentials, so it is a script you run — not part of
the offline unit suite. It exercises the integration playmaker can't fake:
that the LiteLLM gateway accepts our model id + headers (the spike's
User-Agent/WAF gotcha), and that an `openkb add` compiles a source into a play.

Usage:
    # with LLM_API_KEY + OPENAI_API_BASE in the environment (or a .env), and a
    # model set in the KB config / passed via --model:
    python scripts/smoke_test.py --model openai/<model>

Exit code 0 = both stages passed.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def stage_llm_call(model: str) -> bool:
    """Stage 1: a minimal completion through the configured gateway."""
    print(f"[1/2] tiny LLM call via gateway (model={model})...")
    try:
        import litellm
    except ImportError:
        print("  litellm not installed — install playmaker deps first.")
        return False

    api_base = os.environ.get("OPENAI_API_BASE")
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  LLM_API_KEY not set.")
        return False

    # Mirror the WAF workaround playmaker bakes into config.yaml.
    extra_headers = {"User-Agent": os.environ.get("PLAYMAKER_UA", "curl/8.4.0")}
    try:
        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            api_base=api_base,
            api_key=api_key,
            extra_headers=extra_headers,
            max_tokens=2048,
        )
        text = resp.choices[0].message.content or ""
        print(f"  gateway replied: {text.strip()[:60]!r}")
        return True
    except Exception as exc:  # noqa: BLE001 - smoke test reports any failure
        print(f"  [FAIL] gateway call failed: {exc}")
        return False


def stage_ingest(model: str) -> bool:
    """Stage 2: init an instance, ingest one tiny source, assert a play page."""
    print("[2/2] one-source end-to-end ingest...")
    from click.testing import CliRunner

    from playmaker.cli import cli
    from playmaker.paths import KB

    with tempfile.TemporaryDirectory() as tmp:
        kb_root = Path(tmp) / "kb"
        runner = CliRunner()
        r = runner.invoke(cli, ["init", str(kb_root), "--model", model])
        if r.exit_code != 0:
            print(f"  [FAIL] init: {r.output}")
            return False

        src = Path(tmp) / "tdd.md"
        src.write_text(
            "# Test-Driven Development\n\n"
            "Write a failing test first, then write just enough code to pass "
            "it, then refactor. Use a test runner (e.g. pytest). This keeps "
            "design honest and gives a regression safety net.\n",
            encoding="utf-8",
        )
        r = runner.invoke(cli, ["--kb-dir", str(kb_root), "ingest", str(src)])
        print(r.output)
        if r.exit_code != 0:
            print(f"  [FAIL] ingest exit {r.exit_code}")
            return False

        kb = KB(kb_root)
        plays = list(kb.plays_dir.glob("*.md")) if kb.plays_dir.is_dir() else []
        if not plays:
            print("  [FAIL] no play pages produced.")
            return False
        print(f"  produced {len(plays)} play page(s): {[p.stem for p in plays]}")
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("PLAYMAKER_MODEL", "openai/gpt-5.4-mini"))
    ap.add_argument("--skip-llm", action="store_true", help="Skip stage 1.")
    args = ap.parse_args()

    ok = True
    if not args.skip_llm:
        ok = stage_llm_call(args.model) and ok
    ok = stage_ingest(args.model) and ok

    print("\nSMOKE TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
