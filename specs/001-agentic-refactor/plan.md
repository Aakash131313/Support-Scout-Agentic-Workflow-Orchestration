# Implementation Plan: Agentic Workflow Refactor

**Spec:** `spec.md` | **Decisions:** `research.md` | **Contracts:** `data-model.md`

## Constitution check

| Principle | How this plan satisfies it |
|---|---|
| I. Human authority | Screening before any model call; kernel-invoked HITL gate; restricted-claim detection in QA |
| II. Evidence before confidence | `EvidenceRegistry` mints all identifiers; submission tools reject unknown ones |
| III. Deterministic controls outrank models | Kernel validates every transition; failed checks block approval at the tool boundary |
| IV. Privacy by construction | `ArticlePrivacyValidator` on all eight identifier families; `redact()` on every write |
| V. Honest limitation | Insufficient and conflicting evidence escalate; evaluation reports numerator/denominator |
| VI. Auditability | Run-scoped JSONL trace; append-only error audit; artifacts in a `finally` block |
| VII. Offline reproducibility | Injectable dependencies; scripted agent harness; no keys needed |

## Architecture

```
                      ┌──────────────────────────┐
   ticket.json ──────▶│   OrchestratorAgent      │  ToolCallingAgent
                      │   (chooses next step)    │
                      └────────────┬─────────────┘
                                   │ delegate_to_* @tool
                      ┌────────────▼─────────────┐
                      │    WorkflowKernel        │  deterministic authority
                      │  transitions · escalation│
                      │  budgets · HITL gate     │
                      └────────────┬─────────────┘
          ┌──────────┬─────────────┼─────────────┬──────────────┐
          ▼          ▼             ▼             ▼              ▼
       Triage    Research      Support          QA        Documentation
      (3 tools) (5 tools)     (7 tools)     (6 tools)      (4 tools)
                     │             │
                     ▼             ▼
               Tavily · URL     Operations
               policy · scraper  service (read-only)
                     │             │
                     └──────┬──────┘
                            ▼
                    EvidenceRegistry
                  EV-NNN  ·  OP-NNN
```

The orchestrator chooses. The kernel decides whether the choice is legal. Specialists
do the work through tools. The registry owns provenance.

## Project structure

```
src/support_scout/
├── main.py                  CLI: run · chat · serve
├── config.py                environment settings and budgets
├── schemas.py               every Pydantic contract
├── exceptions.py            sanitized exception hierarchy
├── logging_config.py        redaction · JSONL trace · error audit
├── evidence_registry.py     deterministic EV-/OP- minting
├── hitl.py                  the single human approval gate
├── artifacts.py             safe artifact writing
├── agents/                  six ToolCallingAgents + model adapter
├── tools/                   six @tool modules
├── services/                deterministic validators and research services
├── clients/                 operations service HTTP client
├── workflow/                kernel + assembly
└── prompts/                 prompt documentation and decision log
```

## Implementation sequence

1. **Contracts** — schemas, exceptions, config, logging. Everything else depends on these.
2. **Determinism** — safety rules, content validation, URL policy, evidence rules.
   Written and tested before any agent exists, because they hold final authority.
3. **Registry and HITL** — provenance and human authority primitives.
4. **Tools** — one module per specialist, each a factory over a workspace.
5. **Kernel** — transitions, escalation, revision loop, budgets.
6. **Agents** — five specialists, then the orchestrator over delegation tools.
7. **Assembly and CLI** — one wiring path, three subcommands.
8. **Tests** — unit, integration (IT-001 to IT-008), adversarial (AT-001 to AT-020).
9. **Documentation** — README, CLAUDE.md, prompts, diagram, evaluation.

## Removals

| Removed | Reason |
|---|---|
| `agentic/execution_mode.py` | Agentic is the only path |
| `agentic/shadow_orchestrator.py` | Migration scaffolding, retired per R-011 |
| `agentic/specialist_adapters.py` | Replaced by kernel-applying runner closures |
| `agentic/agent_runner.py` | Dead stub; real tracing comes from run results |
| `agentic/tool_registry.py`, `tool_context.py`, `trace_recorder.py`, `agentic/schemas.py` | Dead stubs, unused by any agent |
| `agents/` (legacy) | Superseded by tool-calling specialists |
| `orchestrator.py` | The pipeline this refactor replaces |
| `services/operational_diagnostics_service.py` | Tool selection is now the agent's job |
| `services/content_pipeline.py` | Revision loop moved into the kernel |
| `services/routing_service.py` | Replaced by token-based `safety_rules.py` |
| `services/model_client.py` | No caller once triage became agentic |
| `data_server/schemas.py::OperationalEvidence` | Duplicate definition; would drift |

## Risks

| Risk | Mitigation |
|---|---|
| Agent loops or stalls | Step and tool-call budgets; structured failure observations; no identical retry |
| Model fabricates evidence | Registry-minted identifiers; submission-time rejection |
| Refactor silently drops a safety property | Adversarial suite named to the AT matrix; deterministic validators tested independently |
| Tool descriptions drift from behaviour | Descriptions derive from the function itself; a registration test asserts the expected set |
