# SupportScout

An agentic customer-support workflow for e-commerce. Six tool-calling agents,
coordinated by an agentic orchestrator, grounded in real evidence and bounded by a
deterministic kernel.

SupportScout reads a support ticket, classifies it, researches public guidance, looks up
read-only operational records, drafts a reply, reviews that reply against deterministic
checks, and publishes a reusable troubleshooting article. Where a human decision is
required, it stops and asks.

---

## What makes it agentic

Every capability is a real `@tool` function. The model chooses which tools to call and
in what order; nothing is sequenced in advance.

```python
@tool
def get_shipment_status(order_id: str) -> str:
    """Look up read-only shipment and tracking information for one order.

    Args:
        order_id: An order identifier such as ORD-1001.
    """
```

The orchestrator is itself a `ToolCallingAgent`. Its tools are its specialists:

```
inspect_workflow_state · delegate_to_triage · delegate_to_research
delegate_to_support · delegate_to_qa · delegate_to_documentation · finalize_workflow
```

**The agent chooses; the kernel decides whether the choice is legal.** A
`WorkflowKernel` validates every state transition, enforces escalation, bounds the
revision loop, applies execution budgets and owns the human-in-the-loop gate. A prompt
change cannot bypass any of it.

---

## Architecture

```
ticket.json
    │
    ▼
SafetyScreener ──restricted action──▶ Human approval gate ──denied──▶ ESCALATED
    │ clear                                    │ approved
    ▼                                          ▼
OrchestratorAgent ◀──── inspect_workflow_state ────▶ WorkflowKernel
    │                                                      ▲
    │ delegate_to_*                                        │ apply_*
    ▼                                                      │
Triage → Research → Support → QA → Documentation ──────────┘
   (3)      (5)       (7)     (6)        (4)   tools each
             │         │
             ▼         ▼
      Tavily +    Operations service
      URLPolicy   (read-only FastAPI)
             │         │
             └────┬────┘
                  ▼
           EvidenceRegistry  →  EV-NNN (public) · OP-NNN (operational)
```

Full diagram: `diagrams/architecture.mmd`.

---

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest                                   # offline, no keys needed

cp .env.example .env                     # then fill in your keys
support-scout serve --reseed             # terminal 1
support-scout run sample_inputs/01_order_delay_operational.json   # terminal 2
```

### Commands

| Command | Purpose |
|---|---|
| `support-scout run <ticket.json>` | Run the workflow over one ticket |
| `support-scout chat` | Interactive session, one ticket per message |
| `support-scout serve` | Start the synthetic operations service |

| Exit code | Meaning |
|---:|---|
| 0 | Completed |
| 2 | Invalid input or configuration |
| 3 | Escalated to a human |
| 4 | Workflow failure |
| 5 | Output error |

---

## The agents

| Agent | Tools | Responsibility |
|---|---:|---|
| **Orchestrator** | 7 | Chooses which specialist runs next |
| **Triage** | 3 | Domain, urgency, sentiment |
| **Research** | 5 | Public guidance: search, validate, fetch, assess |
| **Support** | 7 | Selects operational lookups, drafts the reply |
| **QA** | 6 | Four deterministic checks, then approve/revise/escalate |
| **Documentation** | 4 | Privacy-safe reusable article |

The Support Agent decides which operational tools are worth calling. A delayed-delivery
question triggers order and shipment lookups and leaves return, account and checkout
alone.

---

## Safety model

### Human authority
SupportScout never approves a refund, authorizes a payment, grants a policy exception,
or modifies an order or account.

Nine conditions escalate to a human. Three of them — financial authorization, policy
exception, suspected account compromise — are *restricted actions* and fire the single
human-in-the-loop gate:

```
==================== HUMAN APPROVAL REQUIRED ====================
Restricted action : Continue automated handling despite financial_authorization
Reason code       : financial_authorization
SupportScout cannot perform this action on its own authority.
=================================================================
Approve? [y/N]:
```

Unattended, the default policy denies and the run escalates. The safety property holds
with no operator present. The other six conditions route to a human queue without
interrupting the customer.

### Evidence, not assertion
Evidence identifiers are minted by `EvidenceRegistry`, never by a model. `OP-` grounds
customer-specific facts; `EV-` grounds general guidance. Submission tools reject any
identifier the registry did not issue, so a fabricated citation cannot reach a customer.

### Deterministic screening
Safety rules run before any model call and use token co-occurrence rather than phrase
matching, so paraphrases are caught:

| Input | Outcome |
|---|---|
| "Please approve refund" | escalated |
| "please refund me" | escalated |
| "I want my money back" | escalated |
| "can you authorize a refund" | escalated |
| "How do I return an unopened item?" | handled normally |

Restricted-claim detection works the same way: "I approved your refund", "I've approved
your refund", "Your refund is approved" and "refund has been authorized" are all caught.

### Privacy
Reusable articles are scanned deterministically for all eight identifier families —
`OP-`, `ORD-`, `CUS-`, `SHP-`, `RET-`, `CHK-`, `ACC-`, `TKT-` — plus emails and tracking
numbers, across title, body, citations and limitations.

### Sentiment does not confer authority
Sentiment shapes tone and priority. An angry customer with a routine question gets a
warmer reply and normal handling. A calm customer reporting account compromise is
escalated immediately.

---

## Logging

Logging is first-class. Three sinks, all redacted:

| Sink | Path | Contents |
|---|---|---|
| Trace | `logs/<run_id>/trace.jsonl` | Agent steps, tool calls, results, delegations, transitions, human decisions |
| Error audit | `logs/errors.jsonl` | Append-only across runs; one `StructuredError` per caught failure, including inside tools |
| Console | stdout | Readable `[AGENT INSIGHT]` blocks |

```json
{"agent_name":"support_agent","event":"tool_called","run_id":"a3f2c1","step_number":2,
 "tool_name":"get_shipment_status","tool_arguments":{"order_id":"ORD-1001"}}
