## ADDED Requirements

### Requirement: Custom AGENTS.md steers the compiler
playmaker SHALL provide a custom `wiki/AGENTS.md` that OpenKB injects as the compilation system prompt, redefining concept pages as PLAYS, so compiled output is play-shaped without modifying OpenKB code.

#### Scenario: Compiled page follows the play shape
- **WHEN** a source is compiled
- **THEN** each produced play leads with a WHY/principle sentence and contains a `Kind`, a when-to-use, a how (steps), an outcome, and caveats sections

### Requirement: Category-first tool references
The play schema SHALL record tools as a stable category with specific tools as swappable examples (e.g. "coding agent (e.g., Claude, Codex)"), not as the primary identifier.

#### Scenario: Tools recorded category-first
- **WHEN** a source mentions specific tools
- **THEN** the play lists the tool category with those tools as examples

### Requirement: Auto-detected play kind
The play schema SHALL have the compiler tag each play with a `Kind` of technique, principle, or procedure.

#### Scenario: Kind is assigned
- **WHEN** a play is generated
- **THEN** it carries a `Kind` label appropriate to its content

### Requirement: High-precision extraction
The play schema SHALL instruct high-precision extraction so only clearly actionable practices become plays and non-actionable prose is ignored.

#### Scenario: Non-actionable content is skipped
- **WHEN** a source contains practices it explicitly dismisses or general prose
- **THEN** the compiler does not create plays for that content

### Requirement: Automatic related links
The play schema SHALL preserve OpenKB's `[[wikilinks]]` so related plays are automatically cross-linked.

#### Scenario: Related plays are linked
- **WHEN** two plays are related
- **THEN** they are cross-linked via wikilinks without manual action
