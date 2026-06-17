## ADDED Requirements

### Requirement: Thin AI query endpoint
The published site SHALL expose an `/api/query` serverless function that answers a question from the published snapshot via one gateway chat call, without OpenKB, embeddings, or the live vault.

#### Scenario: Answer from the snapshot
- **WHEN** a question is posted to `/api/query`
- **THEN** the function selects plays from the published `plays.json` (via the retrieval seam), sends them to the gateway, and returns the answer

#### Scenario: Grounded, cited answer
- **WHEN** the function answers
- **THEN** it cites the plays it used by key, and the citations link back to the published play pages

#### Scenario: Bound to the last publish
- **WHEN** the vault has changed but no `publish` has run
- **THEN** the query answers from the last published snapshot, not the live vault

### Requirement: Swappable retrieval seam
The query function SHALL isolate play selection behind a `select_plays(question, plays)` seam whose v1 implementation returns all plays (whole-playbook context, bodies truncated). Larger-corpus strategies (brief-routing, embeddings) replace this seam without changing the artifact contract.

#### Scenario: v1 sends the whole playbook
- **WHEN** `select_plays` runs in v1
- **THEN** it returns every play, and the function sends their truncated bodies in one call

#### Scenario: Seam is replaceable
- **WHEN** a larger corpus requires retrieval
- **THEN** `select_plays` can be replaced without changing `plays.json` or the endpoint contract

### Requirement: Gateway configuration and secret handling
The query function SHALL call the public LiteLLM gateway with the configured model id, the `User-Agent` workaround, certifi-based TLS, and a generous `max_tokens`; the gateway key SHALL be a deployment env var, never bundled.

#### Scenario: Public gateway, correct model
- **WHEN** the function calls the gateway
- **THEN** it targets the public base URL (not a LAN-only endpoint) with the case-correct model id and a generous `max_tokens`

#### Scenario: Secret not in the bundle
- **WHEN** the site is published and deployed
- **THEN** the gateway key is read from a deployment env var and never written into the bundle
