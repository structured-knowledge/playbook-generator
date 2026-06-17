"""The playmaker command surface.

Wraps OpenKB's ingest/query/lint (presenting results in *play* terms with a
changelog), and adds the play-specific curation and views OpenKB lacks
(spec: playmaker-cli). Single-user, no auth.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from playmaker import __version__
from playmaker import changelog as changelog_mod
from playmaker import engine
from playmaker.agents_md import install_agents_md
from playmaker.paths import KB, PLAYS_DIR, find_kb
from playmaker.sidecar import (
    LINK_TYPES,
    MATURITY_VALUES,
    Sidecar,
    SidecarError,
)
from playmaker.wiki import VALID_KINDS, list_plays, play_keys

_TEMPLATES = Path(__file__).parent / "templates"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _require_kb(ctx) -> KB:
    override = ctx.obj.get("kb_dir")
    kb = KB(override) if override else find_kb()
    if kb is None or not kb.is_initialized():
        raise click.ClickException(
            "No playmaker instance found. Run `playmaker init` first "
            "(or pass --kb-dir)."
        )
    return kb


def _normalize_key(value: str) -> str:
    """Accept a slug (``tdd``) or a full key (``concepts/tdd``); normalize to
    the wikilink-target form ``concepts/<slug>``."""
    value = value.strip().strip("[]")
    if "/" in value:
        return value
    return f"{PLAYS_DIR}/{value}"


def _reconcile_sidecar(kb: KB) -> dict:
    """Reconcile the sidecar against plays on disk; persist if anything moved."""
    sidecar = Sidecar.load(kb.sidecar_path)
    result = sidecar.reconcile(play_keys(kb))
    if result["orphaned"] or result["restored"]:
        sidecar.save()
    return result


# --------------------------------------------------------------------------
# root
# --------------------------------------------------------------------------

@click.group()
@click.version_option(__version__, prog_name="playmaker")
@click.option(
    "--kb-dir", "kb_dir", default=None,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Path to a playmaker instance root (overrides auto-detection).",
)
@click.pass_context
def cli(ctx, kb_dir):
    """playmaker — a self-maintaining playbook over OpenKB."""
    ctx.ensure_object(dict)
    ctx.obj["kb_dir"] = kb_dir


# --------------------------------------------------------------------------
# Section 1 — bootstrap
# --------------------------------------------------------------------------

@cli.command()
@click.argument("path", default=".")
@click.option("--model", "-m", default=None, help="LiteLLM model id, e.g. openai/<model>.")
@click.option("--language", "-l", default="en", help="Wiki output language.")
@click.pass_context
def init(ctx, path, model, language):
    """Initialize a playmaker instance (one per domain) at PATH.

    Runs `openkb init`, installs the play-shaped AGENTS.md, drops in the
    gateway config + .env.example templates, and creates the sidecar.
    """
    kb = KB(Path(path))
    if kb.is_initialized():
        raise click.ClickException(f"Already a knowledge base: {kb.root}")

    click.echo(f"Initializing playmaker instance at {kb.root}")
    engine.init(kb.root, model=model, language=language)

    # Steer the compiler into producing plays.
    install_agents_md(kb.agents_md, force=True)
    click.echo("  Installed play-shaped wiki/AGENTS.md")

    # Gateway config + env template (the user edits model + secrets).
    template_cfg = (_TEMPLATES / "config.yaml").read_text(encoding="utf-8")
    if model:
        template_cfg = template_cfg.replace("openai/<model>", model)
    kb.config_path.write_text(template_cfg, encoding="utf-8")
    (kb.root / ".env.example").write_text(
        (_TEMPLATES / "env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    click.echo("  Wrote gateway config (.openkb/config.yaml) + .env.example")

    # Sidecar.
    Sidecar.load(kb.sidecar_path).save()
    click.echo("  Created sidecar (.playmaker/plays-meta.json)")

    click.echo(
        "\nNext: copy .env.example to .env and fill in LLM_API_KEY + "
        "OPENAI_API_BASE, set the model in .openkb/config.yaml, then "
        "`playmaker ingest <source>`."
    )


# --------------------------------------------------------------------------
# Section 5.1 — wrapped engine operations
# --------------------------------------------------------------------------

@cli.command()
@click.argument("source")
@click.pass_context
def ingest(ctx, source):
    """Ingest a SOURCE (file, directory, or URL) and report what changed."""
    kb = _require_kb(ctx)

    before = changelog_mod.snapshot(kb)
    engine.add(kb, source, stream=True)
    after = changelog_mod.snapshot(kb)

    cs = changelog_mod.diff(before, after, source=source)

    # Reconcile the sidecar (a removal/rename during ingest must not lose
    # metadata) and surface contested plays into the sidecar.
    sidecar = Sidecar.load(kb.sidecar_path)
    sidecar.reconcile(play_keys(kb))
    for key, reason in cs.contested:
        sidecar.mark_contested(key, reason=reason, source=source)
    sidecar.save()

    changelog_mod.append_changelog(kb, cs)

    click.echo("\n" + changelog_mod.render_markdown(cs).rstrip())
    if cs.contested:
        click.echo(
            "\nReview contested plays with `playmaker conflicts`, then "
            "`playmaker resolve-conflict <play>`."
        )


@cli.command()
@click.argument("question")
@click.option("--save", is_flag=True, default=False, help="Save the answer to wiki/explorations/.")
@click.pass_context
def query(ctx, question, save):
    """Ask the playbook QUESTION; returns a grounded answer with citations."""
    kb = _require_kb(ctx)
    result = engine.query(kb, question, save=save)
    click.echo(result.stdout.rstrip() or result.stderr.rstrip())


@cli.command()
@click.pass_context
def lint(ctx):
    """Run OpenKB's health checks, then reconcile the sidecar."""
    kb = _require_kb(ctx)
    engine.lint(kb, stream=True)
    result = _reconcile_sidecar(kb)
    if result["orphaned"]:
        click.echo(f"\nSidecar: {len(result['orphaned'])} entry(ies) orphaned (page gone).")
    if result["restored"]:
        click.echo(f"Sidecar: {len(result['restored'])} entry(ies) restored.")


