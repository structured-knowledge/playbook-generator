"""Read OpenKB wiki pages and parse them in playmaker (play) terms.

This is read-only: playmaker never writes into ``wiki/`` (that is OpenKB's
job). We parse the play shape that ``agents_md.PLAY_AGENTS_MD`` instructs the
compiler to produce — keep the two in sync.

A play's **key** is its wikilink target relative to ``wiki/``, e.g.
``concepts/test-driven-development`` (no ``.md``). This is stable, matches how
OpenKB cross-links pages, and is what the sidecar is keyed by (design.md D3 /
open question "page-key strategy").
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from playmaker.paths import KB, PLAYS_DIR

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")
_KIND_RE = re.compile(r"^\s*\*\*Kind:\*\*\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_WHY_RE = re.compile(r"^\s*>\s*\*\*Why:\*\*\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

VALID_KINDS = ("technique", "principle", "procedure")


@dataclass
class Play:
    """A parsed play page (an OpenKB concept page in playbook shape)."""

    key: str  # e.g. "concepts/tdd"
    slug: str  # e.g. "tdd"
    path: Path
    title: str
    why: str | None
    kind: str | None
    brief: str | None
    sources: list[str] = field(default_factory=list)
    tool_categories: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)
    body: str = ""
    content_hash: str = ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split OpenKB's YAML frontmatter (sources/brief) from the body.

    Uses a tolerant line parser rather than a YAML dependency for the only two
    fields we read; falls back to PyYAML if available for odd shapes.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    data: dict = {}
    try:
        import yaml

        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        for line in raw.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                data[k.strip()] = v.strip()
    return data, body


def _coerce_sources(value) -> list[str]:
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    if isinstance(value, str):
        inner = value.strip().strip("[]")
        return [s.strip().strip("'\"") for s in inner.split(",") if s.strip()]
    return []


def _extract_tool_categories(body: str) -> list[str]:
    """Pull bullet lines from a ``## Tools`` section.

    The play schema records tools category-first as bullets; we return each
    bullet's text (the category phrase, e.g. ``coding agent (e.g., ...)``).
    """
    cats: list[str] = []
    in_tools = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_tools = stripped[3:].strip().lower().startswith("tool")
            continue
        if in_tools and (stripped.startswith("- ") or stripped.startswith("* ")):
            cats.append(stripped[2:].strip())
    return cats


def parse_play(path: Path, *, plays_dirname: str = PLAYS_DIR) -> Play:
    """Parse a single play page file."""
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    slug = path.stem
    key = f"{plays_dirname}/{slug}"

    h1 = _H1_RE.search(body)
    title = h1.group(1).strip() if h1 else slug

    kind_m = _KIND_RE.search(body)
    kind = None
    if kind_m:
        k = kind_m.group(1).strip().lower()
        kind = k if k in VALID_KINDS else k  # keep raw; validation is separate

    why_m = _WHY_RE.search(body)
    why = why_m.group(1).strip() if why_m else None

    return Play(
        key=key,
        slug=slug,
        path=path,
        title=title,
        why=why,
        kind=kind,
        brief=(str(fm["brief"]).strip() if fm.get("brief") else None),
        sources=_coerce_sources(fm.get("sources")),
        tool_categories=_extract_tool_categories(body),
        wikilinks=sorted(set(_WIKILINK_RE.findall(text))),
        body=body,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def list_plays(kb: KB) -> list[Play]:
    """Parse every play page in the KB, sorted by key."""
    plays_dir = kb.plays_dir
    if not plays_dir.is_dir():
        return []
    plays = [parse_play(p) for p in sorted(plays_dir.glob("*.md"))]
    return plays


def play_keys(kb: KB) -> set[str]:
    """The set of current play keys (``concepts/<slug>``) on disk."""
    plays_dir = kb.plays_dir
    if not plays_dir.is_dir():
        return set()
    return {f"{PLAYS_DIR}/{p.stem}" for p in plays_dir.glob("*.md")}
