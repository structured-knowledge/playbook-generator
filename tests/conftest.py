"""Shared fixtures for the offline playmaker suite.

These tests never invoke OpenKB or an LLM. They fabricate a KB directory layout
on disk (the ``.openkb`` marker + ``wiki/concepts/`` play pages + ``.playmaker``)
so we can exercise the sidecar, changelog, wiki parser, and CLI deterministically.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from playmaker.paths import KB

PLAY_TEMPLATE = """\
---
sources: [{sources}]
brief: {brief}
---

# {title}

> **Why:** {why}

**Kind:** {kind}

## When to use
{when}

## How
{how}

## Outcome
{outcome}

## Caveats
{caveats}

## Tools
{tools}

## Related plays
{related}
"""


def write_play(
    kb: KB,
    slug: str,
    *,
    title: str = "A Play",
    why: str = "Because it pays off.",
    kind: str = "technique",
    sources: str = "summaries/doc.md",
    brief: str = "One-liner.",
    when: str = "When the situation calls for it.",
    how: str = "Do the thing.",
    outcome: str = "You get the result.",
    caveats: str = "It has limits.",
    tools: str = "- coding agent (e.g., Claude Code, Codex)",
    related: str = "",
) -> Path:
    kb.plays_dir.mkdir(parents=True, exist_ok=True)
    path = kb.plays_dir / f"{slug}.md"
    path.write_text(
        PLAY_TEMPLATE.format(
            sources=sources, brief=brief, title=title, why=why, kind=kind,
            when=when, how=how, outcome=outcome, caveats=caveats, tools=tools,
            related=related,
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def kb(tmp_path: Path) -> KB:
    """An initialized-looking KB (the .openkb marker makes discovery succeed)."""
    root = tmp_path / "kb"
    (root / ".openkb").mkdir(parents=True)
    (root / ".openkb" / "config.yaml").write_text("model: openai/test\n", encoding="utf-8")
    (root / "wiki" / "concepts").mkdir(parents=True)
    (root / ".playmaker").mkdir(parents=True)
    return KB(root)