# --------------------------------------------------------------------------
# Section 5.2 — curation commands
# --------------------------------------------------------------------------

@cli.command(name="set-maturity")
@click.argument("play")
@click.argument("maturity", type=click.Choice(MATURITY_VALUES))
@click.pass_context
def set_maturity(ctx, play, maturity):
    """Set PLAY's maturity (experimental | emerging | established)."""
    kb = _require_kb(ctx)
    key = _normalize_key(play)
    if key not in play_keys(kb):
        click.echo(f"Warning: no play page found at '{key}' (setting anyway).", err=True)
    sidecar = Sidecar.load(kb.sidecar_path)
    sidecar.set_maturity(key, maturity)
    sidecar.save()
    click.echo(f"Set maturity of {key} = {maturity}")


@cli.command(name="assert-link")
@click.argument("source")
@click.argument("link_type", type=click.Choice(LINK_TYPES))
@click.argument("target")
@click.pass_context
def assert_link(ctx, source, link_type, target):
    """Assert a typed link: SOURCE --LINK_TYPE--> TARGET.

    LINK_TYPE is prerequisite | alternative | counters. Typed links are
    human-asserted and kept distinct from OpenKB's automatic wikilinks.
    """
    kb = _require_kb(ctx)
    src_key = _normalize_key(source)
    tgt_key = _normalize_key(target)
    sidecar = Sidecar.load(kb.sidecar_path)
    try:
        added = sidecar.add_typed_link(src_key, link_type, tgt_key)
    except SidecarError as exc:
        raise click.ClickException(str(exc))
    sidecar.save()
    if added:
        click.echo(f"Asserted: {src_key} --{link_type}--> {tgt_key}")
    else:
        click.echo("That typed link already exists.")


@cli.command()
@click.pass_context
def conflicts(ctx):
    """List plays currently flagged as contested."""
    kb = _require_kb(ctx)
    sidecar = Sidecar.load(kb.sidecar_path)
    contested = sidecar.contested_keys()
    if not contested:
        click.echo("No contested plays.")
        return
    click.echo(f"{len(contested)} contested play(s):")
    for key in contested:
        info = sidecar.get(key).get("contested", {})
        click.echo(f"  - {key}")
        click.echo(f"      reason: {info.get('reason', '?')}")
        if info.get("source"):
            click.echo(f"      source: {info['source']}")
        click.echo(f"      flagged: {info.get('flagged_at', '?')}")


