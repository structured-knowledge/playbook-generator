"""playmaker — a self-maintaining playbook, built as a non-invasive superset
over VectifyAI OpenKB.

playmaker does not reimplement OpenKB's ingest/compile/query/lint engine. It
wraps it (see ``playmaker.engine``), steers it into producing *plays* via a
custom ``wiki/AGENTS.md`` (see ``playmaker.agents_md``), and owns the
playbook-specific concerns OpenKB lacks: a sidecar metadata store
(``playmaker.sidecar``) and an explicit conflict/changelog layer
(``playmaker.changelog``).
"""
from __future__ import annotations

__version__ = "0.1.0"

# The pinned OpenKB version playmaker is built and tested against. Upgrades are
# deliberate: bump this, bump the git tag in pyproject.toml, then re-run the
# smoke + e2e tests (design.md D1, tasks 1.1 / 6.3).
OPENKB_PIN = "v0.4.1"
