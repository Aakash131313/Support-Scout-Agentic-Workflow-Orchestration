# SupportScout Refactor Bundle Requirements

## Bundle Name

**Refactor Bundle: Tool-Calling Agent Mesh and Agentic Orchestrator**

## Mission

SupportScout shall be refactored into a genuine multi-agent system in which LLM-powered specialist agents select and invoke registered tools, and an LLM-powered orchestrator agent delegates work to specialist agents. Deterministic software shall remain the final authority for safety, authorization, schema validation, evidence provenance, workflow integrity, privacy, execution limits, and artifact persistence.

---

## Definitions

### Agent

A model-powered component that executes an agent loop, receives a registered set of tools or managed agents, selects actions through model output, and produces an observable execution trace.

### Tool Call

A structured, model-selected invocation containing a tool name and validated arguments that is executed by the agent framework.

### Orchestrator Agent

A model-powered agent that selects and delegates work to specialist agents through managed-agent calls or explicit delegation tools.

### Deterministic Workflow Kernel

Non-LLM code that enforces workflow state, policy, execution limits, evidence registries, terminal states, and final acceptance.

### Required Tool Call

A tool invocation that must be present in the trace for a scenario to satisfy its acceptance criteria.

---

## Functional Requirements

## FR-RB-001: Structured Tool-Calling Framework

SupportScout shall use a structured tool-calling agent framework for the agentic execution path.

### Acceptance Criteria

- The framework accepts a model and explicit tool list.
- Tool calls are emitted as structured actions.
- Tool arguments are validated before execution.
- Tool results are returned to the agent loop.
- Agent execution supports a configurable maximum step count.

---

## FR-RB-002: Observable Tool-Call Traces

Every agent run shall produce an execution trace sufficient to prove which agent selected which tool.

### Acceptance Criteria

Each tool-call record includes:

```text
run_id
agent_name
step_number
tool_name
tool_arguments
started_at
completed_at
status
returned_evidence_ids
error_category
```

Sensitive values shall not appear in traces.

---

## FR-RB-003: Offline Agent Testing

The agentic architecture shall be testable without live model, search, scraping, or operational-data services.

### Acceptance Criteria

- A scripted model can emit predetermined tool calls.
- Unit and integration tests do not require API keys.
- Tool behavior can be mocked or faked.
- Trace assertions remain available in offline tests.

---

## FR-RB-004: Tool-Calling Research Agent

The Research Agent shall select and invoke research tools through its own agent loop.

### Required Tools

```text
web_search
validate_source_url
fetch_web_page
prepare_public_evidence
submit_research_result
```

### Acceptance Criteria

- The Research Agent selects search queries.
- The Research Agent invokes `web_search`.
- The Research Agent invokes URL validation before page retrieval.
- The Research Agent invokes page retrieval for selected results.
- The Research Agent submits structured public evidence.
- The primary orchestrator path does not directly loop through search and scrape operations.

---

## FR-RB-005: Public Evidence Provenance

Research Agent outputs shall preserve public-evidence provenance.

### Acceptance Criteria

- Public evidence uses `EV-*` identifiers.
- Source URL, title, retrieval time, content hash, and content are retained.
- Evidence IDs are assigned deterministically.
- Unknown or unvalidated URLs cannot become evidence.
- Insufficient and conflicting evidence are represented explicitly.

---

## FR-RB-006: Tool-Calling Support Agent

The Support Agent shall select and invoke operational and evidence-retrieval tools through its own agent loop.

### Required Tools

```text
get_order_status
get_shipment_status
get_return_status
get_account_diagnostics
get_checkout_diagnostics
retrieve_public_evidence
submit_support_draft
```

### Acceptance Criteria

- The Support Agent selects tools based on ticket content and available identifiers.
- Tool selection originates from the agent model action.
- The primary orchestrator path does not choose operational tools.
- Tool outputs are converted to validated operational evidence.
- The support draft contains only known evidence IDs.

---

## FR-RB-007: Operational Evidence Provenance

Operational tool outputs shall preserve record-level provenance.

### Acceptance Criteria

- Operational evidence uses `OP-*` identifiers.
- Source system, record type, record ID, retrieval time, and returned facts are retained.
- Evidence IDs are deterministic within a run.
- Missing records are represented as unavailable results, not fabricated evidence.

---

## FR-RB-008: Read-Only Operational Tools