@cli.command(name="resolve-conflict")
@click.argument("play")
@click.option("--note", default=None, help="A note recording how it was resolved.")
@click.pass_context
def resolve_conflict(ctx, play, note):
    """Clear the contested flag on PLAY and record the resolution."""
    kb = _require_kb(ctx)
    key = _normalize_key(play)
    sidecar = Sidecar.load(kb.sidecar_path)
    if sidecar.resolve_contested(key, note=note):
        sidecar.save()
        click.echo(f"Resolved conflict on {key}.")
    else:
        click.echo(f"{key} is not flagged as contested.")


# --------------------------------------------------------------------------
# Section 3.4 / 6.2 — reconciliation surface
# --------------------------------------------------------------------------

@cli.command()
@click.option(
    "--repair", nargs=2, default=None, metavar="OLD NEW",
    help="Move sidecar metadata from play key OLD to NEW (e.g. after a rename).",
)
@click.pass_context
def reconcile(ctx, repair):
    """Reconcile sidecar entries against plays on disk (orphan/repair)."""
    kb = _require_kb(ctx)
    sidecar = Sidecar.load(kb.sidecar_path)
    if repair:
        old, new = _normalize_key(repair[0]), _normalize_key(repair[1])
        try:
            sidecar.repair(old, new)
        except SidecarError as exc:
            raise click.ClickException(str(exc))
        sidecar.save()
        click.echo(f"Repaired: moved metadata {old} → {new}")
        return
    result = sidecar.reconcile(play_keys(kb))
    sidecar.save()
    click.echo(
        f"Reconciled: {len(result['orphaned'])} orphaned, "
        f"{len(result['restored'])} restored."
    )
    orphans = sidecar.orphaned_keys()
    if orphans:
        click.echo("Orphaned entries (metadata preserved):")
        for k in orphans:
            click.echo(f"  - {k}  (repair with `playmaker reconcile --repair {k} <new-key>`)")


# --------------------------------------------------------------------------
# Section 5.3 — play-shaped view
# --------------------------------------------------------------------------

@cli.command(name="plays")
@click.option("--kind", type=click.Choice(VALID_KINDS), default=None, help="Filter by Kind.")
@click.option("--tool", default=None, help="Filter by tool category substring.")
@click.option("--maturity", type=click.Choice(MATURITY_VALUES), default=None, help="Filter by maturity.")
@click.pass_context
def plays_cmd(ctx, kind, tool, maturity):
    """List plays, merging the play body with sidecar metadata.

    Filter by Kind, tool category, and/or maturity.
    """
    kb = _require_kb(ctx)
    sidecar = Sidecar.load(kb.sidecar_path)
    plays = list_plays(kb)

    rows = []
    for play in plays:
        mat = sidecar.get_maturity(play.key)
        if kind and (play.kind or "").lower() != kind:
            continue
        if maturity and mat != maturity:
            continue
        if tool and not any(tool.lower() in tc.lower() for tc in play.tool_categories):
            continue
        rows.append((play, mat))

    if not rows:
        click.echo("No plays match.")
        return

    # Order by maturity (established first), then title.
    order = {m: i for i, m in enumerate(reversed(MATURITY_VALUES))}
    rows.sort(key=lambda r: (order.get(r[1], 99), r[0].title.lower()))

    for play, mat in rows:
        tags = []
        if play.kind:
            tags.append(play.kind)
        if mat:
            tags.append(mat)
        if sidecar.is_contested(play.key):
            tags.append("⚠ contested")
        tagstr = f"  [{', '.join(tags)}]" if tags else ""
        click.echo(f"- {play.title}  (`{play.key}`){tagstr}")
        if play.why:
            click.echo(f"    why: {play.why}")
        for link in sidecar.typed_links(play.key):
            click.echo(f"    {link['type']} → {link['target']}")


def main() -> int:
    cli()
    return 0


if __name__ == "__main__":
    sys.exit(main())
