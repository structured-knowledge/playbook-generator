## ADDED Requirements

### Requirement: Sidecar metadata store
playmaker SHALL maintain a metadata store located outside OpenKB's managed directories, keyed by play page, holding playmaker-owned fields that OpenKB does not manage.

#### Scenario: Sidecar survives engine operations
- **WHEN** OpenKB compiles or recompiles pages
- **THEN** the playmaker sidecar metadata is preserved and not overwritten by the engine

### Requirement: Human-set maturity
The sidecar SHALL record a human-set maturity (experimental | emerging | established) per play.

#### Scenario: Set maturity
- **WHEN** the user sets a play's maturity
- **THEN** the value is stored in the sidecar keyed to that play

### Requirement: Manual typed links
The sidecar SHALL record human-asserted typed links between plays — prerequisite/builds-on, alternative-to, and counters/conflicts-with — distinct from automatic related links.

#### Scenario: Assert a typed link
- **WHEN** the user asserts a prerequisite link from play A to play B
- **THEN** the typed link is stored in the sidecar and is not confused with an automatic related link

### Requirement: Sidecar reconciliation
playmaker SHALL reconcile sidecar entries against current pages when OpenKB renames or removes a page, repairing or orphaning entries rather than losing metadata silently.

#### Scenario: Page removed
- **WHEN** OpenKB removes a play page
- **THEN** playmaker detects the dangling sidecar entry and handles it explicitly (repair or mark orphaned)
