"""End-to-end of the playmaker *layer* (task 6.1 / 6.2), minus the live LLM.

The live ingest (OpenKB compile) is exercised by scripts/smoke_test.py with
real credentials. Here we simulate the wiki state OpenKB would produce and
assert the playmaker layer's guarantees: enrich-in-place (no duplicate),
provenance accumulation, maturity, typed links, conflict flag/resolve, and
reconciliation when a page is removed/renamed.
"""
from __future__ import annotations

from tests.conftest import write_play

from playmaker import changelog as cl
from playmaker.sidecar import Sidecar
from playmaker.wiki import play_keys


def _simulate_ingest(kb, source, mutate):
    """Mirror cli.ingest: snapshot, mutate the wiki, diff, reconcile, flag."""
    before = cl.snapshot(kb)
    mutate()
    after = cl.snapshot(kb)
    cs = cl.diff(before, after, source=source)

    sc = Sidecar.load(kb.sidecar_path)
    sc.reconcile(play_keys(kb))
    for key, reason in cs.contested:
        sc.mark_contested(key, reason=reason, source=source)
    sc.save()
    cl.append_changelog(kb, cs)
    return cs


def test_full_layer_flow(kb):
    # 1) ingest source -> one new play
    cs = _simulate_ingest(
        kb, "source-a.md",
        lambda: write_play(kb, "tdd", title="TDD", sources="summaries/a.md",
                           how="Write a failing test."),
    )
    assert cs.added == ["concepts/tdd"]

    # 2) ingest overlapping source -> enrich in place, no duplicate, +provenance
    cs = _simulate_ingest(
        kb, "source-b.md",
        lambda: write_play(kb, "tdd", title="TDD",
                           sources="summaries/a.md, summaries/b.md",
                           how="Write a failing test, then minimal code, then refactor."),
    )
    assert cs.added == []
    assert cs.enriched == ["concepts/tdd"]
    assert cs.sources_added["concepts/tdd"] == ["summaries/b.md"]
    assert len(play_keys(kb)) == 1  # no duplicate page

    # 3) set maturity + assert a typed link
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/tdd", "established")
    sc.add_typed_link("concepts/tdd", "prerequisite", "concepts/version-control")
    sc.save()

    # 4) ingest a contradicting source -> contested flag surfaced
    cs = _simulate_ingest(
        kb, "contrarian.md",
        lambda: write_play(kb, "tdd", title="TDD",
                           sources="summaries/a.md, summaries/b.md, summaries/c.md",
                           caveats="However, this source contradicts the practice "
                                   "and argues it should be avoided for spikes."),
    )
    sc = Sidecar.load(kb.sidecar_path)
    assert sc.is_contested("concepts/tdd")
    # maturity + typed link survived the contradicting ingest
    assert sc.get_maturity("concepts/tdd") == "established"
    assert sc.typed_links("concepts/tdd")

    # 5) resolve the conflict
    assert sc.resolve_contested("concepts/tdd", note="kept; noted the exception") is True
    sc.save()
    assert not Sidecar.load(kb.sidecar_path).is_contested("concepts/tdd")


def test_reconcile_when_page_removed(kb):
    write_play(kb, "tdd", title="TDD")
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/tdd", "established")
    sc.save()

    # OpenKB removes the page
    (kb.plays_dir / "tdd.md").unlink()
    sc = Sidecar.load(kb.sidecar_path)
    result = sc.reconcile(play_keys(kb))
    sc.save()

    assert result["orphaned"] == ["concepts/tdd"]
    # metadata preserved, not lost
    assert Sidecar.load(kb.sidecar_path).get_maturity("concepts/tdd") == "established"


def test_reconcile_when_page_renamed(kb):
    write_play(kb, "tdd", title="TDD")
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/tdd", "established")
    sc.save()

    # OpenKB renames the page: tdd.md -> test-driven-development.md
    (kb.plays_dir / "tdd.md").rename(kb.plays_dir / "test-driven-development.md")
    sc = Sidecar.load(kb.sidecar_path)
    sc.reconcile(play_keys(kb))  # old key orphaned, new key present but bare
    sc.repair("concepts/tdd", "concepts/test-driven-development")
    sc.save()

    reloaded = Sidecar.load(kb.sidecar_path)
    assert reloaded.get_maturity("concepts/test-driven-development") == "established"
    assert "concepts/tdd" not in reloaded.plays
