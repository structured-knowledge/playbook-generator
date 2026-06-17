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

# Maturity ordering for the maturity-first list view (established first),
# mirroring ``cli.py:plays_cmd``; see ``MATURITY_VALUES`` in sidecar.py.
_MATURITY_ORDER = ("established", "emerging", "experimental")

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


def _maturity_rank(record: dict) -> int:
    """Established < emerging < experimental < (unset), matching the CLI."""
    try:
        return _MATURITY_ORDER.index(record.get("maturity"))
    except ValueError:
        return len(_MATURITY_ORDER)


def sort_maturity_first(records: list[dict]) -> list[dict]:
    """Order plays maturity-first then title — the `cli.py:plays_cmd` ordering."""
    return sorted(records, key=lambda r: (_maturity_rank(r), r["title"].lower()))


def _facets(records: list[dict]) -> dict:
    """Per-facet value counts the index renders as chips. ``kind`` and ``tool``
    are ordered by count (desc) then name; ``maturity`` follows the canonical
    established-first order so the chips line up with the list sort."""
    kind: dict[str, int] = {}
    maturity: dict[str, int] = {}
    tool: dict[str, int] = {}
    for r in records:
        if r.get("kind"):
            kind[r["kind"]] = kind.get(r["kind"], 0) + 1
        if r.get("maturity"):
            maturity[r["maturity"]] = maturity.get(r["maturity"], 0) + 1
        for t in r.get("tool_categories") or []:
            tool[t] = tool.get(t, 0) + 1

    def by_count(counts: dict[str, int]) -> list[dict]:
        return [
            {"value": v, "count": c}
            for v, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        ]

    return {
        "kind": by_count(kind),
        "maturity": [
            {"value": m, "count": maturity[m]} for m in _MATURITY_ORDER if m in maturity
        ],
        "tool": by_count(tool),
        "contested": sum(1 for r in records if r.get("contested")),
    }


def group_by_kind(records: list[dict], facets: dict) -> list[dict]:
    """Group plays into a kind-keyed taxonomy for the vault tree, ordered by the
    facet order (most common kind first), each group maturity-first then title.
    Plays with no kind fall into a trailing ``None`` group."""
    by_kind: dict[str, list[dict]] = {}
    for r in records:
        by_kind.setdefault(r.get("kind") or "", []).append(r)
    groups: list[dict] = []
    for f in facets["kind"]:
        k = f["value"]
        groups.append({"kind": k, "plays": sort_maturity_first(by_kind.get(k, []))})
    if by_kind.get(""):
        groups.append({"kind": None, "plays": sort_maturity_first(by_kind[""])})
    return groups


def _to_question(record: dict) -> str:
    """Phrase a play as a natural example question, kind-aware. The first word is
    lowercased unless it's an acronym (AI, TDD), so titles read inside a sentence
    without mangling capitalized terms."""
    title = (record.get("title") or "").strip()
    if not title:
        return ""
    first = title.split(" ", 1)[0]
    if not (first.isupper() and len(first) > 1):
        title = title[:1].lower() + title[1:]
    if (record.get("kind") or "").lower() == "procedure":
        return f"How do I {title}?"
    return f"What's the playbook's take on {title}?"


def seed_questions(records: list[dict], limit: int = 3) -> list[str]:
    """A few example questions derived from the corpus at build time so the empty
    command bar is primed and the examples never drift from the plays. Prefers
    the most mature plays and spreads across kinds for variety."""
    ordered = sort_maturity_first(records)
    picked: list[str] = []
    seen_kind: set[str] = set()
    # Pass 1: at most one per kind (maturity-first) for variety.
    for r in ordered:
        if len(picked) >= limit:
            break
        kind = r.get("kind") or ""
        if kind in seen_kind:
            continue
        q = _to_question(r)
        if q and q not in picked:
            picked.append(q)
            seen_kind.add(kind)
    # Pass 2: fill any remaining slots from the top.
    for r in ordered:
        if len(picked) >= limit:
            break
        q = _to_question(r)
        if q and q not in picked:
            picked.append(q)
    return picked


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
    facets = _facets(records)
    examples = seed_questions(records)
    groups = group_by_kind(records, facets)

    env = Environment(
        loader=FileSystemLoader(str(_TPL_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    md = MarkdownIt("commonmark", {"linkify": True}).enable("table")
    titles = {r["key"]: r["title"] for r in records}

    # Enrich each record with the rendered reading-HTML + related panel. The
    # in-app viewer renders documents from plays.json client-side, so ``body_html``
    # is carried there too (additive — the query function reads ``body`` and
    # ignores it). Internal links stay as ``<slug>.html`` so the viewer can
    # intercept them (open in-pane) while deep links / no-JS still resolve.
    for r in records:
        body_md = _rewrite_wikilinks(_body_prose(r["body"]), keys)
        r["body_html"] = md.render(body_md)
        r["related"] = _related(r, keys, titles)

    # plays.json — the snapshot contract (viewer + query function read this).
    # ``facets``/``examples``/``body_html``/``related`` are additive; the query
    # function only uses ``key``/``title``/``body``.
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "plays.json").write_text(
        json.dumps(
            {"plays": records, "facets": facets, "examples": examples},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    play_tpl = env.get_template("play.html")
    for r in records:
        (out / r["url"]).write_text(play_tpl.render(play=r), encoding="utf-8")

    index_tpl = env.get_template("index.html")
    (out / "index.html").write_text(
        index_tpl.render(
            groups=groups,
            count=len(records),
            facets=facets,
            examples=examples,
            title="Playbook",
        ),
        encoding="utf-8",
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
