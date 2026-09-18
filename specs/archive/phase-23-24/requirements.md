# Phases 23-24 Requirements

## Orchestrator Ownership

The orchestrator shall own `WorkflowState`, transition order, revision count, terminal status, escalation routing, dependency invocation, and sanitized audit events. It shall not contain provider-specific HTTP logic, prompt text, HTML parsing, or low-level file serialization.

## Dependency Injection

Model client, search tool, URL policy, scraper, evidence service, routing service, agents, and file writer shall be injectable so default tests can use fakes or mocks. Live dependencies shall be created only after configuration is validated.

## State Transitions

Allowed progression shall follow the architecture. Invalid transitions shall raise a controlled workflow error. Only `completed`, `escalated`, and `failed` are terminal. Once terminal, no additional model or network operation may execute.

## Escalation and Failure Rules

- Input/safety failures do not retry.
- Mandatory escalation stops normal generation unless limited-information output is required.
- Retryable model/network failures use bounded configuration.
- QA revision is bounded.
- File-writing failure produces `failed`, never `completed`.
- Partial tool failure may continue only when sufficient supported evidence remains.

## Audit Requirements

Record state, step, status, sanitized counts, evidence IDs, QA outcome, escalation reason, error category, and terminal result. Do not record credentials, headers, hidden reasoning, full sensitive messages, or complete unreviewed page content.

## CLI Requirements

**CLI-001** Accept exactly one input JSON path.

**CLI-002** Support `--help` without live credentials.

**CLI-003** Allow safe output-root override.

**CLI-004** Reject missing/unreadable input with nonzero exit status.

**CLI-005** Do not accept API keys on the command line.

**CLI-006** Print a concise terminal summary containing ticket ID, terminal status, escalation reason if any, and output path.

**CLI-007** Avoid raw traceback for expected user/configuration errors.

## Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Completed successfully |
| 2 | Input or configuration error |
| 3 | Escalated for human review |
| 4 | Dependency or controlled workflow failure |
| 5 | Output-writing failure |

Exact constants shall be documented and tested.

## Output Behavior

Completed and escalated runs shall write sanitized standardized artifacts. Failed runs shall write an audit/error summary only if the output layer is functional and doing so cannot misrepresent completion.

## Testing Requirements

Tests shall cover completed delivery/return/checkout flows, early escalation, insufficient evidence, QA revision, revision exhaustion, search/scrape/model failures, file failure, invalid transition, invalid CLI input, help invocation, exit-code mapping, and output summaries. All default tests shall use injected mocks.

## Acceptance Criteria

One documented CLI command processes a synthetic ticket end to end with mocked dependencies. Every terminal branch is reproducible, reflects the correct exit code, and writes only truthful sanitized output.
