"""Changelog/diff: added vs enriched, provenance, links, conflict detection."""
from __future__ import annotations

import pytest

from tests.conftest import write_play

from playmaker import changelog as cl


def test_added_play(kb):
    before = cl.snapshot(kb)
    write_play(kb, "tdd", title="TDD")
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="tdd.md")
    assert cs.added == ["concepts/tdd"]
    assert cs.enriched == []
    assert cs.titles["concepts/tdd"] == "TDD"


def test_enrichment_distinguished_from_add_with_provenance(kb):
    write_play(kb, "tdd", title="TDD", sources="summaries/a.md", how="Write a failing test.")
    before = cl.snapshot(kb)
    # same page, new source + changed body => enrichment, not a new play
    write_play(
        kb, "tdd", title="TDD",
        sources="summaries/a.md, summaries/b.md",
        how="Write a failing test, then the minimum code to pass it.",
    )
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="b.md")
    assert cs.added == []
    assert cs.enriched == ["concepts/tdd"]
    # provenance accumulated
    assert cs.sources_added["concepts/tdd"] == ["summaries/b.md"]


def test_new_links_reported(kb):
    write_play(kb, "tdd", title="TDD", related="")
    before = cl.snapshot(kb)
    write_play(kb, "tdd", title="TDD", related="[[concepts/refactoring]]")
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="b.md")
    assert ("concepts/tdd", "concepts/refactoring") in cs.linked


def test_conflict_detected_on_contradictory_enrichment(kb):
    write_play(kb, "tdd", title="TDD", caveats="It has limits.")
    before = cl.snapshot(kb)
    # enrichment adds contradiction language
    write_play(
        kb, "tdd", title="TDD",
        caveats="It has limits. However this source contradicts the claim and "
                "argues tests-first should be avoided here.",
    )
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="contrarian.md")
    assert any(k == "concepts/tdd" for k, _ in cs.contested)


def test_conflict_detected_on_reconciled_contradiction(kb):
    """The compiler often merges an opposing source by hedging the rule rather
    than keeping the word 'contradict' — this real e2e phrasing must still flag."""
    write_play(kb, "small-prs", title="Keep PRs Small",
               caveats="Breaking work into small PRs adds coordination overhead.")
    before = cl.snapshot(kb)
    write_play(
        kb, "small-prs", title="Keep PRs Small",
        caveats="Mandating small PRs as an absolute rule can become "
                "counterproductive dogma. For cohesive work, splitting "
                "fragments critical context.",
    )
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="against-small-prs.md")
    assert any(k == "concepts/small-prs" for k, _ in cs.contested)


def test_plain_enrichment_not_flagged_contested(kb):
    write_play(kb, "tdd", title="TDD", how="Write a failing test.")
    before = cl.snapshot(kb)
    write_play(kb, "tdd", title="TDD", how="Write a failing test, then refactor.")
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="b.md")
    assert cs.contested == []


# Real false-positive sentences from the 10-article corpus that the first cue
# list wrongly flagged (bare "critic*"/"conflict"/"contradict"/"whereas"). The
# precise detector must NOT flag ordinary caveat/limitation/comparison prose.
_REAL_FALSE_POSITIVES = [
    "Ensure the compaction prompt extracts critical elements.",
    "A generic compressor might strip details that are critical for downstream instructions.",
    "Tracking failures, state conflicts, or tool errors across windows can be difficult.",
    "Ensure sub-agents do not conflict by enforcing strict layout boundaries.",
    "Test whether the LLM succumbs to the context's factual errors or flags the contradiction.",
    "Ensure your RAG system remains robust when exposed to noisy, contradictory, or absent context.",
    "Smaller chunks improve specificity, whereas larger chunks provide better context.",
    "Measure precision and recall separately to spot a judge missing critical defects.",
    "This is especially critical for high-stakes environments.",
    "Avoid using this technique when queries require precise keyword lookups.",
    "Caveat: this adds latency and token cost overhead.",
]


@pytest.mark.parametrize("sentence", _REAL_FALSE_POSITIVES)
def test_caveat_and_domain_language_not_flagged(kb, sentence):
    write_play(kb, "p", title="P", caveats="Baseline caveat.")
    before = cl.snapshot(kb)
    write_play(kb, "p", title="P", caveats="Baseline caveat. " + sentence)
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="enrich.md")
    assert cs.contested == [], f"false positive on: {sentence!r}"


# Genuine inter-source contradictions (oppositional, anchored to a practice)
# that MUST still flag.
_GENUINE_CONTRADICTIONS = [
    "Mandating this as an absolute rule can become counterproductive dogma.",
    "This source contradicts the recommendation and argues the practice should be avoided.",
    "Contrary to the popular advice, some experts argue 1-5 Likert scales are counterproductive.",
    "This approach is now considered an anti-pattern by many practitioners.",
    "Recent guidance no longer recommends fine-tuning for this case.",
    "This finding supersedes the earlier recommendation to chunk by fixed size.",
]


@pytest.mark.parametrize("sentence", _GENUINE_CONTRADICTIONS)
def test_genuine_contradiction_flagged(kb, sentence):
    write_play(kb, "p", title="P", caveats="Baseline caveat.")
    before = cl.snapshot(kb)
    write_play(kb, "p", title="P", caveats="Baseline caveat. " + sentence)
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="contrarian.md")
    assert any(k == "concepts/p" for k, _ in cs.contested), f"missed: {sentence!r}"


def test_removed_play(kb):
    write_play(kb, "tdd", title="TDD")
    before = cl.snapshot(kb)
    (kb.plays_dir / "tdd.md").unlink()
    after = cl.snapshot(kb)

    cs = cl.diff(before, after, source="remove")
    assert cs.removed == ["concepts/tdd"]


def test_append_changelog_writes_md_and_json(kb):
    write_play(kb, "tdd", title="TDD")
    cs = cl.diff({}, cl.snapshot(kb), source="tdd.md")
    cl.append_changelog(kb, cs)

    md = kb.changelog_md.read_text(encoding="utf-8")
    assert "Added plays" in md
    assert "TDD" in md
    assert kb.changelog_json.exists()