The agentic Support Agent shall receive only read-only operational tools.

### Acceptance Criteria

No registered operational tool may:

```text
approve refunds
issue refunds
issue credits
process payments
change orders
change shipments
change returns
change accounts
change credentials
override policy
```

Restricted-action requests shall be escalated.

---

## FR-RB-009: Tool-Calling QA Agent

The QA Agent shall select and invoke validation tools through its own agent loop.

### Required Tools

```text
validate_evidence_ids
check_restricted_claims
check_sensitive_data
check_operational_grounding
check_public_guidance_grounding
request_support_revision
submit_qa_decision
```

### Acceptance Criteria

- The QA trace shows model-selected validation calls.
- The QA Agent returns a structured recommendation.
- The recommendation is one of `APPROVE`, `REVISE`, or `ESCALATE`.
- Revision instructions are structured and bounded.
- Deterministic checks may override the agent recommendation.

---

## FR-RB-010: Deterministic QA Authority

Agentic QA shall not replace deterministic policy enforcement.

### Acceptance Criteria

- Unknown evidence IDs prevent approval.
- Restricted claims prevent approval.
- Sensitive-data violations prevent approval.
- Operational claims without `OP-*` evidence prevent approval.
- Public recommendations without `EV-*` evidence prevent approval when public support is required.
- A deterministic violation overrides an agent recommendation of `APPROVE`.

---

## FR-RB-011: Agentic Orchestrator

SupportScout shall provide an LLM-powered Orchestrator Agent.

### Required Delegations

```text
delegate_to_triage
delegate_to_research
delegate_to_support
delegate_to_qa
delegate_to_documentation
```

### Acceptance Criteria

- The orchestrator is constructed as an agent with a model.
- The orchestrator receives delegation tools or managed agents.
- The orchestrator selects specialist agents through model actions.
- The trace identifies each delegation.
- The primary agentic path is not a procedural wrapper around the existing `Orchestrator.run()` sequence.

---

## FR-RB-012: Deterministic Workflow Kernel

The Orchestrator Agent shall operate through a deterministic workflow kernel.

### Acceptance Criteria

- All requested transitions are validated.
- Invalid transitions are rejected.
- Terminal states cannot transition.
- Mandatory escalation cannot be bypassed.
- Finalization fails when required artifacts or approvals are absent.
- State changes are auditable.

---

## FR-RB-013: Orchestrator Delegation Ordering

The workflow kernel shall enforce required ordering constraints regardless of orchestrator model output.

### Acceptance Criteria

- Triage occurs before normal research or support generation.
- Support drafting occurs before QA.
- Documentation occurs only after QA approval.
- Finalization occurs only after documentation or an approved limited-information terminal path.
- Early restricted-action escalation prevents unauthorized tool execution.

---

## FR-RB-014: Tool-Calling Documentation Agent

The Documentation Agent shall select and invoke documentation validation tools through its own agent loop.

### Required Tools

```text
select_public_evidence
check_article_privacy
validate_article_citations
submit_article
```

### Acceptance Criteria

- The Documentation Agent uses only public evidence for reusable articles.
- The trace shows model-selected documentation tool calls.
- Article citations contain only `EV-*` IDs.
- Customer-specific operational facts do not enter reusable articles.

---

## FR-RB-015: Privacy Boundary

The system shall maintain separate evidence rules for customer responses and reusable documentation.

### Acceptance Criteria

```text
Customer response:
    OP-* and EV-* permitted

Reusable article:
    EV-* only
```

The deterministic article validator shall reject:

```text
OP-* IDs
customer IDs
order IDs
shipment IDs
return IDs
account diagnostic IDs
checkout attempt IDs
customer-specific operational status
```

---

## FR-RB-016: Execution Modes

SupportScout shall support staged migration through configuration.

### Required Modes

```text
deterministic
agentic
shadow
```

### Acceptance Criteria

- `deterministic` runs the existing validated workflow.
- `agentic` runs the agentic orchestrator and tool-calling specialists.
- `shadow` preserves deterministic output authority while running the agentic path for comparison.
- Unknown mode values fail configuration validation.

---

## FR-RB-017: Shadow Comparison

Shadow mode shall compare deterministic and agentic execution without allowing the agentic result to alter the authoritative customer output.

### Acceptance Criteria

Comparison captures:

