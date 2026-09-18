# Phases 23-24 Plan: Orchestration and CLI

## Purpose

Connect every validated component into one explicit workflow and expose it through a simple, reproducible CLI. The orchestrator owns state transitions, dependency order, bounded retries, revision handling, escalation, audit events, and final output.

## Target Flow

```text
CLI -> load config -> load/validate ticket -> safety/triage
-> research/search/url policy/scrape/evidence
-> support draft -> QA -> revision or escalation
-> documentation -> safe file output -> exit code
```

## Implementation Sequence

1. Implement dependency container or constructor injection.
2. Implement workflow-state initialization and audit helper.
3. Implement each transition in roadmap order.
4. Implement early escalation and controlled failure branches.
5. Implement QA revision loop with configured limit.
6. Implement terminal output writing.
7. Implement CLI argument parsing and exit-code mapping.
8. Add mocked orchestrator and CLI tests.
9. Update README commands only after tests pass.

## CLI Scope

Required options: input JSON path; optional output directory; optional cache behavior if implemented; `--help`; and an explicitly opt-in live mode if the implementation distinguishes offline fixtures from live providers. The CLI shall not expose or accept API keys as command-line arguments.

## Deliverables

- `orchestrator.py`
- Completed `main.py`
- Dependency wiring
- Workflow/audit helpers
- CLI and orchestrator tests
- Updated README run command
- Completed validation

## Exit Criteria

- Mocked happy path reaches `completed`.
- Mandatory escalation reaches `escalated`.
- Dependency/file failures reach `failed` or defined escalation.
- Invalid input has a nonzero exit code and controlled message.
- No expected user error emits a raw secret-bearing traceback.
- Required output files are written for terminal outcomes.

## Recommended Commit

`feat: integrate SupportScout orchestrator and CLI`
