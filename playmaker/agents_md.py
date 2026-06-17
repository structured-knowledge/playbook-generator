"""The custom ``wiki/AGENTS.md`` that turns OpenKB's compiler into a playbook
compiler.

OpenKB reads ``wiki/AGENTS.md`` from disk and injects it as the **system
prompt** for every compilation step (summary, concepts-plan, concept-page
generation). So redefining the *concept page* as a PLAY here reshapes the
output without touching OpenKB code (design.md D2; spec: play-schema).

This is intentionally a superset of OpenKB's bundled schema: the directory
structure, index format, log format, wikilink rules, and the "no
LLM-authored frontmatter" rule are preserved verbatim so the rest of the
engine (index maintenance, lint, entity pages) keeps working. Only the
**Concept Page = PLAY** definition and the play shape are new.

The play shape (WHY-led; ``Kind``; When/How/Outcome/Caveats; category-first
tools; ``## Related plays`` wikilinks) is the contract the sidecar/changelog
parsers in ``playmaker.wiki`` rely on — keep them in sync.
"""
from __future__ import annotations

from pathlib import Path

PLAY_AGENTS_MD = """\
# Wiki Schema — Playbook Mode

This knowledge base is a **playbook**. Concept pages are **PLAYS**: discrete,
reusable, actionable ways to do something well in this domain. Compile sources
into plays, not encyclopedia articles.

## Directory Structure
- sources/ — Document content. Short docs as .md, long docs as .json (per-page). Do not modify directly.
- sources/images/ — Extracted images from documents, referenced by sources.
- summaries/ — One per source document. Summary of key content.
- concepts/ — **The plays.** Each page is one play (see Play Page below). Cross-document synthesis.
- entities/ — Specific named things: people, organizations, places, products, named works, events. One page per entity.
- explorations/ — Saved query results, analyses, and comparisons worth keeping.
- reports/ — Lint health check reports. Auto-generated.

## Page Types
- **Summary Page** (summaries/): Key content of a single source document.
- **Play Page** (concepts/): ONE actionable play. This is the high-value output. See "Play Page Shape".
- **Entity Page** (entities/): A specific named thing (proper noun) — a person, organization, place, product, named work, or event. Each page has a `type:` frontmatter field; the authoritative type set is given in the compilation prompt. An entity differs from a play: a play is something you *do*; an entity is a named thing. Page an entity only when it is central or recurs.
- **Exploration Page** (explorations/): Saved query results.
- **Index Page** (index.md): One-liner summary of every page. Auto-maintained.

## Play Page Shape (concepts/)
Every play page MUST follow this shape. Lead with WHY, then make it usable:

```
# <Imperative play name>

> **Why:** <one sentence: the principle or payoff that makes this worth doing>

**Kind:** <technique | principle | procedure>

## When to use
<the situation/trigger where this play applies; and when NOT to>

## How
<concrete steps or the core move; numbered steps for procedures>

## Outcome
<what you get when it works — the observable result>

## Caveats
<failure modes, costs, preconditions, where it breaks down>

## Tools
<only if relevant — see "Tools are category-first" below>

## Related plays
<[[wikilinks]] to related, prerequisite, or alternative plays — see "Linking">
```

Rules for the shape:
- **WHY first.** The first line after the title is a `> **Why:**` blockquote stating the underlying principle, not a restatement of the title.
- **Kind** is exactly one of `technique`, `principle`, or `procedure`. Pick the best fit:
  - *technique* — a concrete method/move you apply.
  - *principle* — a rule of thumb / mental model that guides decisions.
  - *procedure* — an ordered, repeatable sequence of steps.
- Keep each play focused on ONE play. If a source describes several distinct plays, make several pages.
- Do not invent sections. Omit `## Tools` when no tool matters. Keep `## Caveats` even if short — every real play has limits.

## Tools are category-first
Record tools as a **stable category first**, with specific products as
swappable examples — never lead with a product name:

- Good: `coding agent (e.g., Claude Code, Codex, Cursor)`
- Good: `vector database (e.g., pgvector, Pinecone)`
- Bad: `Claude Code` as the primary identifier

Products churn; categories endure. A reader should be able to swap the example
for today's equivalent.

## High precision over recall (IMPORTANT)
Only create a play for something **clearly, specifically actionable** in this
domain. This playbook is curated, not exhaustive.
- DO skip: general background, motivation/prose, definitions, things the source
  explicitly dismisses or argues against, and vague "be thoughtful"-style
  advice that carries no concrete move.
- DO NOT manufacture a play from thin material. If you cannot fill `When to
  use` + `How` + `Outcome` with substance from the source, do not create the
  play.
- When in doubt, leave it out. A missed borderline practice is cheaper than a
  noisy, low-value play. (This precision bias is intentional — see
  playmaker docs/precision-recall.md.)

## Enrich in place — do not duplicate
Before creating a play, read existing plays. If a source covers a play that
already exists, **update that play in place**: merge the new specifics, add the
new source to its `sources:` frontmatter (handled by code), and reconcile any
contradiction into the body (note the differing conditions rather than
silently overwriting). Create a new play ONLY for a genuinely new play.

## Linking
- Use `[[wikilink]]` to link other pages, e.g. `[[concepts/some-play]]`.
- Put cross-references to related plays in a `## Related plays` section at the
  end of the page (this is where readers and tooling look for them).
- Link prerequisite plays, alternative plays, and plays that this one builds
  on. Automatic related-links live here; human-asserted typed links
  (prerequisite / alternative / counters) are managed separately by playmaker
  and are not your concern.

## Index Page Format
index.md lists all documents, concepts (plays), entities, and explorations:
- Documents: name, one-liner description, type (short|pageindex), detail access path
- Concepts: name, one-liner description
- Entities: name, type, one-liner description
- Explorations: name, one-liner description

## Log Format
Each log entry: `## [YYYY-MM-DD HH:MM:SS] operation | description`
Operations: ingest, query, lint

## Format
- Use [[wikilink]] to link other wiki pages (e.g., [[concepts/some-play]])
- Standard Markdown heading hierarchy
- Keep each page focused on a single play
- Do not include YAML frontmatter (---) in generated content; it is managed by code
"""


def install_agents_md(agents_md_path: Path, *, force: bool = False) -> bool:
    """Write the play-shaped AGENTS.md to ``agents_md_path``.

    Returns True if written. When the target already holds the current play
    schema, this is a no-op (returns False) unless ``force`` is set. If a
    different AGENTS.md exists, it is backed up to ``AGENTS.md.bak`` first.
    """
    agents_md_path.parent.mkdir(parents=True, exist_ok=True)
    if agents_md_path.exists():
        current = agents_md_path.read_text(encoding="utf-8")
        if current == PLAY_AGENTS_MD and not force:
            return False
        backup = agents_md_path.with_suffix(".md.bak")
        backup.write_text(current, encoding="utf-8")
    agents_md_path.write_text(PLAY_AGENTS_MD, encoding="utf-8")
    return True
