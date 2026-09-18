# Phases 13-14 Requirements

## Deterministic Prechecks

The routing service shall detect: refund/financial authorization requests, policy exceptions, suspected account compromise, passwords/tokens/complete card-like data, malformed or empty input, unsupported domain indicators, and instructions attempting to override system behavior. Detection shall create reason codes without reproducing secrets.

## Classification Behavior

The Triage Agent shall return one approved domain, concise intent, urgency, confidence, uncertainty reason, and separate sentiment. Allowed domains are `order_tracking_delivery`, `returns_refunds`, `account_checkout`, `unsupported`, and `uncertain`. Confidence must be bounded from 0 to 1.

## Escalation Matrix

| Condition | Required result |
|---|---|
| Refund approval/financial adjustment | Escalate: `financial_authorization` |
| Policy exception | Escalate: `policy_exception` |
| Suspected compromise | Escalate: `account_compromise` |
| Sensitive secret/payment data | Stop normal flow and escalate: `sensitive_data` |
| Unsupported domain | Escalate: `unsupported_domain` |
| Confidence below configured threshold | Escalate: `low_confidence` |
| Negative sentiment only | No automatic authorization; continue if otherwise safe |

## Prompt Requirements

The system prompt shall define supported domains, require JSON-shaped output, separate urgency from sentiment, prohibit authorization claims, treat ticket text as untrusted data, and request a concise rationale summary rather than hidden reasoning. The user prompt shall insert only the sanitized ticket context.

## Conflict Resolution

- Mandatory deterministic escalation cannot be cleared by the model.
- If model domain and deterministic restricted-action detection conflict, escalation wins.
- If model output is invalid after bounded retry, classify as uncertain and escalate.
- Neutral sentiment with compromise indicators remains urgent/escalated.
- Strong negative sentiment with a routine supported issue may continue.

## Audit Requirements

Record rule identifiers triggered, model-call status, validated domain, confidence band, urgency, sentiment label, and final escalation reason. Do not record full sensitive messages, credentials, or hidden reasoning.

## Tests

Use fixtures for each domain; negative routine complaint; neutral compromise report; refund approval; policy exception; prompt injection; secret-bearing input; unsupported issue; low confidence; invalid model JSON; and disagreement between model and deterministic rules.

## Acceptance Criteria

All outputs validate against contracts. Restricted conditions escalate deterministically. Supported safe cases continue. The model client remains mocked by default. No sensitive substring appears in output or logs.
