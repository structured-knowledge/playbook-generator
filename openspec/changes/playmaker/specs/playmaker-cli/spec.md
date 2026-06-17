## ADDED Requirements

### Requirement: Wrap engine operations
The playmaker CLI SHALL expose ingest, query, and lint by invoking OpenKB, presenting results in playmaker terms (plays, changelog).

#### Scenario: Ingest via playmaker
- **WHEN** the user runs the playmaker ingest command with a source
- **THEN** OpenKB compiles it and playmaker reports the per-changeset summary

#### Scenario: Query via playmaker
- **WHEN** the user asks a question
- **THEN** playmaker returns a synthesized answer citing the plays used

### Requirement: Play curation commands
The playmaker CLI SHALL provide commands to set a play's maturity, assert a typed link, and resolve a flagged conflict, all writing to the sidecar.

#### Scenario: Set maturity from the CLI
- **WHEN** the user sets a play's maturity
- **THEN** the sidecar is updated for that play

#### Scenario: Resolve a flagged conflict
- **WHEN** the user resolves a contested play
- **THEN** playmaker clears the contested flag and records the resolution

### Requirement: Play-shaped query/view
The playmaker CLI SHALL support filtering/listing plays by play attributes — Kind, tool category, and sidecar maturity.

#### Scenario: Filter by tool category and maturity
- **WHEN** the user lists plays involving a "coding agent" ordered by maturity
- **THEN** playmaker returns matching plays using the play body and sidecar metadata

### Requirement: Single-user, no auth
The playmaker CLI SHALL operate as a single-user tool with no accounts, authentication, or roles in v1.

#### Scenario: Single-user access
- **WHEN** the CLI is run
- **THEN** it serves one user with no login or role checks
