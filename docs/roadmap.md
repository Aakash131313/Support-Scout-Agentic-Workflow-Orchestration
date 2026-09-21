# Roadmap

## Delivered

### Phases 1-8 — Specification

Mission, scope, architecture, data contracts, functional and safety requirements, and
the offline-first test strategy.

### Phases 9-12 — Foundation

Package structure, environment settings, Pydantic contracts, safe artifact writing,
provider-isolated model access.

### Phases 13-14 — Triage and routing

Domain classification, sentiment, and deterministic safety screening with a documented
escalation matrix.

### Phases 15-19 — Evidence

Bounded Tavily search, URL safety policy, bounded scraping with redirect revalidation,
evidence deduplication and attribution.

### Phases 20-22 — Content

Support drafting, QA review, and privacy-safe documentation generation.

### Phases 23-32 — Hardening

Adversarial coverage, curated evaluation, prompt documentation, traceability.

### Phases 33-34 — Operations platform

FastAPI/SQLModel synthetic operations service and read-only diagnostic tooling, giving
the workflow real customer-specific evidence to reason about.

### Agentic refactor — specs/001-agentic-refactor/

Replaced the deterministic pipeline with a genuine tool-calling agent workflow:

- Five specialist ToolCallingAgents, each with explicit `@tool` functions.
- An orchestrator that is itself an agent, delegating through tools.
- A deterministic kernel that validates every state change the agent requests.
- One human-in-the-loop gate at restricted actions.
- Run-scoped JSONL tracing and an append-only error audit.
- Deterministic mode, shadow mode and the execution-mode switch removed entirely.

Three defects fixed in the process: escalation was recorded but ignored; escalated runs
wrote no artifacts at all; every QA escalation collapsed to a generic reason.

### Live validation pass (current)

The refactor shipped with a green offline suite. Running all eighteen curated tickets
against the live model exposed a class of defect the offline suite could not see, and
this pass closed it.

**Starting point:** 10 of 18 tickets reached their documented expected outcome.
**Result:** 18 of 18, with zero anomalies flagged.

| Measure | Before | After |
|---|---:|---:|
| Expected outcome met | 10/18 | **18/18** |
| Anomalies flagged | 34 | **0** |
| Tool calls traced | 0 | **503** |
| Wall-clock time | 1344s | 1020s |

Every safety escalation was correct throughout, with the right reason code and zero
delegations. Nothing in this pass weakened a safety control; the failures were
correctness and liveness defects sitting on top of a safety layer that already worked.

**What was fixed, grouped by cause:**

*Tool contracts.* Structured arguments declared as `str` were rejected by smolagents
before the tool ran, because a model sends a native JSON array as readily as a quoted
one. They are now `Any` and normalised inside the tool. Nested list fields accept a
bare string for the single-item case.

*Agent termination.* Specialists and the orchestrator called smolagents' built-in
`final_answer` in place of their own submit tool, discarding completed work. Every
agent prompt now states that the submit tool is the only way to deliver a result.
The orchestrator was the last one missed, and its omission made a fully successful
run record as `failed`.

*Idempotency.* No submit tool enforced its own "call this exactly once" instruction.
`submit_qa_decision` was observed being called eleven times in one run, silently
overwriting its own decision and burning roughly 41k tokens. All five submit tools
now return `already_submitted` on a repeat call, and the first decision is final.

*Unwinnable revisions.* QA requested changes for reasons its own deterministic checks
had already disproved, twice, exhausting the revision budget on drafts that needed no
change. `submit_qa_decision` now refuses a revision whose stated reason is about
operational grounding when that exact check passed.

*Evidence grounding.* `check_operational_claims` inspected only cited identifiers, so a
draft citing none passed vacuously no matter what it asserted. It now reads the
customer response and requires an `OP-` citation for any concrete status claim. A
confirmed absence is registered as citable `OP-` evidence so that rule is always
satisfiable; a service outage deliberately is not, because our downtime is not
evidence about a customer's order.

*Tracing.* Tool call history was read from the object returned by `agent.run(...)`,
which carried none. Reading `agent.memory.steps` instead took traced calls from 0 to
503 and restored the diagnostic value of every trace file.

*Retry bounding.* A failing delegation could be retried until the run's budget
collapsed. The kernel now escalates after two consecutive failures of the same
specialist with a specific reason, capping the cost of any similar failure.

**The finding worth recording:** five of these defects were false positives in
SupportScout's own deterministic checks, and each survived a fully green test suite.
Enumerated phrase lists failed five separate times — patched, then defeated by the next
paraphrase the model produced. The offline suite proved correctness of *mechanism*.
Only live runs proved correctness of *judgment*. See R-013 and PD-013 for what replaced
the phrase lists and why.

## Next

**Token-budget enforcement per agent.** Step and tool-call budgets exist; token
accounting is traced but not yet enforced. The eleven-call QA loop cost roughly 41k
tokens before a step ceiling stopped it, which is the concrete argument for this.

**Richer conflict detection.** Occurrence-level negation is a real improvement over
concatenated pair matching, but it still reasons about surface form. A claim-level
comparison would be better.

**Internal knowledge sources.** Public web search cannot answer policy questions
authoritatively. An internal documentation source would reduce escalations.

**Reviewer tooling.** A small interface for the human queue, showing the escalation
reason, sanitized context and the recommended action.

**Multi-ticket throughput.** Currently one ticket per run. Batch processing would need
per-run trace isolation, which the current `run_id` scoping already anticipates.

**Trace tool results, not only tool names.** The trace records which tool was called
but not what it returned, so a deliberately rejected call cannot be distinguished from
an accepted one. This produced false alarms in the verification harness and is the
cheapest remaining improvement to observability.
