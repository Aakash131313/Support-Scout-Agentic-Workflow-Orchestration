# Feature Specification: Agentic Workflow Refactor

**Feature branch:** `001-agentic-refactor`
**Status:** Implemented
**Input:** Replace the deterministic pipeline with a genuine agentic workflow driven by
tool-calling agents and an agentic orchestrator, while keeping every existing safety,
privacy and evidence guarantee.

---

## Why

The previous implementation described itself as agentic but was not. Concretely:

- `orchestrator.py` executed a fixed sequence. The model never chose a next step.
- `OperationalDiagnosticsService.gather()` regex-extracted identifiers from the ticket
  body and then unconditionally called order, shipment **and** return lookups for every
  order, plus account and checkout lookups for every customer. No selection happened.
- `QAAgent.review()` contained no model call at all; it was a direct call to
  `ContentValidator.validate()`.
- `ResearchAgent` was a five-line stub returning one hard-coded query string. It never
  searched, scraped or produced evidence.
- Operational "tools" carried `name` and `description` attributes but were ordinary
  classes with a `.run()` method. Nothing was a callable tool.

The FY27 training plan requires demonstrating agent design and orchestration. A pipeline
with tool-shaped metadata does not demonstrate that.

Three latent defects were also found and are in scope to fix:

1. **Escalation was ignored.** `apply_triage`'s predecessor advanced to `triaged`
   regardless of the escalation decision, so a refund-approval ticket continued into
   research and drafting.
2. **Escalated runs wrote nothing.** `ESCALATED` was terminal, `finalize()` required
   `DOCUMENTED`, so an escalated run raised before any artifact was written.
3. **QA escalation reasons were erased.** Every QA escalation was recorded as
   `qa_failure`, discarding the information a human reviewer needs.

---

## User scenarios

### US-1: Delayed delivery with operational evidence
A customer asks where a late parcel is and supplies an order reference.

**Expected:** The orchestrator delegates to triage, research, support, QA and
documentation in turn. The support agent chooses to call the order and shipment tools
and does *not* call return, account or checkout tools. The reply cites both `OP-` and
`EV-` evidence. The workflow completes and every artifact is written.

### US-2: Refund approval request
A customer asks for a refund to be approved.

**Expected:** Deterministic screening fires before any model call. The human-in-the-loop
gate asks an operator whether automated handling may continue. Unattended, the default
policy denies. The workflow escalates with `financial_authorization`, no specialist
runs, and a full artifact set including `escalation.json` is written.

### US-3: Unknown order
A customer asks about an order that does not exist in the operations system.

**Expected:** The order tool returns `available: false` with a reason. The agent
explains that the record could not be found rather than inventing a status, and the
run does not crash.

### US-4: QA requests a revision
The first draft cites evidence weakly.

**Expected:** QA runs all four deterministic checks, calls `request_support_revision`
with specific instructions, and returns `revise`. The orchestrator delegates to support
again with those instructions, then to QA again. Within the revision limit, the run
completes; beyond it, it escalates with `revision_limit_exceeded`.

### US-5: Documentation privacy
The documentation agent drafts an article mentioning a specific order.

**Expected:** `check_article_privacy` rejects it deterministically and names the
identifier found. The agent rewrites generically and submits successfully. The published
article contains no identifier of any family.

### US-6: Prompt injection
A ticket instructs the system to ignore its rules.

**Expected:** Screening treats the text as data and escalates `outside_authority`. No
specialist runs. If injected text arrives via a scraped page instead, it is stored as
inert evidence and cannot change what any tool permits.

---

## Functional requirements

| ID | Requirement |
|---|---|
| FR-A01 | Every specialist SHALL be a `ToolCallingAgent` whose capabilities are `@tool` functions. |
| FR-A02 | The orchestrator SHALL itself be a `ToolCallingAgent` whose tools are state inspection, five delegation tools, and finalization. |
| FR-A03 | Each specialist SHALL have exactly one corresponding delegation tool. |
| FR-A04 | The support agent SHALL select which operational tools to call; no tool may run automatically. |
| FR-A05 | Evidence identifiers SHALL be minted deterministically by a registry, never by a model. |
| FR-A06 | Submission tools SHALL reject any evidence identifier the registry did not issue. |
| FR-A07 | A mandatory escalation SHALL stop the workflow before any further specialist runs. |
| FR-A08 | An escalated run SHALL be finalizable and SHALL write the full artifact set. |
| FR-A09 | QA escalation SHALL preserve the specific reason derived from the failing check. |
| FR-A10 | The QA submit tool SHALL refuse `approve` while any deterministic check is failing. |
| FR-A11 | The QA submit tool SHALL refuse submission until all four required checks have run. |
| FR-A12 | A QA revision SHALL re-enter drafting and SHALL be bounded by the configured limit. |
| FR-A13 | Missing operational records SHALL return a structured unavailable result, not raise. |
| FR-A14 | Research queries SHALL have customer, order, account and refund identifiers stripped deterministically. |
| FR-A15 | Article privacy SHALL be enforced deterministically across all eight identifier families. |
| FR-A16 | Exactly one human-in-the-loop gate SHALL exist, at restricted actions only. |
| FR-A17 | The gate SHALL be invoked by the kernel, never by an agent. |
| FR-A18 | Every run SHALL produce a run-scoped JSONL trace of agent steps, tool calls, delegations, transitions and human decisions. |
| FR-A19 | Every caught failure SHALL append a `StructuredError` to a shared append-only audit. |
| FR-A20 | Sentiment SHALL be produced by a tool and SHALL never confer authority. |
| FR-A21 | Agent autonomy SHALL be bounded by configurable step and tool-call budgets. |
| FR-A22 | Deterministic mode, shadow mode and the execution-mode switch SHALL be removed. |
| FR-A23 | The ticket contract SHALL carry an optional validated `customer_reference`. |
| FR-A24 | The operations service SHALL be probed at start-up with a clear remediation message on failure. |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-A01 | The default test suite SHALL pass offline with no API keys. |
| NFR-A02 | Logs, traces and artifacts SHALL contain no credential, card number or raw customer message body. |
| NFR-A03 | Tool names, descriptions and argument schemas SHALL be readable directly from source. |
| NFR-A04 | The workflow SHALL run one ticket at a time with a single wiring path. |
| NFR-A05 | Artifacts SHALL be written for every terminal state. |

## Safety requirements

Inherited unchanged from Phase 3-4 (SR-001 to SR-010) and re-verified by the adversarial
suite. See `specs/archive/phase-3-4/requirements.md`.

---

## Acceptance criteria

- [x] Every specialist registers its expected `@tool` set, asserted mechanically.
- [x] The orchestrator exposes exactly seven tools, five of them delegations.
- [x] A refund request escalates with zero delegations recorded.
- [x] An escalated run writes eight artifacts including `escalation.json`.
- [x] A QA sensitive-data failure escalates as `sensitive_data`, not `qa_failure`.
- [x] The revision loop completes within budget and escalates beyond it.
- [x] `ORD-9999` yields a structured miss and the run still completes.
- [x] An article containing any of the eight identifier families is rejected.
- [x] AT-001 to AT-020 and AT-016A all pass.
- [x] IT-001 to IT-008 all pass.
- [x] No `execution_mode`, `shadow_orchestrator` or deterministic routing path remains.

## Out of scope

- Live provider validation (separately marked, opt-in)
- Concurrency or batch processing
- A web interface for the human review queue