```

`redact()` strips API keys, bearer tokens, card numbers and national identifiers, and
drops raw customer message bodies entirely.

---

## Artifacts

Written for **every** terminal state, including escalation and failure:

```
output/<ticket_id>/
├── interaction_summary.json      domain, sentiment, status, escalation, delegations
├── customer_response.md          the customer-facing reply
├── troubleshooting_article.md    reusable, customer-agnostic
├── sources.json                  EV- public evidence
├── operational_sources.json      OP- operational evidence
├── audit_log.json                sanitized workflow events
├── agent_trace.json              full delegation and tool-call trace
└── escalation.json               only when escalated
```

---

## Testing

```bash
pytest                                              # everything, offline
pytest tests/unit tests/integration tests/adversarial
pytest --cov=src/support_scout --cov-report=term-missing
```

The suite runs with no API keys and no network. Integration tests drive the **real**
orchestrator, kernel, tools and registry — only the model's tool choices and external
HTTP are substituted, so the agentic path itself is genuinely exercised.

| Layer | Coverage |
|---|---|
| Unit | Tools, validators, kernel, registry, artifacts, logging, CLI, schemas |
| Integration | IT-001 to IT-008 end-to-end scenarios |
| Adversarial | AT-001 to AT-020 plus AT-016A |
| Contract | Tool registration and the delegation surface |

`tests/TRACEABILITY_MATRIX.md` maps requirements to tests.

---

## Evaluation

```bash
python -m evaluation.evaluation_runner
```

18 curated cases. Every metric reports numerator, denominator and date. This is a
curated deterministic baseline, not production performance, and the report says so.

---

## Project layout

```
support-scout/
├── src/support_scout/
│   ├── main.py · config.py · schemas.py · exceptions.py
│   ├── logging_config.py · evidence_registry.py · hitl.py · artifacts.py
│   ├── agents/      six ToolCallingAgents + model adapter
│   ├── tools/       six @tool modules
│   ├── services/    deterministic validators and research services
│   ├── clients/     operations service client
│   ├── workflow/    kernel + assembly
│   └── prompts/     prompt documentation and decision log
├── src/evaluation/  curated evaluation harness
├── data_server/     synthetic read-only operations service
├── specs/001-agentic-refactor/   SDD bundle (Spec Kit layout)
├── .specify/memory/constitution.md
├── tests/           unit · integration · adversarial
├── sample_inputs/   18 curated tickets
├── docs/            mission · roadmap · tech stack
└── diagrams/        architecture
```

---

## Known limitations

Stated plainly, because overclaiming is its own failure:

- **Conflict detection is a heuristic.** It matches explicit affirmative/negative pairs
  and will miss subtly worded disagreement.
- **Sentiment is lexicon-based.** It does not detect sarcasm or implied frustration.
- **Research is public-web only.** There is no internal policy corpus, so some policy
  questions escalate that a knowledge base could answer.
- **One ticket per run.** No batching or concurrency.
- **Synthetic data throughout.** The operations service contains fabricated records; no
  real customer system is touched.
- **Evaluation is curated.** Frozen fixtures measure the deterministic layer, not live
  model quality.

---

## Documentation

| Document | Contents |
|---|---|
| `.specify/memory/constitution.md` | Non-negotiable principles |
| `specs/001-agentic-refactor/spec.md` | What and why, with acceptance criteria |
| `specs/001-agentic-refactor/plan.md` | How: architecture and sequence |
| `specs/001-agentic-refactor/research.md` | Decisions, alternatives, rationale |
| `specs/001-agentic-refactor/data-model.md` | Contracts and state machine |
| `specs/001-agentic-refactor/quickstart.md` | Step-by-step validation walkthrough |
| `src/support_scout/prompts/` | Prompt documentation and decision log |
| `CLAUDE.md` | Working agreement for AI coding agents |