```text
workflow terminal status
escalation reason
selected tools
selected agents
evidence IDs
QA decision
article privacy result
output schema validity
```

---

## FR-RB-018: Safe Tool Registry

Each agent shall receive only the tools required for its role.

### Acceptance Criteria

- Research Agent cannot call operational tools.
- Support Agent cannot write final artifacts directly.
- QA Agent cannot mutate evidence.
- Documentation Agent cannot access operational retrieval tools.
- Orchestrator Agent cannot bypass the workflow kernel.

---

## FR-RB-019: Tool Budgets

Agent and tool execution shall be bounded.

### Acceptance Criteria

Configuration supports:

```text
maximum agent steps
maximum total tool calls
maximum calls per tool
timeout per tool
maximum delegated agent calls
maximum revision count
```

Exceeding a budget shall produce a controlled failure or escalation.

---

## FR-RB-020: Error Handling

Tool and agent failures shall be represented as structured errors.

### Acceptance Criteria

Structured errors include:

```text
error_category
agent_name
tool_name
retryable
safe_message
```

Secrets, credentials, raw authorization values, and full sensitive payloads shall not be included.

---

## FR-RB-021: Audit Artifacts

The agentic path shall write additional trace artifacts without removing existing terminal artifacts.

### Required Agentic Artifacts

```text
agent_run_trace.json
tool_call_trace.json
agent_delegation_trace.json
execution_comparison.json
```

`execution_comparison.json` is required only in shadow mode.

---

## FR-RB-022: Backward-Compatible Artifacts

Existing output contracts shall remain available.

### Required Existing Artifacts

```text
interaction_summary.json
customer_response.md
troubleshooting_article.md
sources.json
operational_sources.json when applicable
audit_log.json
```

---

## FR-RB-023: Agent Identity

Every production agent shall have a stable name, description, role instructions, tool list, and execution limits.

### Required Agents

```text
OrchestratorAgent
TriageAgent
ResearchAgent
SupportAgent
QAAgent
DocumentationAgent
```

---

## FR-RB-024: Required Tool Use

Applicable scenarios shall fail validation if the expected agent does not invoke required tools.

### Examples

- `ORD-1001` delay requires Support Agent calls to order and shipment tools.
- Customer `CUS-003` checkout failure requires the checkout diagnostic tool.
- Generic tracking guidance requires Research Agent web tools.
- Refund approval requires escalation and must not execute an operational mutation.

---

## Non-Functional Requirements

## NFR-RB-001: Traceability

All agent decisions, delegations, tool calls, evidence outputs, validation outcomes, and terminal decisions shall be traceable.

## NFR-RB-002: Reproducible Tests

All non-live validation shall run deterministically without external services.

## NFR-RB-003: Safety

Restricted actions shall remain blocked by deterministic policy regardless of agent output.

## NFR-RB-004: Privacy

Customer-specific operational information shall not appear in reusable documentation.

## NFR-RB-005: Maintainability

Tools, agents, workflow kernel, model adapters, and trace components shall be modular and independently testable.

## NFR-RB-006: Compatibility

The deterministic execution path shall remain available until the agentic path completes all bundle validation gates.

## NFR-RB-007: Configuration Safety

Secrets shall remain environment-based and shall not appear in source files, prompts, traces, test fixtures, or generated artifacts.

## NFR-RB-008: Bounded Autonomy

Every agent shall have explicit tool lists, step limits, delegation limits, and final-answer validation.

## NFR-RB-009: Structured Contracts

Agent inputs, tool arguments, tool results, specialist outputs, and final outputs shall use validated schemas.

## NFR-RB-010: Failure Transparency

Failures shall indicate the safe error category and failing agent or tool without exposing sensitive payloads.

---

## Explicitly Out of Scope

The Refactor Bundle shall not introduce:

- Refund mutation tools.
- Payment execution tools.
- Order mutation tools.
- Account mutation tools.
- Production customer data.
- Unbounded agent execution.
- Unrestricted code execution.
- Agent-controlled final authorization.
- Removal of deterministic safety gates.

---

## Bundle Acceptance Rule

The Refactor Bundle shall not be accepted solely because the generated response is correct.

Acceptance requires trace evidence proving:

1. Specialist agents selected and invoked their own tools.
2. The Orchestrator Agent selected and invoked specialist agents.
3. Deterministic validators retained final authority.
