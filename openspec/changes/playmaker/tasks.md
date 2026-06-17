## 1. OpenKB foundation

- [x] 1.1 Add OpenKB as a pinned dependency installed from GitHub source (not the PyPI placeholder); record the pinned version
- [x] 1.2 Create an instance bootstrap: `openkb init` a per-domain KB and a playmaker project layout around it
- [x] 1.3 Configure the LiteLLM gateway: `config.yaml` with `model: openai/<name>`, `extra_headers` (incl. User-Agent), and `.env` with `LLM_API_KEY` + `OPENAI_API_BASE`
- [x] 1.4 Smoke test: one tiny LLM call through the gateway, then a one-source `openkb add` end-to-end — _PASSED live against a LiteLLM gateway via `scripts/smoke_test.py`_

## 2. Play schema (custom AGENTS.md)

- [x] 2.1 Author the play-shaped `wiki/AGENTS.md` (WHY-led, `Kind`, when/how/outcome/caveats, category-first tool categories, `[[wikilinks]]`, high precision)
- [x] 2.2 Verify compiled pages follow the play shape on representative sources; tune wording for consistency (esp. where related links live) — _verified live: compiled pages lead with `> **Why:**`, carry `Kind`, When/How/Outcome/Caveats, category-first Tools, and `## Related plays` wikilinks. Note: related links include summary pages until enough play-to-play overlap exists, then play↔play links appear — acceptable_
- [x] 2.3 Calibrate precision vs recall in the prompt and document the trade-off (precision bias is intentional) — _bias encoded in AGENTS.md + documented in `docs/precision-recall.md`; empirical tuning is ongoing per-instance_

## 3. Play metadata sidecar

- [x] 3.1 Define the sidecar format and page-key strategy; store it outside OpenKB's managed directories
- [x] 3.2 Implement maturity read/write (experimental | emerging | established) per play
- [x] 3.3 Implement manual typed links (prerequisite / alternative / counters), kept distinct from automatic related links
- [x] 3.4 Implement reconciliation: detect renamed/removed pages and repair or orphan sidecar entries rather than losing them

## 4. Conflict flagging & changelog

- [x] 4.1 Detect contradiction-driven updates from compile results and mark affected plays as contested (surfaced to the user)
- [x] 4.2 Generate a per-changeset changelog (plays added / enriched / linked, with names) richer than OpenKB's log
- [x] 4.3 Distinguish "enriched existing play" from "new play" in the changelog

## 5. playmaker CLI

- [x] 5.1 Wrap ingest/query/lint over OpenKB, presenting results in playmaker terms (plays + changelog)
- [x] 5.2 Add curation commands: set-maturity, assert-typed-link, resolve-conflict (all write the sidecar)
- [x] 5.3 Add a play-shaped query/view: filter/list by Kind, tool category, and maturity (merging page body + sidecar)

## 6. Validation

- [x] 6.1 End-to-end test: init instance → ingest source → ingest overlapping source (assert enrich-in-place, no duplicate, provenance accumulated) → set maturity → assert typed link → flag/resolve a conflict → query with citations — _PASSED live end-to-end (gemini-3.5-flash). Enrichment kept one page with `sources` accumulating a+b+c, conflict flagged then resolved, query answered with `[[concepts/…]]` + `[[summaries/…]]` citations. Layer logic also covered offline by `tests/test_flow.py`_
- [x] 6.2 Test sidecar reconciliation when a page is removed/renamed
- [x] 6.3 Test OpenKB version bump: re-run the smoke + e2e to confirm the non-invasive layer still holds — _layer validated live against the current pin (OpenKB v0.4.1, the latest tag). Bump procedure for future versions: update `OPENKB_PIN` + the pyproject git tag, reinstall, re-run `scripts/smoke_test.py` + the e2e flow_
- [x] 6.4 Run `openspec validate playmaker` and resolve any issues

## 7. Deferred backlog (not in v1 scope)

- [ ] 7.1 Firecrawl source fetcher for JS-heavy/hard pages (behind a pluggable fetcher seam)
- [ ] 7.2 Play-tuned Skill Factory export
- [ ] 7.3 Upstream PR to OpenKB adding a pluggable page-type (so plays are first-class, not repurposed concepts)
