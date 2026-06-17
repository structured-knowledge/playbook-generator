## MODIFIED Requirements

### Requirement: Unified browse-and-ask command bar
The published index SHALL present a single command bar that serves both browsing and asking, replacing the separate header search box and standalone Ask form. Typing filters the play list client-side; an explicit "Ask the playbook" action SHALL be visible alongside the filtered results whenever the bar is non-empty, so asking is a deliberate action rather than a hidden input mode.

#### Scenario: Typing filters the list
- **WHEN** the user types in the command bar
- **THEN** the play list filters client-side over `plays.json` with no request to the query endpoint

#### Scenario: Ask action is always visible
- **WHEN** the command bar is non-empty
- **THEN** an explicit "Ask the playbook: «query»" action is shown above the filtered results, and triggering it (Enter or the Ask control) sends the query to `/api/query`

#### Scenario: Empty bar restores the default browse view
- **WHEN** the command bar is cleared
- **THEN** the full play list (faceted browse view) is shown again

## ADDED Requirements

### Requirement: Faceted browse
The published index SHALL let the reader narrow plays by `kind`, `maturity`, and `tool` via selectable facet chips with live counts, and SHALL order the list maturity-first (established before emerging before experimental), matching the CLI's `plays` view. Faceting is client-side over `plays.json`.

#### Scenario: Facet narrows the list
- **WHEN** the reader selects a kind, maturity, or tool facet
- **THEN** the list shows only matching plays, with the result count, and no request to the query endpoint

#### Scenario: Facets combine with text filtering
- **WHEN** a facet is active and the reader types in the command bar
- **THEN** both constraints apply together

#### Scenario: Maturity-first ordering
- **WHEN** the play list is shown
- **THEN** plays are ordered by maturity (established first), then title — matching the CLI `plays` view

#### Scenario: Mobile facets collapse
- **WHEN** the site is viewed on a narrow screen
- **THEN** the facet chips collapse into a toggleable filter sheet so the command bar stays primary

### Requirement: Seeded example questions
The published index SHALL show a small set of example questions on the empty command bar, derived at build time from the corpus (play titles/whys) so they reflect the current plays. Selecting one fills the bar and runs the Ask action.

#### Scenario: Empty bar shows examples
- **WHEN** the index loads with an empty command bar
- **THEN** a few example questions derived from the published plays are shown

#### Scenario: Example runs the ask
- **WHEN** the reader selects an example question
- **THEN** the bar is filled with it and the Ask action runs
