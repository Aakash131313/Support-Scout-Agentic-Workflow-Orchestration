# Technology Stack

> **Regenerated for the agentic refactor.** The previous version listed SmolAgents,
> FastAPI and agent frameworks generally under "Not Selected Initially" and specified
> "a custom Python orchestrator rather than a third-party agent framework". That no
> longer describes the system. Both decisions were reversed during Phases 33-34 and the
> agentic refactor; the rationale is recorded in
> `specs/001-agentic-refactor/research.md`.

## Runtime

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | `StrEnum`, native union syntax, mature async ecosystem |
| Environment | WSL2 (Ubuntu 24.04) + venv | Matches the deployment target; isolated and reproducible |
| Packaging | `pyproject.toml`, src-layout | Editable install removes the need for `PYTHONPATH` juggling |
| Interface | CLI (`argparse`) | Three subcommands: `run`, `chat`, `serve` |

## Agent framework

**Selected: `smolagents`.**

Every specialist and the orchestrator are `ToolCallingAgent` instances. Tools are
plain functions decorated with `@tool`; smolagents derives each tool's name,
description and argument schema from the function signature and docstring.

Why this replaced the custom orchestrator:

- The custom orchestrator was a pipeline. Sequencing was hard-coded, so the model
  never actually chose anything. That failed the central requirement.
- `@tool` functions keep the tool contract readable in one place. What a reviewer reads
  is exactly what the model is shown.
- A real tool-calling loop gives a genuine trace of decisions, which is what makes the
  agent's behaviour auditable.

What was kept from the custom approach: the deterministic workflow kernel. The agent
chooses; the kernel decides whether that choice is legal. Explicit state, validated
transitions and mandatory escalation all survive the move.

## Model access

| Component | Choice |
|---|---|
| Provider | OpenAI-compatible endpoint (Udacity Vocareum proxy) |
| Adapter | `smolagents.OpenAIServerModel`, constructed in `agents/model_adapter.py` |
| Isolation | Agents receive a built model object; they never see a key, base URL or provider name |

Swapping providers is a change to `model_adapter.py` alone.

## Operations data service

**Selected: FastAPI + SQLModel + SQLite.**

A standalone read-only service (`data_server/`) exposes synthetic operational records.
SupportScout reaches it only through `SupportDataClient`, which is also the seam the
offline test suite replaces.

It is read-only by construction: there is no POST, PUT, PATCH or DELETE route anywhere
in the service, so no agent can modify an order, account or refund even by accident.

## Research tools

| Component | Choice | Bound |
|---|---|---|
| Search | Tavily via `TavilyAdapter` | Result count, deduplication, identifier stripping |
| URL safety | `URLPolicy` with injectable DNS resolution | Public HTTP(S) only; private, loopback, link-local and reserved addresses rejected |
| Retrieval | `requests` + BeautifulSoup | Timeout, byte size, content type, retained characters, redirect revalidation |

## Contracts and validation

- **Pydantic v2** for every data contract. `extra="forbid"` throughout, so an unexpected
  field is an error rather than silent drift.
- `WorkflowState` uses `validate_assignment=True`, which catches malformed state
  mutation at the point it happens.
- Deterministic validators (`safety_rules`, `content_validation`) hold final authority
  over restricted actions, secret leakage and article privacy.

## Logging and observability

| Sink | Path | Contents |
|---|---|---|
| Trace | `logs/<run_id>/trace.jsonl` | Agent steps, tool calls, tool results, delegations, state transitions, HITL decisions |
| Error audit | `logs/errors.jsonl` | Append-only across runs; one `StructuredError` per caught failure, including failures raised inside tools |
| Console | stdout | Readable `[AGENT INSIGHT]` blocks for live demonstration |

Everything written passes through `redact()` first, which strips API keys, tokens,
passwords, card numbers and national identifiers, and drops raw customer message bodies.

## Testing

| Layer | Approach |
|---|---|
| Unit | Tools, validators, kernel, registry, artifacts, logging |
| Integration | Real orchestrator and real tools; only the model's choices and the network are faked |
| Adversarial | AT-001 to AT-020 plus AT-016A, named to match the matrix |
| Evaluation | Curated deterministic baseline with numerator/denominator reporting |

The suite is offline by default: `pytest` passes with no API keys and no network.

## Not selected

| Option | Why not |
|---|---|
| LangChain / LangGraph | Heavier abstraction than this workflow needs; `@tool` is more legible |
| OpenAI Agents SDK | Would couple the project to one provider |
| Vector database / RAG | Evidence is retrieved live per ticket; there is no corpus to index |
| Async orchestration | One ticket at a time; concurrency would add tracing complexity for no gain |
| Web UI | CLI keeps the surface reviewable and the workflow inspectable |
