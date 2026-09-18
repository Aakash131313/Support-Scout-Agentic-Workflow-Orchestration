# Phases 9-12 Plan: Foundation Layer

## Purpose

Implement the minimum reliable platform required by every later SupportScout phase: package structure, configuration, Pydantic contracts, safe file output, and an isolated client for the Udacity-provided model endpoint.

## Authoritative Inputs

- `mission.md`: accuracy-first e-commerce support, evidence grounding, human escalation, privacy.
- `tech_stack.md`: Python 3.11+, WSL2, CLI, custom orchestrator, Pydantic, Pytest, Udacity model endpoint.
- `roadmap.md`: Phases 9 through 12.
- Phase 5-7 architecture and data contracts.
- Phase 8 offline-first test strategy.

## Scope

**In scope**
- Python package and CLI skeleton
- Environment-based settings
- Custom exceptions and sanitized logging
- Pydantic enums and models
- Safe JSON and Markdown writer
- Provider-isolated model client
- Unit tests and mock model transport

**Out of scope**
- Triage rules, classification, Tavily, scraping, agents, orchestration, and live customer systems.

## Target Structure

```text
src/support_scout/
├── __init__.py
├── main.py
├── config.py
├── exceptions.py
├── logging_config.py
├── schemas.py
├── tools/file_writer.py
└── services/model_client.py
tests/unit/
├── test_config.py
├── test_schemas.py
├── test_file_writer.py
└── test_model_client.py
```

## Implementation Sequence

1. Create package directories and `__init__.py` files.
2. Implement typed settings with safe defaults and missing-key validation.
3. Define project exception hierarchy and sanitized logging.
4. Implement Phase 5-7 schemas and enums.
5. Implement safe ticket-directory and file-writing functions.
6. Define model transport protocol and Udacity adapter.
7. Add structured response extraction, bounded retry, timeout, and error mapping.
8. Add offline unit tests.
9. Run tests and complete validation.

## Design Rules

- No agent directly reads environment variables.
- No agent directly invokes the Udacity transport.
- No output path is constructed from an unsanitized ticket ID.
- No credentials, headers, full environment dumps, or hidden reasoning are logged.
- Default tests make no network calls.
- File-writing failure cannot be reported as completion.

## Deliverables

- Runnable package skeleton
- `config.py`, `exceptions.py`, `logging_config.py`, `schemas.py`
- `tools/file_writer.py`
- `services/model_client.py`
- Unit tests and fixtures
- Completed `phase-9-12-validation.md`

## Exit Criteria

- CLI help or placeholder command runs.
- Settings validate and secrets remain hidden.
- Every approved contract has a Pydantic implementation.
- Valid schema fixtures pass and invalid fixtures fail.
- File writer blocks traversal and writes stable UTF-8/JSON.
- Model client is mockable and maps failures safely.
- Offline tests pass.

## Recommended Commit

`feat: build SupportScout foundation schemas file output and model client`
