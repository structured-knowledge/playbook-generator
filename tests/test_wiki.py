"""Wiki parser: the play shape AGENTS.md promises must be parseable."""
from __future__ import annotations

from tests.conftest import write_play

from playmaker.wiki import list_plays, parse_play, play_keys


def test_parse_play_extracts_shape(kb):
    path = write_play(
        kb, "tdd",
        title="Test-Driven Development",
        why="Tests-first keeps design honest.",
        kind="procedure",
        sources="summaries/a.md, summaries/b.md",
        tools="- coding agent (e.g., Claude Code, Codex)\n- test runner (e.g., pytest)",
        related="[[concepts/refactoring]]",
    )
    play = parse_play(path)
    assert play.key == "concepts/tdd"
    assert play.title == "Test-Driven Development"
    assert play.why == "Tests-first keeps design honest."
    assert play.kind == "procedure"
    assert play.sources == ["summaries/a.md", "summaries/b.md"]
    assert "coding agent (e.g., Claude Code, Codex)" in play.tool_categories
    assert "test runner (e.g., pytest)" in play.tool_categories
    assert "concepts/refactoring" in play.wikilinks


def test_list_plays_and_keys(kb):
    write_play(kb, "a", title="A")
    write_play(kb, "b", title="B")
    plays = list_plays(kb)
    assert [p.slug for p in plays] == ["a", "b"]
    assert play_keys(kb) == {"concepts/a", "concepts/b"}
