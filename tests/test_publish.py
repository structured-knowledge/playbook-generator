"""Web publish: snapshot artifact + readable play pages (offline).

Exercises the publisher without a browser — checks the output tree, plays.json
contract, wikilink rewriting/flattening, no duplicated structured sections, and
sidecar signals on the page.
"""
from __future__ import annotations

import json

from playmaker.publish import build_records, publish
from playmaker.sidecar import Sidecar
from tests.conftest import write_play


def test_publish_emits_pages_index_data_and_static(kb, tmp_path):
    write_play(kb, "alpha", title="Alpha")
    write_play(kb, "beta", title="Beta")

    out = tmp_path / "site"
    result = publish(kb, out)

    assert result.play_count == 2
    assert (out / "alpha.html").exists()
    assert (out / "beta.html").exists()
    assert (out / "index.html").exists()
    assert (out / "data" / "plays.json").exists()
    assert (out / "static" / "style.css").exists()
    assert (out / "static" / "vault-app.js").exists()

    index = (out / "index.html").read_text()
    # 3-pane vault app shell: taxonomy tree lists every play as a tax-item
    assert index.count('class="tax-item"') == 2
    assert 'id="app"' in index and 'id="taxonomy"' in index


def test_bundle_is_deploy_complete(kb, tmp_path):
    write_play(kb, "alpha", title="Alpha")
    out = tmp_path / "site"
    publish(kb, out)
    # the serverless function + the gate + deploy config all land in the bundle
    for rel in [
        "api/query.py",
        "middleware.js",
        "login.html",
        "vercel.json",
        "requirements.txt",
        "DEPLOY.md",
    ]:
        assert (out / rel).exists(), f"missing {rel}"


def test_plays_json_contract(kb, tmp_path):
    write_play(kb, "alpha", title="Alpha", kind="procedure", why="It compounds.")
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/alpha", "established")
    sc.save()

    publish(kb, tmp_path / "site")
    data = json.loads((tmp_path / "site" / "data" / "plays.json").read_text())
    rec = {r["key"]: r for r in data["plays"]}["concepts/alpha"]

    assert rec["title"] == "Alpha"
    assert rec["kind"] == "procedure"
    assert rec["why"] == "It compounds."
    assert rec["maturity"] == "established"
    assert rec["url"] == "alpha.html"
    # body is carried for search + the query function
    assert rec["body"]


def test_plays_json_carries_facets_and_examples(kb, tmp_path):
    write_play(kb, "alpha", title="Alpha", kind="procedure", why="It compounds.")
    write_play(kb, "beta", title="Beta", kind="principle")
    sc = Sidecar.load(kb.sidecar_path)
    sc.set_maturity("concepts/alpha", "established")
    sc.set_maturity("concepts/beta", "emerging")
    sc.save()

    publish(kb, tmp_path / "site")
    data = json.loads((tmp_path / "site" / "data" / "plays.json").read_text())

    # Additive: the plays array and its fields are unchanged.
    assert len(data["plays"]) == 2
    # Per-facet counts the index renders as chips.
    kinds = {f["value"]: f["count"] for f in data["facets"]["kind"]}
    assert kinds == {"procedure": 1, "principle": 1}
    # Maturity facet follows established-first order.
    assert [f["value"] for f in data["facets"]["maturity"]] == ["established", "emerging"]
    # Seeded questions are derived from the corpus.
    assert data["examples"]
    assert any("Alpha".lower() in q.lower() for q in data["examples"])


def test_wikilinks_rewritten_and_flattened(kb, tmp_path):
    # alpha mentions a real play (beta) and a non-play entity in its body + tools.
    write_play(
        kb, "alpha", title="Alpha",
        how="Pair it with [[concepts/beta]] and use [[entities/claude-code]].",
        tools="- coding agent (e.g., [[entities/claude-code]])",
    )
    write_play(kb, "beta", title="Beta")

    publish(kb, tmp_path / "site")
    page = (tmp_path / "site" / "alpha.html").read_text()

    assert "[[" not in page  # no raw wikilinks anywhere
    assert 'href="beta.html"' in page  # play target became a link
    assert "claude code" in page or "claude-code" in page  # entity flattened to text
    # the entity did NOT become a dead link
    assert 'href="entities/claude-code.html"' not in page


def test_structured_sections_not_duplicated(kb, tmp_path):
    write_play(kb, "alpha", title="Alpha", tools="- coding agent (e.g., Cursor)")
    publish(kb, tmp_path / "site")
    page = (tmp_path / "site" / "alpha.html").read_text()

    # Tools render once (structured), not also as a body heading.
    assert page.count("coding agent (e.g., Cursor)") == 1
    assert "<h2>Tools</h2>" in page


def test_sidecar_signals_render(kb, tmp_path):
    write_play(kb, "alpha", title="Alpha")
    sc = Sidecar.load(kb.sidecar_path)
    sc.mark_contested("concepts/alpha", reason="two sources disagree")
    sc.add_typed_link("concepts/alpha", "prerequisite", "concepts/beta")
    sc.save()
    write_play(kb, "beta", title="Beta")

    publish(kb, tmp_path / "site")
    page = (tmp_path / "site" / "alpha.html").read_text()

    assert "contested" in page  # badge + banner
    assert "prerequisite" in page  # typed link labeled
    assert 'href="beta.html"' in page  # typed-link target resolves
