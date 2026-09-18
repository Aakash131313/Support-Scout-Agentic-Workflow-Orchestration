# SupportScout Refactor Bundle Plan

## Bundle Name

**Refactor Bundle: Tool-Calling Agent Mesh and Agentic Orchestrator**

## Purpose

Refactor SupportScout from a primarily procedural orchestration system into a genuine multi-agent system in which:

1. Specialist agents are LLM-powered agents.
2. Specialist agents select and invoke their own registered tools.
3. The orchestrator is itself an LLM-powered agent.
4. The orchestrator delegates work to specialist agents through managed-agent or delegation tool calls.
5. Deterministic Python remains the final authority for safety, authorization, schema validation, state transitions, evidence provenance, execution limits, and artifact writing.

The bundle prioritizes demonstrable agent behavior over execution efficiency. A component does not qualify as an agent merely because it is named `Agent`; it must run an agent loop and produce observable model-selected tool calls.

---

## Current-State Problem

The current architecture is reliable and well-tested, but core decisions are still procedural:

```text
Deterministic Orchestrator
    -> chooses research flow
    -> calls search tool
    -> calls scraper
    -> gathers operational records
    -> sends prepared evidence to agents
    -> invokes QA function
    -> invokes documentation function
```

This means the orchestrator, rather than the specialist agent, decides which tools execute. The Research Agent and QA Agent currently behave more like service functions than autonomous tool-using agents.

---

## Target Architecture

```text
Customer Ticket
      |
      v
Deterministic Entry Boundary
- Ticket schema validation
- Immediate restricted-action detection
- Run and tool budgets
- Audit initialization
      |
      v
OrchestratorAgent
ToolCallingAgent
      |
      +--> delegates to TriageAgent
      |
      +--> delegates to ResearchAgent
      |       +--> calls web_search
      |       +--> calls validate_source_url
      |       +--> calls fetch_web_page
      |       +--> calls prepare_public_evidence
      |
      +--> delegates to SupportAgent
      |       +--> calls get_order_status
      |       +--> calls get_shipment_status
      |       +--> calls get_return_status
      |       +--> calls get_account_diagnostics
      |       +--> calls get_checkout_diagnostics
      |       +--> calls retrieve_public_evidence
      |
      +--> delegates to QAAgent
      |       +--> calls validate_evidence_ids
      |       +--> calls check_restricted_claims
      |       +--> calls check_sensitive_data
      |       +--> calls check_operational_grounding
      |       +--> calls request_support_revision
      |
      +--> delegates to DocumentationAgent
              +--> calls select_public_evidence
              +--> calls check_article_privacy
              +--> calls validate_article_citations
      |
      v
Deterministic Completion Boundary
- State validation
- QA enforcement
- Escalation enforcement
- Evidence provenance verification
- Privacy validation
- Artifact persistence
```

---

## Architectural Principle

The system will use a hybrid model:

```text
Agentic decisions
+
Deterministic authorization and validation
```

### Agents own

- Tool selection.
- Delegation decisions.
- Multi-step reasoning.
- Deciding when additional research or operational context is needed.
- Proposing drafts, QA outcomes, revisions, and documentation.

### Deterministic code owns

- Allowed tools.
- Read-only versus mutating capabilities.
- Restricted-action policy.
- Valid workflow transitions.
- Maximum model steps and tool calls.
- Input and output schemas.
- Evidence identifiers and provenance.
- URL safety.
- Privacy boundaries.
- Final QA acceptance.
- File output.

---

## Framework Direction

Use a structured tool-calling framework, with `smolagents.ToolCallingAgent` as the planned implementation target.

The framework layer will provide:

- JSON-based model tool calls.
- Explicit registered tool lists.
- Multi-step execution.
- Managed specialist agents or delegation tools.
- Maximum-step controls.
- Step callbacks or trace capture.
- Full agent-run results for validation.

The implementation must not simulate tool calling by having procedural Python choose a tool and then merely report that the agent called it.

---

## Bundle Phases

## Phase RB-1: Tool-Calling Foundation

### Objective

Create the reusable infrastructure required for traceable model-selected tool execution.

### Deliverables

```text
src/support_scout/agentic/
├── __init__.py
├── model_adapter.py
├── agent_runner.py
├── tool_context.py
├── tool_registry.py
├── trace_recorder.py
└── result_parsers.py
```

### Scope

