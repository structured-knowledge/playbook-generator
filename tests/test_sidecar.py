"""Sidecar: maturity, typed links, contested flags, reconciliation, repair."""
from __future__ import annotations

import pytest

from playmaker.sidecar import Sidecar, SidecarError


def test_maturity_roundtrip(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/tdd", "established")
    sc.save()

    reloaded = Sidecar.load(kb.sidecar_path)
    assert reloaded.get_maturity("concepts/tdd") == "established"


def test_maturity_rejects_bad_value(kb):
    sc = Sidecar.load(kb.sidecar_path)
    with pytest.raises(SidecarError):
        sc.set_maturity("concepts/tdd", "rock-solid")


def test_typed_links_distinct_and_idempotent(kb):
    sc = Sidecar.load(kb.sidecar_path)
    assert sc.add_typed_link("concepts/a", "prerequisite", "concepts/b") is True
    # second identical assertion is a no-op
    assert sc.add_typed_link("concepts/a", "prerequisite", "concepts/b") is False
    sc.add_typed_link("concepts/a", "counters", "concepts/c")
    links = sc.typed_links("concepts/a")
    assert {(l["type"], l["target"]) for l in links} == {
        ("prerequisite", "concepts/b"),
        ("counters", "concepts/c"),
    }


def test_typed_link_rejects_bad_type_and_self_link(kb):
    sc = Sidecar.load(kb.sidecar_path)
    with pytest.raises(SidecarError):
        sc.add_typed_link("concepts/a", "see-also", "concepts/b")
    with pytest.raises(SidecarError):
        sc.add_typed_link("concepts/a", "prerequisite", "concepts/a")


def test_contested_flag_and_resolve(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.mark_contested("concepts/a", reason="new source disagrees", source="x.md")
    assert sc.is_contested("concepts/a")
    assert sc.contested_keys() == ["concepts/a"]

    assert sc.resolve_contested("concepts/a", note="kept original") is True
    assert not sc.is_contested("concepts/a")
    # resolution is recorded, not lost
    assert sc.get("concepts/a")["resolutions"][0]["note"] == "kept original"
    # resolving a non-contested play is a no-op
    assert sc.resolve_contested("concepts/a") is False


def test_reconcile_orphans_then_restores(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/gone", "emerging")

    # page does not exist -> orphaned, metadata preserved
    result = sc.reconcile(current_keys=set())
    assert result["orphaned"] == ["concepts/gone"]
    assert sc.orphaned_keys() == ["concepts/gone"]
    assert sc.get_maturity("concepts/gone") == "emerging"

    # page reappears -> restored
    result = sc.reconcile(current_keys={"concepts/gone"})
    assert result["restored"] == ["concepts/gone"]
    assert sc.orphaned_keys() == []


def test_repair_moves_metadata_and_merges_links(kb):
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/old", "established")
    sc.add_typed_link("concepts/old", "prerequisite", "concepts/x")
    sc.add_typed_link("concepts/new", "alternative", "concepts/y")

    sc.repair("concepts/old", "concepts/new")

    assert "concepts/old" not in sc.plays
    assert sc.get_maturity("concepts/new") == "established"
    pairs = {(l["type"], l["target"]) for l in sc.typed_links("concepts/new")}
    assert pairs == {("prerequisite", "concepts/x"), ("alternative", "concepts/y")}


def test_repair_missing_source_raises(kb):
    sc = Sidecar.load(kb.sidecar_path)
    with pytest.raises(SidecarError):
        sc.repair("concepts/nope", "concepts/new")
