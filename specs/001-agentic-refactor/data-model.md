# Data Model

Every contract is a Pydantic v2 model in `src/support_scout/schemas.py` with
`extra="forbid"`. An unexpected field is an error, not silent drift.

## Input

**SupportTicket** — `ticket_id` (safe charset, ≤64), `created_at`, `customer_message`
(1–8000 chars), `order_reference` (optional, normalised upper-case),
`customer_reference` (optional, `^CUS-[0-9]+$`).

`customer_reference` is new. See `research.md` R-010.

## Triage

**TicketClassification** — `domain` (5-value enum), `intent`, `urgency` (4-value),
`confidence` (0.0–1.0), `uncertainty_reason`.

**SentimentAssessment** — `label`, `intensity`, `rationale_summary`. Advisory only.

**EscalationDecision** — `required`, `reason_code` (13-value enum), `summary`,
`recommended_human_action`.

## Evidence

| Model | Identifier | Meaning |
|---|---|---|
| `ScrapedEvidence` | `^EV-[0-9]{3,}$` | Public web guidance; reusable in documentation |
| `OperationalEvidence` | `^OP-[0-9]{3,}$` | Customer-specific record; never in documentation |

The prefix is a privacy boundary, not a naming convention. Both are minted only by
`EvidenceRegistry`.

**SearchResult** — `title`, `url` (HttpUrl), `snippet`, `rank`.

## Content

**SupportDraft** — `issue_summary`, `customer_response`, `troubleshooting_steps`,
`evidence_ids`, `unresolved_questions`, `limitations`.

**QAResult** — `decision` (approve/revise/escalate), `issues`,
`revision_instructions`, `escalation_reason`.

**TroubleshootingArticle** — `title`, `body_markdown`, `source_evidence_ids` (EV only),
`limitations`.

## Tracing and audit

| Model | Purpose |
|---|---|
| `ToolCallRecord` | One tool invocation with sanitized arguments |
| `AgentRunRecord` | One agent execution with its tool sequence |
| `DelegationRecord` | One orchestrator delegation and its resulting state |
| `HumanApprovalDecision` | The HITL gate outcome, approver and notes |
| `StructuredError` | `error_category`, `agent_name`, `tool_name`, `retryable`, `safe_message` |
| `AuditEvent` | Sanitized workflow event for `audit_log.json` |
| `InteractionSummary` | The written ticket-interaction summary artifact |

## Workflow state

**WorkflowState** — `validate_assignment=True`, so malformed mutation fails where it
happens rather than surfacing later.

```
received → validated → triaged → researched → drafted ─┬→ qa_approved → documented → completed
                                                        └→ qa_revision_requested → drafted
```

`escalated` is reachable from every non-terminal state and is a legitimate finalizable
outcome. `failed` is reachable from every non-terminal state.
`awaiting_human_approval` is transient, entered and left by the kernel around the gate.

## State transition table

| From | Permitted targets |
|---|---|
| `received` | validated, escalated, failed |
| `validated` | triaged, escalated, failed |
| `triaged` | researched, escalated, failed |
| `researched` | drafted, escalated, failed |
| `drafted` | qa_approved, qa_revision_requested, escalated, failed |
| `qa_revision_requested` | drafted, escalated, failed |
| `qa_approved` | documented, escalated, failed |
| `documented` | completed, escalated, failed |

## Delegation preconditions

| Specialist | Required state |
|---|---|
| triage | `validated` |
| research | `triaged` |
| support | `researched` or `qa_revision_requested` |
| qa | `drafted` |
| documentation | `qa_approved` |

Support appears twice because a QA-requested revision re-enters drafting. State
validation is the single mechanism preventing out-of-order or repeated delegation.
