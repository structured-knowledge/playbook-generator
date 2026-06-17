"""Render the vault into a deployable static site + ``plays.json``.

Read-only over the vault: this reuses ``wiki.list_plays`` + ``Sidecar`` and
writes only into the output directory — never into ``wiki/`` or ``.openkb/``
(spec: web-publish). ``plays.json`` is the snapshot contract (spec: web-query):
it carries each play's full record (incl. body) so search and the query function
need not re-read the vault.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

from playmaker.paths import KB
from playmaker.sidecar import Sidecar
from playmaker.wiki import list_plays

_TPL_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"
_API_DIR = Path(__file__).parent / "api"
_DEPLOY_DIR = Path(__file__).parent / "deploy"

_WIKILINK = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]*))?\]\]")
_H1 = re.compile(r"^\s*#\s+.+$")
_H2 = re.compile(r"^\s*##\s+")
_KIND_LINE = re.compile(r"^\s*\*\*Kind:\*\*", re.IGNORECASE)
_WHY_LINE = re.compile(r"^\s*>\s*\*\*Why:\*\*", re.IGNORECASE)
# Sections rendered separately (structured), so dropped from the body prose.
_SECTION_DROP = re.compile(r"^\s*##\s+(tool|related)", re.IGNORECASE)
_RULE_ONLY = ("", "---", "***", "___")


@dataclass
class PublishResult:
    out_dir: Path
    play_count: int


def _slug_of(key: str) -> str:
    return key.split("/")[-1]


def _titleize(key: str) -> str:
    return _slug_of(key).replace("-", " ")


def _flatten_wikilinks(text: str) -> str:
    """Strip wikilink syntax to readable labels (for non-markdown fields like
    tool categories): ``[[entities/claude-code]]`` → ``claude code``,
    ``[[a|Label]]`` → ``Label``."""
    return _WIKILINK.sub(lambda m: (m.group(2) or "").strip() or _titleize(m.group(1).strip()), text)


def build_records(kb: KB) -> tuple[list[dict], set[str]]:
    """Merge each parsed play with its sidecar entry into a JSON-able record.

    Returns ``(records, play_keys)``. ``play_keys`` lets the renderer resolve
    which links point at real published pages.
    """
    sidecar = Sidecar.load(kb.sidecar_path)
    plays = list_plays(kb)
    keys = {p.key for p in plays}
    records: list[dict] = []
    for p in plays:
        entry = sidecar.get(p.key)
        try:
            updated = datetime.fromtimestamp(p.path.stat().st_mtime).strftime("%Y-%m-%d")
        except OSError:
            updated = None
        records.append(
            {
                "key": p.key,
                "slug": p.slug,
                "title": p.title,
                "updated": updated,
                "why": p.why,
                "kind": p.kind,
                "brief": p.brief,
                "maturity": entry.get("maturity"),
                "contested": bool(entry.get("contested")),
                "tool_categories": [_flatten_wikilinks(t) for t in p.tool_categories],
                "wikilinks": list(p.wikilinks),
                "typed_links": entry.get("typed_links", []),
                "sources": p.sources,
                "body": p.body,
                "url": f"{p.slug}.html",
            }
        )
    records.sort(key=lambda r: r["title"].lower())
    return records, keys


def _body_prose(body: str) -> str:
    """Return the substantive prose: drop the H1, the ``**Kind:**`` line, the
    ``> **Why:**`` blockquote, and the ``## Tools`` / ``## Related`` sections —
    all of which are rendered separately (title, badge, callout, structured
    panels), so leaving them in would duplicate them."""
    out, h1_done, skipping = [], False, False
    for line in body.splitlines():
        if _H2.match(line):
            skipping = bool(_SECTION_DROP.match(line))
            if skipping:
                continue
        if skipping:
            continue
        if not h1_done and _H1.match(line):
            h1_done = True
            continue
        if _KIND_LINE.match(line) or _WHY_LINE.match(line):
            continue
        out.append(line)
    while out and out[-1].strip() in _RULE_ONLY:  # trailing rule before a dropped section
        out.pop()
    return "\n".join(out).strip()


def _rewrite_wikilinks(md: str, play_keys: set[str]) -> str:
    """Turn ``[[concepts/x]]`` / ``[[concepts/x|label]]`` into markdown links to
    published play pages; render non-play targets (entities, summaries) as plain
    text so the body has no dead links."""

    def repl(m: re.Match) -> str:
        target = m.group(1).strip()
        label = (m.group(2) or "").strip() or _titleize(target)
        if target in play_keys:
            return f"[{label}]({_slug_of(target)}.html)"
        return label

    return _WIKILINK.sub(repl, md)


def _related(record: dict, keys: set[str], titles: dict[str, str]) -> dict:
    """Build the Related panel: human typed links (labeled) kept distinct from
    automatic wikilinks; only play targets become links."""
    typed = [
        {
            "type": l.get("type"),
            "key": l.get("target"),
            "title": titles.get(l.get("target"), _titleize(l.get("target") or "")),
            "url": f"{_slug_of(l['target'])}.html" if l.get("target") in keys else None,
        }
        for l in record["typed_links"]
    ]
    wikilinks = [
        {"key": w, "title": titles.get(w, _titleize(w)), "url": f"{_slug_of(w)}.html"}
        for w in record["wikilinks"]
        if w in keys and w != record["key"]
    ]
    return {"typed": typed, "wikilinks": wikilinks}


def publish(kb: KB, out_dir: Path) -> PublishResult:
    """Render the snapshot into ``out_dir`` (created if needed)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    records, keys = build_records(kb)

    # plays.json — the snapshot contract (search + query function read this).
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "plays.json").write_text(
        json.dumps({"plays": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    env = Environment(
        loader=FileSystemLoader(str(_TPL_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    md = MarkdownIt("commonmark", {"linkify": True}).enable("table")
    titles = {r["key"]: r["title"] for r in records}

    play_tpl = env.get_template("play.html")
    for r in records:
        body_md = _rewrite_wikilinks(_body_prose(r["body"]), keys)
        view = dict(r, body_html=md.render(body_md), related=_related(r, keys, titles))
        (out / r["url"]).write_text(play_tpl.render(play=view), encoding="utf-8")

    index_tpl = env.get_template("index.html")
    (out / "index.html").write_text(
        index_tpl.render(plays=records, count=len(records)), encoding="utf-8"
    )

    shutil.copytree(_STATIC_DIR, out / "static", dirs_exist_ok=True)
    # The serverless query function reads data/plays.json at request time
    # (spec: web-query). Deploy config (Vercel pyproject/requirements) is added
    # by the gating-and-deploy step.
    shutil.copytree(_API_DIR, out / "api", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    # Deploy assets at the bundle root: the password gate (middleware.js +
    # login.html), vercel.json, requirements.txt, and the runbook
    # (spec: web-gating-deploy).
    for f in _DEPLOY_DIR.iterdir():
        if f.is_file():
            shutil.copy2(f, out / f.name)
    return PublishResult(out_dir=out, play_count=len(records))
