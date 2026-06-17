## ADDED Requirements

### Requirement: Explicit conflict flagging
playmaker SHALL detect when an ingest introduces guidance that contradicts an existing play and SHALL surface the contested play for human attention, beyond OpenKB's silent reconciliation.

#### Scenario: Contradiction is surfaced
- **WHEN** a new source contradicts an existing play
- **THEN** playmaker marks the affected play as contested and makes it visible to the user

### Requirement: Per-changeset changelog
playmaker SHALL produce a human-readable summary for each ingest, describing what changed (plays added, plays enriched, links created), richer than OpenKB's `ingest | filename` log entry.

#### Scenario: Ingest summary
- **WHEN** a source is ingested and compiled
- **THEN** a changelog entry summarizes the counts and names of plays added, enriched, and linked

#### Scenario: Enrichment is reflected as enrichment
- **WHEN** an ingest updates an existing play rather than creating one
- **THEN** the changelog reports it as an enrichment of that play, not a new play
