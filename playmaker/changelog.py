"""Explicit conflict flagging + a richer changelog (spec: conflict-and-changelog).

OpenKB reconciles contradictions silently and writes a thin ``ingest |
filename`` log. playmaker layers on top, *non-invasively*, by snapshotting the
plays directory before an ingest and diffing it after (design.md D5). No
OpenKB internals are touched — the diff is computed from the wiki files the
engine produces.

From one before/after diff we derive, per changeset:
- **added** plays (a page that did not exist before),
- **enriched** plays (an existing page whose content changed — distinguished
  from "added", and we report accumulated provenance / new sources),
- **linked** plays (new ``[[wikilinks]]`` introduced this ingest),
- **contested** plays (an enrichment whose newly-added text reads like a
  contradiction — surfaced for human attention rather than silently merged).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from playmaker.paths import KB
from playmaker.wiki import list_plays

# Detecting a *contradiction between sources* in prose is a precision problem.
# The first cut matched bare cue words (contradict / conflict / critic* /
# whereas / counterproductive ...) anywhere in the text. Validated against a
# real 10-article AI-engineering corpus (28 plays), that flagged 8 plays — all
# false positives: "critical" matched "\bcritic\w*"; "state conflicts" and
# "sub-agents do not conflict" matched "conflict\w*"; "contradictory context"
# (a play's own subject — stress-testing RAG) matched "contradict\w*"; neutral
# comparisons ("smaller chunks ... whereas larger chunks ...") matched
# "whereas". Ordinary caveat/limitation language is not a contradiction.
#
# A genuine inter-source contradiction is a *meta-statement that a
# recommendation/practice is disputed*. So each cue now requires an
# OPPOSITIONAL construction anchored to advice/practice/belief (or an explicit
# "this is now an anti-pattern / dogma / deprecated" assertion), not a lone
# negative word. On the same corpus this flags 0/28 (correct — the articles are
# complementary), while still catching real contradictions (validated by the
# fixtures in tests/test_changelog.py). The bias is intentional: precision over
# recall (see docs/precision-recall.md). Matched on the text newly added by the
# ingest. A higher-recall alternative (an LLM-judge contradiction check on each
# enrichment) is noted in docs/precision-recall.md as a future lever.
_CONFLICT_CUES = [
    # "contradicts the advice/claim/recommendation/practice that ..."
    r"contradict\w*\s+(the\s+|this\s+|that\s+|prior\s+|existing\s+|common\s+|conventional\s+)?"
    r"(advice|recommendation|guidance|claim|notion|idea|view|practice|rule|belief|consensus|wisdom|principle|approach)",
    # "contrary to (the common) advice/wisdom/practice ..."
    r"contrary to (the |conventional |popular |common |prior |received |standard )?"
    r"(advice|wisdom|belief|recommendation|practice|guidance|view|approach|notion|rule)",
    # a competing camp argues a practice is bad
    r"\b(some|others?|many|several|critics?|skeptics?|detractors?|opponents?|experts?|practitioners?)\b"
    r"[^.]{0,80}?\b(argue|contend|claim|believe|caution|warn|maintain|insist|counter)\w*\b"
    r"[^.]{0,90}?(counterproductive|harmful|wrong|unnecessary|overrated|anti-?pattern|avoid|should not|shouldn't|dogma|mistake|misguided|outdated|obsolete|bad idea)",
    # a practice declared an anti-pattern / counterproductive / dogma / deprecated
    r"\b(is|are|becomes?|became|considered|seen as|viewed as)\b\s+(an?\s+)?"
    r"(anti-?pattern|counterproductive|dogma|overrated|outdated|obsolete|a mistake|misguided|deprecated)\b",
    r"\bcounterproductive\s+(dogma|rule|practice|advice|approach|ritual)\b",
    r"\bdogma\b",
    r"no longer (recommend\w*|advis\w*|considered|the )",
    r"(in contrast to|unlike) (the |a |common |conventional |popular |prior |standard |traditional )"
    r"(advice|recommendation|approach|practice|wisdom|belief|view|guidance|consensus)",
    r"\bdebate[sd]?\b\s+(over|about|on|whether)",
    r"at odds with (the |this |that |prior |existing |common )?"
    r"(advice|recommendation|guidance|claim|practice|rule|belief|consensus|view|approach|finding)",
    r"\bsupersed\w*\b",
    r"\bdeprecat\w*\b",
]
_CONFLICT_RE = re.compile("|".join(_CONFLICT_CUES), re.IGNORECASE)


@dataclass
class PlaySnap:
    key: str
    title: str
    content_hash: str
    sources: list[str]
    wikilinks: list[str]
    body: str


@dataclass
class Changeset:
    source: str
    added: list[str] = field(default_factory=list)
    enriched: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    linked: list[tuple[str, str]] = field(default_factory=list)
    contested: list[tuple[str, str]] = field(default_factory=list)  # (key, reason)
    sources_added: dict[str, list[str]] = field(default_factory=dict)
    titles: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""

    @property
    def empty(self) -> bool:
        return not (self.added or self.enriched or self.removed or self.linked)


def snapshot(kb: KB) -> dict[str, PlaySnap]:
    """Capture the current state of every play page, keyed by play key."""
    snaps: dict[str, PlaySnap] = {}
    for play in list_plays(kb):
        snaps[play.key] = PlaySnap(
            key=play.key,
            title=play.title,
            content_hash=play.content_hash,
            sources=list(play.sources),
            wikilinks=list(play.wikilinks),
            body=play.body,
        )
    return snaps


def _added_text(before_body: str, after_body: str) -> str:
    """Return the lines present in ``after_body`` but not in ``before_body``.

    A line-set difference, not a true diff — sufficient for spotting newly
    introduced contradiction language without a diff dependency.
    """
    before_lines = set(before_body.splitlines())
    return "\n".join(
        line for line in after_body.splitlines() if line not in before_lines
    )


def diff(
    before: dict[str, PlaySnap],
    after: dict[str, PlaySnap],
    *,
    source: str,
) -> Changeset:
    """Compute the changeset between two play snapshots."""
    cs = Changeset(source=source, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    before_keys = set(before)
    after_keys = set(after)

    for key in sorted(after_keys - before_keys):
        cs.added.append(key)
        cs.titles[key] = after[key].title

    for key in sorted(before_keys - after_keys):
        cs.removed.append(key)
        cs.titles[key] = before[key].title

    for key in sorted(before_keys & after_keys):
        b, a = before[key], after[key]
        cs.titles[key] = a.title
        if a.content_hash != b.content_hash:
            cs.enriched.append(key)
            new_sources = [s for s in a.sources if s not in set(b.sources)]
            if new_sources:
                cs.sources_added[key] = new_sources
            new_added_text = _added_text(b.body, a.body)
            if _CONFLICT_RE.search(new_added_text):
                cs.contested.append(
                    (key, "ingest introduced text that contradicts existing guidance")
                )

    # New links: any wikilink present in an added/enriched play that wasn't
    # there before (added plays: all their links are new).
    for key in cs.added:
        for target in after[key].wikilinks:
            cs.linked.append((key, target))
    for key in cs.enriched:
        new_links = set(after[key].wikilinks) - set(before[key].wikilinks)
        for target in sorted(new_links):
            cs.linked.append((key, target))

    return cs


def render_markdown(cs: Changeset) -> str:
    """Render a changeset as a human-readable changelog entry."""
    headline_bits = []
    if cs.added:
        headline_bits.append(f"+{len(cs.added)} play{'s' if len(cs.added) != 1 else ''}")
    if cs.enriched:
        headline_bits.append(f"enriched {len(cs.enriched)}")
    if cs.linked:
        headline_bits.append(f"linked {len(cs.linked)}")
    if cs.removed:
        headline_bits.append(f"removed {len(cs.removed)}")
    if cs.contested:
        headline_bits.append(f"⚠ {len(cs.contested)} contested")
    headline = ", ".join(headline_bits) if headline_bits else "no changes"

    lines = [f"## [{cs.timestamp}] {cs.source} — {headline}", ""]

    def name(key: str) -> str:
        return cs.titles.get(key, key)

    if cs.added:
        lines.append("**Added plays:**")
        lines += [f"- {name(k)}  (`{k}`)" for k in cs.added]
        lines.append("")
    if cs.enriched:
        lines.append("**Enriched plays:**")
        for k in cs.enriched:
            extra = ""
            if k in cs.sources_added:
                extra = f"  (+source: {', '.join(cs.sources_added[k])})"
            lines.append(f"- {name(k)}  (`{k}`){extra}")
        lines.append("")
    if cs.linked:
        lines.append("**Links created:**")
        lines += [f"- {name(src)} → [[{tgt}]]" for src, tgt in cs.linked]
        lines.append("")
    if cs.removed:
        lines.append("**Removed plays:**")
        lines += [f"- {name(k)}  (`{k}`)" for k in cs.removed]
        lines.append("")
    if cs.contested:
        lines.append("**⚠ Contested (needs review):**")
        lines += [f"- {name(k)}  (`{k}`) — {reason}" for k, reason in cs.contested]
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def append_changelog(kb: KB, cs: Changeset) -> None:
    """Append the changeset to ``.playmaker/changelog.md`` and ``changelog.json``."""
    kb.playmaker_dir.mkdir(parents=True, exist_ok=True)

    md_entry = render_markdown(cs) + "\n"
    if kb.changelog_md.exists():
        with kb.changelog_md.open("a", encoding="utf-8") as f:
            f.write(md_entry)
    else:
        kb.changelog_md.write_text(
            "# playmaker changelog\n\n" + md_entry, encoding="utf-8"
        )

    record = {
        "timestamp": cs.timestamp,
        "source": cs.source,
        "added": cs.added,
        "enriched": cs.enriched,
        "removed": cs.removed,
        "linked": [list(p) for p in cs.linked],
        "contested": [list(p) for p in cs.contested],
        "sources_added": cs.sources_added,
        "titles": cs.titles,
    }
    existing = []
    if kb.changelog_json.exists():
        try:
            existing = json.loads(kb.changelog_json.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append(record)
    kb.changelog_json.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
