"""Knowledge-base layout and discovery.

playmaker operates one OpenKB knowledge base per domain instance (spec:
openkb-foundation / "Per-instance KB layout"). The on-disk layout is OpenKB's,
plus a playmaker-owned ``.playmaker/`` directory that lives *outside* OpenKB's
managed directories so the engine never touches it (design.md D3).

    <kb-root>/
    ├── raw/                     OpenKB: original ingested files
    ├── wiki/                    OpenKB: the compiled playbook
    │   ├── AGENTS.md            playmaker: the play-shaped compiler prompt
    │   ├── concepts/<slug>.md   the PLAYS (OpenKB calls them "concepts")
    │   ├── log.md               OpenKB: thin ingest|filename log
    │   └── ...
    ├── .openkb/                 OpenKB: config.yaml, hashes.json, pageindex.db
    └── .playmaker/              playmaker: sidecar + changelog (engine never writes here)
        ├── plays-meta.json
        └── changelog.md
"""
from __future__ import annotations

from pathlib import Path

# OpenKB-owned markers / directories (we read but never restructure these).
OPENKB_STATE_DIR = ".openkb"
WIKI_DIR = "wiki"
RAW_DIR = "raw"
# Plays physically live in OpenKB's concept directory — they ARE concept pages,
# reshaped by AGENTS.md (design.md D2). Cosmetic naming only.
PLAYS_DIR = "concepts"

# playmaker-owned, outside OpenKB's directories.
PLAYMAKER_DIR = ".playmaker"
SIDECAR_FILE = "plays-meta.json"
CHANGELOG_FILE = "changelog.md"
CHANGELOG_JSON = "changelog.json"


class KB:
    """Resolved paths for a single playmaker/OpenKB instance."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    # --- OpenKB-owned ---
    @property
    def openkb_dir(self) -> Path:
        return self.root / OPENKB_STATE_DIR

    @property
    def config_path(self) -> Path:
        return self.openkb_dir / "config.yaml"

    @property
    def wiki(self) -> Path:
        return self.root / WIKI_DIR

    @property
    def plays_dir(self) -> Path:
        return self.wiki / PLAYS_DIR

    @property
    def agents_md(self) -> Path:
        return self.wiki / "AGENTS.md"

    @property
    def log_md(self) -> Path:
        return self.wiki / "log.md"

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    # --- playmaker-owned ---
    @property
    def playmaker_dir(self) -> Path:
        return self.root / PLAYMAKER_DIR

    @property
    def sidecar_path(self) -> Path:
        return self.playmaker_dir / SIDECAR_FILE

    @property
    def changelog_md(self) -> Path:
        return self.playmaker_dir / CHANGELOG_FILE

    @property
    def changelog_json(self) -> Path:
        return self.playmaker_dir / CHANGELOG_JSON

    def is_initialized(self) -> bool:
        return self.openkb_dir.is_dir()


def find_kb(start: Path | None = None) -> KB | None:
    """Find the enclosing KB by walking up from ``start`` (default: cwd).

    Mirrors OpenKB's discovery: a directory is a KB root iff it has a
    ``.openkb/`` subdirectory.
    """
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / OPENKB_STATE_DIR).is_dir():
            return KB(current)
        parent = current.parent
        if parent == current:
            return None
        current = parent
