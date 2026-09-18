# Tasks

Ordered, testable breakdown. All complete.

## Phase 1 — Contracts
- [x] T001 Sanitized exception hierarchy with `category` and `retryable`
- [x] T002 Pydantic contracts incl. `customer_reference`, trace, HITL and error models
- [x] T003 Settings with agent budgets and HITL toggles
- [x] T004 Redacting logger, JSONL trace, append-only error audit

## Phase 2 — Deterministic authority
- [x] T005 Token co-occurrence safety screening
- [x] T006 Pattern-based restricted-claim and secret-request detection
- [x] T007 `ArticlePrivacyValidator` across all eight identifier families
- [x] T008 URL policy with injectable DNS resolution
- [x] T009 Evidence sufficiency and conflict assessment
- [x] T010 Research query identifier stripping (FR-A14)

## Phase 3 — Provenance and human authority
- [x] T011 `EvidenceRegistry` with deterministic minting and deduplication
- [x] T012 HITL gate: auto-deny, auto-approve, interactive

## Phase 4 — Tools
- [x] T013 Triage tools incl. sentiment
- [x] T014 Research tools
- [x] T015 Support tools with structured unavailable results
- [x] T016 QA tools with required-check enforcement
- [x] T017 Documentation tools with deterministic privacy screening
- [x] T018 Orchestration tools: inspect, five delegations, finalize

## Phase 5 — Kernel
- [x] T019 Transition table and legality checks
- [x] T020 Escalation that stops the workflow (fixes defect 1)
- [x] T021 Finalizable escalated state (fixes defect 2)
- [x] T022 Specific QA escalation reasons (fixes defect 3)
- [x] T023 Bounded revision loop
- [x] T024 Execution budgets

## Phase 6 — Agents
- [x] T025 Shared agent construction and tracing
- [x] T026 Triage, Research, Support, QA, Documentation agents
- [x] T027 Orchestrator agent with artifacts written in `finally`

## Phase 7 — Assembly and interface
- [x] T028 Single wiring path with injectable dependencies
- [x] T029 CLI: `run`, `chat`, `serve`
- [x] T030 Operations service start-up probe
- [x] T031 Operations service fixes: engine injection, force reseed, duplicate contract removed

## Phase 8 — Removals
- [x] T032 Delete execution mode, shadow orchestrator, specialist adapters, dead stubs
- [x] T033 Delete legacy agents, pipeline orchestrator, diagnostics service, content pipeline
- [x] T034 Verify no deterministic routing path remains

## Phase 9 — Verification
- [x] T035 Unit tests: tools, validators, kernel, registry, artifacts, logging, CLI
- [x] T036 Integration tests IT-001 to IT-008
- [x] T037 Adversarial tests AT-001 to AT-020 and AT-016A
- [x] T038 Agentic contract tests (tool registration and delegation surface)
- [x] T039 Operations service contract tests
- [x] T040 Curated evaluation, 18 cases

## Phase 10 — Documentation
- [x] T041 Regenerate `tech_stack.md`, `mission.md`, `roadmap.md`
- [x] T042 Spec Kit bundle: spec, plan, research, data-model, contracts, tasks, quickstart
- [x] T043 README and CLAUDE.md
- [x] T044 Prompt documentation and decision log
- [x] T045 Architecture diagram
- [x] T046 Curate 18 sample inputs
- [x] T047 Traceability matrix
