"""playmaker's read-side web publisher.

A triggered, local, read-only snapshot of the vault into a deployable static
site (one readable page per play + an index) plus a ``plays.json`` data file —
the contract consumed by client-side search and the AI query function. The UI is
a snapshot, not synchronized with the vault (openspec: add-web-publish).
"""
from playmaker.publish.builder import PublishResult, build_records, publish

__all__ = ["publish", "build_records", "PublishResult"]
