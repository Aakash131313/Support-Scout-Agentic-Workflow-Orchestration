# Phases 13-14 Plan: Triage and Classification

## Purpose

Implement a hybrid intake layer in which deterministic safety rules constrain model-assisted classification. The result is a validated domain, intent, sentiment, urgency, confidence, and escalation decision.

## Inputs and Outputs

**Input:** `SupportTicket`

**Outputs:** `TicketClassification`, `SentimentAssessment`, `EscalationDecision`, and audit events.

## Implementation Sequence

1. Define normalized text and safe pattern helpers.
2. Implement deterministic prechecks for sensitive data, restricted actions, compromise, malformed input, and obvious unsupported scope.
3. Implement Triage Agent prompt and structured response.
4. Validate model output through Pydantic.
5. Apply deterministic post-classification policy.
6. Resolve confidence and rule conflicts in favor of safety.
7. Add unit, adversarial, and evaluation fixtures.

## Authority Ordering

Deterministic safety rules override model recommendations. The model may interpret ambiguity but cannot clear a mandatory escalation. Sentiment affects tone and prioritization, not authorization.

## Deliverables

- `services/routing_service.py`
- `agents/triage_agent.py`
- `prompts/triage-agent.md`
- Unit and adversarial tests
- Completed validation

## Exit Criteria

Three supported domains classify through mocked fixtures; mandatory escalation rules always win; uncertain/unsupported cases escalate; sensitive content is not repeated; outputs validate; offline tests pass.

## Recommended Commit

`feat: implement deterministic routing and model-assisted triage`
