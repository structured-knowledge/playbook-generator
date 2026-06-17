## ADDED Requirements

### Requirement: Honest wait feedback during a query
While a query is in flight, the Ask UI SHALL show progressive feedback — an elapsed timer and a phase line (e.g. "Reading N plays… · 6s") — instead of a static label. The answer is delivered as a single response; this requirement covers client-side feedback only and does not introduce token streaming.

#### Scenario: Elapsed feedback while waiting
- **WHEN** a question has been sent to `/api/query` and the response has not yet arrived
- **THEN** the UI shows an advancing elapsed timer and a phase line, not a static "Asking…" label

#### Scenario: Network path unchanged
- **WHEN** the Ask action runs
- **THEN** it posts the same request to `/api/query` and consumes the same single JSON response as before — no streaming, no endpoint or gateway change

### Requirement: Next-step affordance when the playbook does not cover a question
When the answer reports the playbook does not cover the question (no plays cited), the Ask UI SHALL present a next step — a copyable `playmaker ingest <url>` call — rather than ending at a dead-end message. A closest related play MAY be surfaced when one is cheaply available client-side.

#### Scenario: No-answer offers a next step
- **WHEN** the query returns an answer with no cited plays (not covered)
- **THEN** the UI shows a copyable `playmaker ingest <url>` call as the suggested next step

#### Scenario: Closest topic is optional
- **WHEN** no cheap closest-topic signal is available client-side
- **THEN** the next-step affordance still renders with only the `ingest` call
