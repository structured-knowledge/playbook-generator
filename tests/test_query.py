"""The serverless query function: retrieval seam, prompt, citation handling.

Loads the deployable function file directly (it intentionally does not import
playmaker) and exercises it offline by stubbing the gateway call.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_QUERY_PY = Path(__file__).resolve().parents[1] / "playmaker" / "publish" / "api" / "query.py"


@pytest.fixture
def q():
    spec = importlib.util.spec_from_file_location("query_fn", _QUERY_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plays():
    return [
        {"key": "concepts/a", "title": "Alpha", "body": "A" * 5000},
        {"key": "concepts/b", "title": "Beta", "body": "Beta body."},
    ]


def test_select_plays_returns_all(q):
    plays = _plays()
    assert q.select_plays("anything", plays) == plays


def test_build_prompt_includes_all_keys_and_truncates(q):
    prompt = q.build_prompt("how?", _plays())
    assert "[[concepts/a]]" in prompt and "[[concepts/b]]" in prompt
    assert "QUESTION: how?" in prompt
    # the 5000-char body is truncated to the per-play budget
    assert "A" * (q.MAX_BODY_CHARS + 1) not in prompt


def test_answer_extracts_and_validates_citations(q, monkeypatch):
    # stub the gateway: cite one real key and one bogus key
    monkeypatch.setattr(
        q, "call_gateway",
        lambda prompt: "Use [[concepts/a]] and also [[concepts/ghost]].",
    )
    res = q.answer("how?", _plays())
    assert res["cited"] == ["concepts/a"]      # bogus key dropped
    assert res["play_count"] == 2
    assert "ghost" in res["answer"]            # text itself is untouched


def test_load_plays_from_explicit_path(q, tmp_path):
    p = tmp_path / "plays.json"
    p.write_text(json.dumps({"plays": _plays()}), encoding="utf-8")
    loaded = q.load_plays(str(p))
    assert [r["key"] for r in loaded] == ["concepts/a", "concepts/b"]
