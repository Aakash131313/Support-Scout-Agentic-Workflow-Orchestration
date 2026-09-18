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

### Agentic refactor (current) — `specs/001-agentic-refactor/`
Replaced the deterministic pipeline with a genuine tool-calling agent workflow:

- Five specialist `ToolCallingAgent`s, each with explicit `@tool` functions.
- An orchestrator that is itself an agent, delegating through tools.
- A deterministic kernel that validates every state change the agent requests.
- One human-in-the-loop gate at restricted actions.
- Run-scoped JSONL tracing and an append-only error audit.
- Deterministic mode, shadow mode and the execution-mode switch removed entirely.

Three defects fixed in the process: escalation was recorded but ignored; escalated runs
wrote no artifacts at all; every QA escalation collapsed to a generic reason.

## Next

**Token-budget enforcement per agent.** Step and tool-call budgets exist; token
accounting is traced but not yet enforced.

**Richer conflict detection.** The current affirmative/negative pair matching is
conservative and misses subtle disagreement. A claim-level comparison would be better.

**Internal knowledge sources.** Public web search cannot answer policy questions
authoritatively. An internal documentation source would reduce escalations.

**Reviewer tooling.** A small interface for the human queue, showing the escalation
reason, sanitized context and the recommended action.

**Multi-ticket throughput.** Currently one ticket per run. Batch processing would need
per-run trace isolation, which the current `run_id` scoping already anticipates.
