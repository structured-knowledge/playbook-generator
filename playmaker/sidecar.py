"""playmaker's sidecar metadata store.

OpenKB manages page frontmatter in code and forbids LLM-authored frontmatter,
so playmaker keeps the playbook-specific fields OpenKB does not manage in a
sidecar that lives *outside* OpenKB's directories (``.playmaker/plays-meta.json``)
and is never touched by the engine (design.md D3; spec: play-metadata-sidecar).

Held per play (keyed by ``concepts/<slug>``):
- **maturity** — human-set: experimental | emerging | established.
- **typed links** — human-asserted: prerequisite | alternative | counters,
  kept distinct from OpenKB's automatic ``[[wikilinks]]``.
- **contested** — set by the conflict layer (changelog.py) and cleared by
  ``resolve-conflict``.
- **orphaned** — set by reconciliation when the play's page disappears, so
  metadata is preserved rather than lost.

Open question resolved (design.md): single JSON file, keyed by the wikilink
target path. JSON is atomic to write, trivial to reconcile, and has no per-play
file sprawl.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1

MATURITY_VALUES = ("experimental", "emerging", "established")
LINK_TYPES = ("prerequisite", "alternative", "counters")


class SidecarError(ValueError):
    """Invalid sidecar input (bad maturity value, link type, etc.)."""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Sidecar:
    """In-memory view of ``.playmaker/plays-meta.json``.

    The on-disk shape is ``{"schema_version": N, "plays": {key: entry}}`` where
    each entry may carry ``maturity``, ``typed_links``, ``contested``,
    ``orphaned``, and bookkeeping timestamps.
    """

    path: Path
    plays: dict[str, dict]

    # --- load / save ---
    @classmethod
    def load(cls, path: Path) -> "Sidecar":
        if Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            plays = data.get("plays", {}) if isinstance(data, dict) else {}
        else:
            plays = {}
        return cls(path=Path(path), plays=plays)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": SCHEMA_VERSION, "plays": self.plays}
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        # Atomic write: temp file in the same dir + os.replace.
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _entry(self, key: str) -> dict:
        return self.plays.setdefault(key, {})

    def get(self, key: str) -> dict:
        return self.plays.get(key, {})

    # --- maturity ---
    def set_maturity(self, key: str, maturity: str) -> None:
        maturity = maturity.strip().lower()
        if maturity not in MATURITY_VALUES:
            raise SidecarError(
                f"maturity must be one of {', '.join(MATURITY_VALUES)}; got '{maturity}'"
            )
        entry = self._entry(key)
        entry["maturity"] = maturity
        entry["maturity_set_at"] = _now()

    def get_maturity(self, key: str) -> str | None:
        return self.get(key).get("maturity")

    # --- typed links ---
    def add_typed_link(self, source_key: str, link_type: str, target_key: str) -> bool:
        """Assert ``source --link_type--> target``. Returns False if it already
        existed (idempotent). Typed links are stored on the source play."""
        link_type = link_type.strip().lower()
        if link_type not in LINK_TYPES:
            raise SidecarError(
                f"link type must be one of {', '.join(LINK_TYPES)}; got '{link_type}'"
            )
        if source_key == target_key:
            raise SidecarError("a play cannot link to itself")
        entry = self._entry(source_key)
        links = entry.setdefault("typed_links", [])
        for link in links:
            if link.get("type") == link_type and link.get("target") == target_key:
                return False
        links.append({"type": link_type, "target": target_key, "asserted_at": _now()})
        return True

    def remove_typed_link(self, source_key: str, link_type: str, target_key: str) -> bool:
        links = self.get(source_key).get("typed_links", [])
        before = len(links)
        kept = [
            l for l in links
            if not (l.get("type") == link_type and l.get("target") == target_key)
        ]
        if kept != links:
            self._entry(source_key)["typed_links"] = kept
        return len(kept) != before

    def typed_links(self, key: str) -> list[dict]:
        return list(self.get(key).get("typed_links", []))

    # --- contested / conflict ---
    def mark_contested(self, key: str, *, reason: str, source: str | None = None) -> None:
        entry = self._entry(key)
        entry["contested"] = {
            "reason": reason,
            "source": source,
            "flagged_at": _now(),
        }

    def is_contested(self, key: str) -> bool:
        return bool(self.get(key).get("contested"))

    def contested_keys(self) -> list[str]:
        return [k for k, e in self.plays.items() if e.get("contested")]

    def resolve_contested(self, key: str, *, note: str | None = None) -> bool:
        entry = self.get(key)
        if not entry.get("contested"):
            return False
        flagged = entry.pop("contested")
        resolutions = entry.setdefault("resolutions", [])
        resolutions.append(
            {"resolved_at": _now(), "note": note, "was": flagged}
        )
        return True

    # --- reconciliation ---
    def reconcile(self, current_keys: set[str]) -> dict[str, list[str]]:
        """Reconcile sidecar entries against the plays that exist on disk.

        Entries whose play key is no longer present are marked ``orphaned``
        (rather than deleted) so human-set metadata survives an OpenKB
        rename/remove. Entries that reappear are un-orphaned. Returns
        ``{"orphaned": [...], "restored": [...]}`` describing what changed.
        """
        orphaned: list[str] = []
        restored: list[str] = []
        for key, entry in self.plays.items():
            present = key in current_keys
            was_orphaned = bool(entry.get("orphaned"))
            if not present and not was_orphaned:
                entry["orphaned"] = {"since": _now()}
                orphaned.append(key)
            elif present and was_orphaned:
                entry.pop("orphaned", None)
                restored.append(key)
        return {"orphaned": orphaned, "restored": restored}

    def orphaned_keys(self) -> list[str]:
        return [k for k, e in self.plays.items() if e.get("orphaned")]

    def repair(self, old_key: str, new_key: str) -> None:
        """Re-point a play's metadata from ``old_key`` to ``new_key`` (e.g.
        after OpenKB renamed a page). Merges into any existing new entry,
        preferring existing new values, and drops the orphaned flag."""
        if old_key not in self.plays:
            raise SidecarError(f"no sidecar entry for '{old_key}'")
        old = self.plays.pop(old_key)
        old.pop("orphaned", None)
        if new_key in self.plays:
            merged = {**old, **self.plays[new_key]}
            # Concatenate typed_links from both, de-duped.
            links = old.get("typed_links", []) + self.plays[new_key].get("typed_links", [])
            seen, deduped = set(), []
            for l in links:
                sig = (l.get("type"), l.get("target"))
                if sig not in seen:
                    seen.add(sig)
                    deduped.append(l)
            if deduped:
                merged["typed_links"] = deduped
            merged.pop("orphaned", None)
            self.plays[new_key] = merged
        else:
            self.plays[new_key] = old
