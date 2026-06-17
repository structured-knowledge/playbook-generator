# Precision vs. recall in the play compiler

playmaker's `wiki/AGENTS.md` deliberately biases the compiler toward
**precision over recall** (tasks 2.3, design.md "Risks"). This document records
the trade-off so it is a decision, not an accident.

## The bias

A play is created only when the source yields something **clearly, specifically
actionable** — enough to fill `When to use` + `How` + `Outcome` with substance.
Borderline material (general background, motivation, definitions, practices the
source dismisses, vague "be thoughtful" advice) is intentionally **dropped**.

The rule in the prompt: *when in doubt, leave it out.*

## Why precision

A playbook is read to *act*. Its value is that every page is a real play you can
run, not an exhaustive transcript of everything a source mentioned. Noise is
expensive in two ways:

- A low-value play dilutes the index and the query results, so good plays are
  harder to find.
- Once a weak play exists, enrichment keeps it alive — the cost compounds.

A *missed* borderline practice is cheap by comparison: the source is still in
the KB, and re-reading or a future source can promote the practice later.

## The cost (observed)

The spike (2026-06-16) saw the precision bias drop a genuinely useful but
softly-stated practice (an incident-postmortem habit that the source only
gestured at). That is the expected failure mode: **high precision loses some
real plays at the margin.** We accept it.

## Tuning levers

If a deployed instance is too sparse (missing plays you wanted) or too noisy
(weak plays), tune the prompt rather than the code:

- **More recall:** soften "when in doubt, leave it out"; lower the bar on what
  counts as actionable; explicitly invite plays from single strong paragraphs.
- **More precision:** strengthen the "do not manufacture a play from thin
  material" clause; require an explicit `How` with concrete steps.

Re-run `playmaker ingest` on representative sources after a change and inspect
the produced plays (`playmaker plays`). Because compilation is LLM-driven, this
calibration is empirical — there is no offline test for "good recall."

## Conflict detection precision

Conflict flagging (`playmaker.changelog`) carries the *same* precision bias,
and learned it the hard way. The first detector matched bare cue words
(`contradict`, `conflict`, `critic*`, `whereas`, `counterproductive`, …)
anywhere in an enriched play's new text. Validated against a real 10-article
AI-engineering corpus (28 plays), that flagged **8 plays — all false
positives**:

- `critic*` matched the everyday word **"critical"** ("critical elements",
  "latency-critical") — it fired on ~11 pages.
- `conflict` matched **"state conflicts"** / "sub-agents do not conflict"
  (technical conflicts between components, not sources disagreeing).
- `contradict` matched **"contradictory context"** — which is a play's *own
  subject* (stress-testing RAG against contradictory inputs).
- `whereas` / `in contrast` matched neutral comparative prose ("smaller chunks
  improve specificity, whereas larger chunks provide context").

The lesson: **ordinary caveat / limitation / comparison language is not a
contradiction.** A genuine inter-source contradiction is a *meta-statement that
a recommendation or practice is disputed.* The detector now requires an
**oppositional construction anchored to advice/practice/belief** — e.g.
"contradicts the recommendation that…", "contrary to the popular advice…",
"some practitioners argue this is counterproductive", "now considered an
anti-pattern", "no longer recommended", "supersedes the earlier guidance",
"`dogma`". On the same corpus it flags **0/28** (correct — the articles are
complementary), while still catching real contradictions
(`tests/test_changelog.py` pins both directions with parametrized TP/FP cases
drawn from the real corpus).

This trades recall for precision deliberately: a missed soft disagreement is
cheaper than crying wolf on every strong caveat, which trains the user to
ignore the flag.

**Higher-recall lever (future):** the robust ceiling for this semantic task is
an **LLM-as-judge** check — on each *enrichment*, ask the model "did this source
contradict the play's prior guidance? yes/no + why". It would catch subtle
disagreements the regex can't, at the cost of an extra LLM call per enriched
play and some nondeterminism. The cheap, deterministic regex is the default;
the LLM-judge is the opt-in upgrade when recall matters more than cost.
