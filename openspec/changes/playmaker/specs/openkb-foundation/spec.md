## ADDED Requirements

### Requirement: OpenKB as the underlying engine
playmaker SHALL use OpenKB (installed from its GitHub source, not the PyPI `openkb` placeholder) as the engine for ingest, compile, query, lint, enrichment, and dedup, and SHALL pin a specific OpenKB version.

#### Scenario: Engine operations are provided by OpenKB
- **WHEN** playmaker ingests a source or answers a query
- **THEN** it does so by invoking OpenKB rather than a reimplemented pipeline

#### Scenario: Pinned version
- **WHEN** playmaker is installed
- **THEN** a specific pinned OpenKB version is resolved, and upgrades are deliberate

### Requirement: Per-instance KB layout
playmaker SHALL operate one OpenKB knowledge base per domain instance, owning the data directory (wiki, sources, OpenKB state, and the playmaker sidecar).

#### Scenario: One instance per domain
- **WHEN** a new domain playbook is created
- **THEN** a separate OpenKB KB directory is initialized for it

### Requirement: LiteLLM gateway configuration
playmaker SHALL configure the LLM via a LiteLLM-compatible gateway: an `openai/<model>` model id, the base URL via `OPENAI_API_BASE`, the key via `LLM_API_KEY`, and any required HTTP headers via `config.yaml` `extra_headers`.

#### Scenario: Gateway User-Agent requirement
- **WHEN** the gateway rejects LiteLLM's default User-Agent
- **THEN** playmaker sets a `User-Agent` (and any other required headers) in `extra_headers`, and compilation succeeds

#### Scenario: Base URL supplied to the engine
- **WHEN** OpenKB makes an LLM call
- **THEN** it reaches the configured gateway base URL with the configured key

### Requirement: Adopt OpenKB's state model
playmaker SHALL rely on OpenKB's state model — a content-hash registry for source-level dedup and an append-only operation log — and SHALL NOT introduce git-as-truth or a vector database in v1.

#### Scenario: No git or vector DB required
- **WHEN** playmaker runs
- **THEN** it functions without a git repository or an embeddings index, using OpenKB's hash registry and log
