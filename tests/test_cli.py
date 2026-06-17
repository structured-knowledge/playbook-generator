"""CLI: curation commands, the play-shaped view, reconcile — all engine-free."""
from __future__ import annotations

from click.testing import CliRunner

from tests.conftest import write_play

from playmaker.cli import cli
from playmaker.sidecar import Sidecar


def _run(kb, *args):
    return CliRunner().invoke(cli, ["--kb-dir", str(kb.root), *args])


def test_set_maturity_writes_sidecar(kb):
    write_play(kb, "tdd", title="TDD")
    r = _run(kb, "set-maturity", "tdd", "established")
    assert r.exit_code == 0, r.output
    assert Sidecar.load(kb.sidecar_path).get_maturity("concepts/tdd") == "established"


def test_assert_link(kb):
    r = _run(kb, "assert-link", "a", "prerequisite", "b")
    assert r.exit_code == 0, r.output
    links = Sidecar.load(kb.sidecar_path).typed_links("concepts/a")
    assert links[0]["type"] == "prerequisite"
    assert links[0]["target"] == "concepts/b"


def test_assert_link_rejects_bad_type(kb):
    r = _run(kb, "assert-link", "a", "see-also", "b")
    assert r.exit_code != 0


def test_conflicts_and_resolve(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.mark_contested("concepts/tdd", reason="disagreement", source="x.md")
    sc.save()

    r = _run(kb, "conflicts")
    assert "concepts/tdd" in r.output

    r = _run(kb, "resolve-conflict", "tdd", "--note", "kept original")
    assert r.exit_code == 0, r.output
    assert not Sidecar.load(kb.sidecar_path).is_contested("concepts/tdd")


def test_plays_view_filters(kb):
    write_play(kb, "tdd", title="TDD", kind="procedure",
               tools="- coding agent (e.g., Claude Code)")
    write_play(kb, "pairing", title="Pair Programming", kind="technique",
               tools="- whiteboard")
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/tdd", "established")
    sc.save()

    # filter by kind
    r = _run(kb, "plays", "--kind", "procedure")
    assert "TDD" in r.output and "Pair Programming" not in r.output

    # filter by tool category
    r = _run(kb, "plays", "--tool", "coding agent")
    assert "TDD" in r.output and "Pair Programming" not in r.output

    # filter by maturity
    r = _run(kb, "plays", "--maturity", "established")
    assert "TDD" in r.output and "Pair Programming" not in r.output


def test_reconcile_orphans_missing_page(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/ghost", "emerging")  # no page on disk
    sc.save()

    r = _run(kb, "reconcile")
    assert r.exit_code == 0, r.output
    assert "concepts/ghost" in r.output
    assert Sidecar.load(kb.sidecar_path).orphaned_keys() == ["concepts/ghost"]


def test_reconcile_repair(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/old", "established")
    sc.save()

    r = _run(kb, "reconcile", "--repair", "old", "new")
    assert r.exit_code == 0, r.output
    reloaded = Sidecar.load(kb.sidecar_path)
    assert reloaded.get_maturity("concepts/new") == "established"
    assert "concepts/old" not in reloaded.plays


def test_no_kb_errors_cleanly(tmp_path):
    r = CliRunner().invoke(cli, ["--kb-dir", str(tmp_path / "nope"), "conflicts"])
    assert r.exit_code != 0
    assert "No playmaker instance" in r.output
