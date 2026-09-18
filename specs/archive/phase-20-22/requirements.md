# Phases 20-22 Requirements

## Support Specialist Agent

**CG-001** The agent shall accept sanitized ticket context, classification, sentiment, escalation state, and `ScrapedEvidence[]`.

**CG-002** It shall return a validated `SupportDraft` with issue summary, customer response, ordered troubleshooting steps, evidence IDs, unresolved questions, and limitations.

**CG-003** Every material factual troubleshooting step shall reference a supplied evidence ID.

**CG-004** It shall not invent customer-specific order, account, payment, delivery, or refund status.

**CG-005** It shall preserve mandatory escalation and never claim a restricted action was completed.

## QA Agent

**QA-001** The QA Agent shall consume the draft, evidence, classification, sentiment, and escalation policy.

**QA-002** It shall return `approve`, `revise`, or `escalate`.

**QA-003** It shall check evidence grounding, factual consistency, completeness, tone, privacy, source identifiers, restricted-action claims, and unsupported certainty.

**QA-004** Revision instructions shall identify observable defects without exposing hidden reasoning.

**QA-005** Unknown evidence IDs, copied secrets, unsupported actions, or insufficient evidence shall prevent approval.

## Revision Behavior

The content pipeline shall permit no more than `MAX_AGENT_REVISIONS`. A revision request shall include the prior draft and bounded correction instructions, not the complete audit log. When the limit is reached, the workflow shall escalate and shall not report normal completion.

## Documentation Agent

**DOC-001** The agent shall use only an approved draft and retained evidence, unless generating a limited-information escalation notice.

**DOC-002** It shall produce a validated `TroubleshootingArticle` with title, Markdown body, source evidence IDs, and limitations.

**DOC-003** The article shall describe the general issue, not the individual customer.

**DOC-004** It shall exclude ticket IDs, order references, credentials, payment information, and customer-specific status.

**DOC-005** It shall not convert uncertain or conflicting evidence into definitive guidance.

## Prompt Requirements

Each prompt shall define role, permitted inputs, required structured output, authority limits, untrusted-data boundaries, evidence-use rules, privacy rules, and escalation behavior. Prompt files shall be version controlled without credentials or private chain-of-thought.

## Post-Generation Controls

Deterministic validators shall confirm Pydantic validity, bounded field lengths, known evidence IDs, no secret-like content, no unsupported completion claim, and required limitations. Detection of a violation shall result in revision, rejection, or escalation according to the current phase and revision count.

## Testing Requirements

Mocked tests shall cover all three support domains, refund authorization, missing/conflicting evidence, unknown evidence IDs, prompt injection, sensitive content, unsupported claims, QA revision, revision exhaustion, invalid model JSON, timeout, privacy-safe article generation, and limited-information documentation.

## Acceptance Criteria

A normal completed content pipeline must produce an approved `SupportDraft` and a valid attributed `TroubleshootingArticle`. A restricted, unsafe, or insufficiently supported case must not produce a normal approved response and must preserve a clear human-review path.
