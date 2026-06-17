## ADDED Requirements

### Requirement: Triggered publish command
playmaker SHALL provide a `publish` command that renders the current vault (plays + sidecar) into a deployable static bundle, run locally and on demand. The UI is a snapshot, not synchronized with the vault.

#### Scenario: Publish produces a bundle
- **WHEN** the user runs `playmaker publish`
- **THEN** a static site (one page per play plus an index) and a `plays.json` data file are written to the output directory

#### Scenario: Read-only over the vault
- **WHEN** publish runs
- **THEN** nothing is written into `wiki/` or `.openkb/`; the command only reads the vault and sidecar

### Requirement: Readable play pages
The published site SHALL render each play in play shape — title, `Kind` badge, maturity badge, Why callout, body sections, category-first tools, related links, and sources — optimized for readability.

#### Scenario: Play shape rendered
- **WHEN** a play page is viewed
- **THEN** its Why callout, `Kind`, maturity, When/How/Outcome/Caveats body, tools, related links, and sources are shown

#### Scenario: Sidecar fields render as visual signal
- **WHEN** a play is marked contested in the sidecar
- **THEN** the page shows a contested banner, and maturity renders as a badge

#### Scenario: Links resolve to play pages
- **WHEN** a `[[wikilink]]` or typed-link target is another published play
- **THEN** it renders as a link to that play's page, with typed links labeled by relationship and kept distinct from automatic wikilinks

### Requirement: Snapshot data file
publish SHALL emit a `plays.json` capturing every play (key, title, why, kind, maturity, body, tool_categories, wikilinks, typed_links, sources) as the contract consumed by the query function and client-side search.

#### Scenario: plays.json is self-sufficient
- **WHEN** publish runs
- **THEN** `plays.json` contains an entry per play sufficient to answer queries and render search without re-reading the vault

### Requirement: Client-side search
The published site SHALL provide instant search over plays with no backend call.

#### Scenario: Search works without the query backend
- **WHEN** the user types in the search box
- **THEN** matching plays are listed client-side, with no request to the query endpoint