- Add the agent framework dependency.
- Adapt the existing OpenAI-compatible Udacity model endpoint to the agent framework.
- Define agent execution configuration.
- Define tool execution context.
- Define structured trace schemas.
- Add scripted offline model behavior for tests.
- Enforce model-step and tool-call limits.
- Validate tool arguments and results.

### Exit Criteria

- A minimal agent selects and calls a controlled test tool.
- The tool call is visible in an execution trace.
- Invalid tool arguments fail deterministically.
- Execution stops at configured limits.
- Tests run without external API keys.

---

## Phase RB-2: Tool-Calling Research Agent

### Objective

Replace the planning-only research component with an LLM-powered agent that selects and invokes research tools.

### Tools

```text
web_search
validate_source_url
fetch_web_page
prepare_public_evidence
submit_research_result
```

### Refactor Outcome

The procedural orchestrator will no longer loop through search queries or scrape results. The Research Agent will select the query, invoke search, choose URLs, invoke scraping, and submit a structured evidence result.

### Deterministic Controls

- URL policy.
- Search and scrape budgets.
- Content limits.
- Evidence ID assignment.
- Content hashing.
- Conflict and insufficiency checks.

### Exit Criteria

- Traces prove the Research Agent called search and scraping tools.
- Public evidence remains `EV-*` provenance-tracked.
- Insufficient or conflicting evidence remains an escalation condition.

---

## Phase RB-3: Tool-Calling Support Agent

### Objective

Make the Support Agent responsible for selecting and invoking operational tools.

### Tools

```text
get_order_status
get_shipment_status
get_return_status
get_account_diagnostics
get_checkout_diagnostics
retrieve_public_evidence
submit_support_draft
```

### Refactor Outcome

The procedural orchestrator will no longer call `OperationalDiagnosticsService.gather()` as the primary live path. The Support Agent will inspect the ticket and choose the appropriate operational tools.

### Deterministic Controls

- Read-only API operations.
- Identifier validation.
- Evidence ID generation.
- Restricted-action blocking.
- SupportDraft schema validation.
- Evidence citation validation.

### Exit Criteria

For `My order ORD-1001 is delayed`, the trace must show the Support Agent selecting order and shipment tools. The orchestrator must not choose those tools directly.

---

## Phase RB-4: Tool-Calling QA Agent

### Objective

Replace the function-style QA component with a tool-calling QA agent while retaining deterministic final authority.

### Tools

```text
validate_evidence_ids
check_restricted_claims
check_sensitive_data
check_operational_grounding
check_public_guidance_grounding
request_support_revision
submit_qa_decision
```

### Refactor Outcome

The QA Agent will select and invoke verification tools, inspect their results, and submit an `APPROVE`, `REVISE`, or `ESCALATE` recommendation.

### Deterministic Controls

- Policy checks are authoritative.
- Agent approval cannot override a deterministic violation.
- Revision loops remain bounded.
- Escalation remains mandatory for restricted actions.

### Exit Criteria

- QA traces contain model-selected validation tool calls.
- Adversarial content cannot be approved when deterministic checks fail.
- Revision and escalation behavior remains bounded and reproducible.

---

## Phase RB-5: Agentic Orchestrator

### Objective

Replace procedural sequencing decisions with an LLM-powered orchestrator agent that delegates to specialist agents.

### Proposed Structure

```text
src/support_scout/orchestration/
├── __init__.py
├── orchestrator_agent.py
├── workflow_kernel.py
├── delegation_tools.py
├── state_tools.py
├── policy_tools.py
└── completion_tools.py
```

### Orchestrator Tools

```text
inspect_workflow_state
delegate_to_triage
delegate_to_research
delegate_to_support
delegate_to_qa
delegate_to_documentation
request_state_transition
escalate_workflow
finalize_workflow
```

### Two-Layer Design

#### OrchestratorAgent

- Chooses the next specialist.
- Delegates tasks.
- Reviews specialist results.
- Decides whether to research, draft, revise, document, escalate, or finalize.

#### DeterministicWorkflowKernel

- Owns valid state transitions.
- Enforces execution budgets.
- Enforces immutable policy.
- Owns evidence registries.
- Enforces terminal states.
- Persists artifacts.

### Exit Criteria

- The orchestrator is a real tool-calling agent.
- Its trace proves delegation to specialists.
- Invalid state transitions are rejected by the kernel.
- Procedural specialist sequencing is removed from the primary `run()` path.

---

