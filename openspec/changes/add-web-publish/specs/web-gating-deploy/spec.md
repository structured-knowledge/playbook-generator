## ADDED Requirements

### Requirement: Password-gated access
The published site and the query endpoint SHALL be gated behind a single shared password via edge middleware, so a private playbook stays private while remaining web-accessible.

#### Scenario: Unauthenticated requests are blocked
- **WHEN** a request to a page lacks a valid session
- **THEN** it is redirected to a login that checks the shared password (verified against a hashed env var) before serving

#### Scenario: Gate covers the API
- **WHEN** `/api/query` is called without a valid session
- **THEN** the request is rejected

### Requirement: Local build, deploy the artifact
publish SHALL run locally (where the vault and secret live) and produce a bundle deployed to the host; the build SHALL NOT require the host to access the vault.

#### Scenario: Build does not expose the vault
- **WHEN** publish runs
- **THEN** the bundle is built locally and the host receives only the rendered output, never the vault or `.env`

### Requirement: Private deploy repo and env-var secrets
The deploy repo SHALL be private (it contains the rendered content), and the gateway key plus the gate password SHALL be deployment env vars, never committed.

#### Scenario: Content is not public via the repo
- **WHEN** the bundle is pushed for deploy
- **THEN** it goes to a private repository

#### Scenario: Secrets live as env vars
- **WHEN** the site is deployed
- **THEN** the gateway key and the gate password are host env vars, not present in the repo or the bundle