## Phase RB-6: Tool-Calling Documentation Agent and Full Mesh

### Objective

Complete the tool-calling specialist mesh and validate the complete delegated workflow.

### Documentation Tools

```text
select_public_evidence
check_article_privacy
validate_article_citations
submit_article
```

### Privacy Invariant

```text
Support response:
    OP-* and EV-* permitted

Reusable article:
    EV-* only

Deterministic privacy validator:
    final authority
```

### Exit Criteria

A complete trace must show:

```text
OrchestratorAgent
    -> TriageAgent
    -> ResearchAgent
        -> web_search
        -> fetch_web_page
    -> SupportAgent
        -> get_order_status
        -> get_shipment_status
    -> QAAgent
        -> validate_evidence_ids
        -> check_restricted_claims
    -> DocumentationAgent
        -> select_public_evidence
        -> check_article_privacy
    -> finalize_workflow
```

---

## Migration Strategy

Use configuration-controlled migration:

```env
SUPPORTSCOUT_EXECUTION_MODE=deterministic
```

Supported modes:

```text
deterministic
agentic
shadow
```

### deterministic

Runs the current validated workflow.

### agentic

Runs the tool-calling specialist mesh and agentic orchestrator as the primary path.

### shadow

Runs the deterministic workflow as authoritative and executes the agentic workflow for trace and output comparison.

The deterministic implementation will not be removed until the agentic path passes all bundle validation gates.

---

## Major Deliverables

### Agent Infrastructure

- Model adapter.
- Tool registry.
- Tool execution context.
- Trace recorder.
- Scripted test model.
- Result parsers.

### Agents

- Tool-calling Research Agent.
- Tool-calling Support Agent.
- Tool-calling QA Agent.
- Tool-calling Documentation Agent.
- Agentic Orchestrator.

### Deterministic Kernel

- State transition enforcement.
- Policy enforcement.
- Evidence registry.
- Tool budgets.
- Final acceptance logic.
- Safe file outputs.

### Testing

- Tool contract tests.
- Agent tool-selection tests.
- Delegation tests.
- Deterministic veto tests.
- Shadow comparison tests.
- Integration tests.
- Adversarial tests.
- Live tool-call validation.

### Documentation

- Updated architecture diagram.
- Tool catalog.
- Agent catalog.
- Agent prompt decision log.
- Trace examples.
- Updated README.
- Refactor Bundle validation record.

---

## Implementation Order

1. Freeze the current deterministic baseline and record its test count.
2. Add agentic infrastructure without changing runtime behavior.
3. Implement and validate the Research Agent.
4. Implement and validate the Support Agent.
5. Implement and validate the QA Agent.
6. Implement the deterministic workflow kernel.
7. Implement the Orchestrator Agent.
8. Implement and validate the Documentation Agent.
9. Add shadow mode and compare both paths.
10. Promote agentic mode only after all gates pass.

---

## Risks and Mitigations

### Risk: Agents avoid tools and answer directly

Mitigation:

- Instructions require tool use for applicable tasks.
- Final answer checks require expected tool-call traces.
- Tests fail if required tools were not called.

### Risk: Agents call irrelevant tools

Mitigation:

- Narrow per-agent tool lists.
- Tool descriptions define exact applicability.
- Tool and step budgets.
- Negative tool-selection tests.

### Risk: Agent retries loop indefinitely

Mitigation:

- Maximum steps.
- Maximum calls per tool.
- Deterministic timeout and circuit-breaker handling.

### Risk: Orchestrator bypasses required stages

Mitigation:

- Workflow kernel validates transitions.
- Finalization requires mandatory state and artifact checks.

### Risk: QA agent approves unsafe output

Mitigation:

- Deterministic validators remain final authority.
- Restricted claims create mandatory escalation regardless of agent recommendation.

### Risk: Operational data enters reusable documentation

Mitigation:

- Documentation Agent receives privacy tools.
- Deterministic article validator permits only `EV-*` citations.

### Risk: Agentic refactor breaks existing behavior

Mitigation:

- Preserve deterministic mode.
- Add shadow comparison mode.
- Require existing regression and adversarial suites to remain green.

---

## Bundle Completion Decision

The bundle is complete only when all phases are validated and the final live trace proves both of the following:

1. Specialist agents selected and invoked their own tools.
2. The Orchestrator Agent selected and invoked specialist agents.

Passing output-quality tests without observable agent tool calls is insufficient.
