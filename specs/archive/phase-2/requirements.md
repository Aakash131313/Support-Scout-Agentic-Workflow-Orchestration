# Phase 2 Requirements: Use Cases

## Common Assumptions
- Input is a local JSON ticket.
- Research uses Tavily and permitted public pages.
- Responses must distinguish sourced guidance from unresolved information.
- Customer-specific secrets are neither requested nor retained.
- Human review remains authoritative for restricted actions.

## UC-01: Delayed Order or Stale Tracking
**Primary actor:** Support specialist  
**Trigger:** A customer reports that an expected delivery is late or tracking has stopped updating.

### Preconditions
- Ticket contains `ticket_id` and `customer_message`.
- Message contains no secret required for research.

### Main Flow
1. Validate the ticket.
2. Classify it as `order_tracking_delivery`.
3. Determine sentiment and urgency.
4. Research general delayed-delivery and tracking guidance.
5. Scrape permitted relevant pages.
6. Prepare attributed evidence.
7. Draft troubleshooting steps without claiming access to the order.
8. Run QA.
9. Write the response, article, summary, sources, and audit log.

### Alternate Flows
- No reliable evidence: produce a limited-information response and escalate.
- Suspected lost or stolen delivery requiring account action: escalate.
- Tracking or order reference is present: treat it as customer-provided context, not proof of status.

### Acceptance Criteria
- Correct domain is selected.
- No invented delivery status appears.
- Each factual troubleshooting claim is supported by evidence.
- Response clearly states that SupportScout cannot inspect or modify the order.

## UC-02: Return or Refund Inquiry
**Primary actor:** Support specialist  
**Trigger:** A customer asks about return eligibility, return steps, refund status, or refund approval.

### Main Flow
1. Validate and classify as `returns_refunds`.
2. Assess sentiment, urgency, and requested action.
3. Research general public return or refund guidance.
4. Generate general troubleshooting or next steps.
5. Escalate any approval, exception, status verification, or financial adjustment.
6. Run QA and write outputs.

### Alternate Flows
- General return-process question: provide sourced guidance.
- Refund approval or policy exception: mandatory human review.
- Conflicting policies: disclose conflict and escalate.

### Acceptance Criteria
- System never states that a refund was approved, issued, denied, or scheduled.
- Financial authorization always routes to a human.
- General guidance retains source attribution.

## UC-03: Account or Checkout Troubleshooting
**Primary actor:** Support specialist  
**Trigger:** A customer reports sign-in, password recovery, checkout, or payment troubleshooting problems.

### Main Flow
1. Validate and classify as `account_checkout`.
2. Detect sensitive information and signs of compromise.
3. Research general troubleshooting guidance.
4. Generate safe steps that do not request secrets.
5. Escalate suspected compromise, payment authorization, or account changes.
6. Run QA and write outputs.

### Alternate Flows
- Customer includes password, token, or complete card data: stop normal processing, avoid reproducing it, and escalate.
- Suspected compromised account: immediate escalation.
- General checkout failure: provide sourced, non-account-specific troubleshooting.

### Acceptance Criteria
- Response never requests a password, authentication token, or complete card number.
- Suspected compromise always escalates.
- The system does not claim to access or repair the account.

## UC-04: Insufficient or Conflicting Evidence
**Trigger:** Search or scraping returns no reliable evidence, or sources materially disagree.

### Required Behavior
- Do not invent a resolution.
- Explain that reliable guidance could not be established.
- Preserve available source metadata.
- Escalate to human review.
- Produce a limited-information troubleshooting article rather than unsupported instructions.

## UC-05: Unsupported Issue
**Trigger:** Ticket is outside the three supported domains or confidence is insufficient.

### Required Behavior
- Mark the domain as unsupported or uncertain.
- Do not force-fit the issue into a supported category.
- Write a sanitized escalation summary.
- Stop web research if it cannot be safely scoped.

## Minimum JSON Input
```json
{
  "ticket_id": "TKT-1001",
  "created_at": "2026-09-08T12:00:00Z",
  "customer_message": "My order was expected yesterday, but tracking has not updated.",
  "order_reference": "DEMO-ORDER-1001"
}
```

## Expected Output Set
```text
output/<ticket_id>/
├── interaction_summary.json
├── customer_response.md
├── troubleshooting_article.md
├── sources.json
└── audit_log.json
```

## Use-Case Traceability
| Use case | Mission capability | Human review condition |
|---|---|---|
| UC-01 | Delivery research and troubleshooting | Missing evidence or account action |
| UC-02 | Return/refund guidance | Approval, status, exception, adjustment |
| UC-03 | Account/checkout guidance | Compromise, secrets, account action |
| UC-04 | Evidence-first behavior | Conflicting or insufficient evidence |
| UC-05 | Transparent scope boundary | Unsupported or uncertain domain |

# Phase 2 Requirements - Annotated Updates

> **Revision note:** These updates were added after reviewing Phase 2 against the approved SupportScout mission, roadmap, technology stack, and Phase 1 baseline.

## UPDATE-P2-REQ-01: Research Scope Boundary

**Location:** Insert under `### Common Assumptions`.

```markdown
### Revision: Research Scope Boundary

SupportScout researches only general guidance from permitted public sources.

The system SHALL NOT:

- query private customer systems;
- inspect a customer's order, account, payment, or refund record;
- verify customer-specific refund or delivery status;
- retrieve internal business records; or
- place customer-provided identifiers into public search queries.

Customer-provided references may be retained as contextual input when safe, but they SHALL NOT be treated as authoritative evidence of account, order, payment, refund, or delivery status.
```

**Reason for update:** This prevents future search and agent implementations from drifting into unsupported customer-specific investigation.

---

## UPDATE-P2-REQ-02: Policy Exception Clarification

**Location:** Add to `UC-02: Return or Refund Inquiry`, under `#### Alternate Flows`.

```markdown
- Customer requests an exception to a stated or researched return/refund policy: mandatory human review and escalation.
```

**Location:** Add to the same use case under `#### Acceptance Criteria`.

```markdown
- Policy exceptions are never approved automatically.
```

**Reason for update:** Policy exceptions are a mission-defined human-review condition and should be explicit at the use-case layer.

---

## UPDATE-P2-REQ-03: Low-Confidence Classification Use Case

**Location:** Insert after `### UC-05: Unsupported Issue`.

```markdown
### UC-06: Low-Confidence Classification

**Trigger:** The classification process cannot confidently determine whether the ticket belongs to one of the supported domains.

#### Required Behavior

- Do not force the ticket into a supported domain.
- Mark the classification as uncertain.
- Generate a sanitized escalation summary.
- Record `low_confidence` as the escalation reason.
- Stop normal automated processing unless a later authorized human review approves a classification.

#### Acceptance Criteria

- Unsupported certainty is never presented as fact.
- Low-confidence cases require human review.
- The escalation summary explains the uncertainty without exposing hidden model reasoning.
- No web research occurs when the issue cannot be safely scoped.
```

**Reason for update:** Later classification phases use confidence thresholds, so Phase 2 must define the expected business behavior.

---

## UPDATE-P2-REQ-04: Escalation Output Rule

**Location:** Insert under `### Expected Output Set`.

```markdown
### Revision: Escalation Output Rule

An escalated workflow SHALL produce only the artifacts that can be generated safely and truthfully.

Expected escalation artifacts are:

```text
output/<ticket_id>/
├── interaction_summary.json
├── customer_response.md
├── troubleshooting_article.md
├── sources.json
└── audit_log.json
```

For escalation cases:

- `interaction_summary.json` SHALL record the escalation status and reason.
- `customer_response.md` SHALL contain only escalation-safe language and SHALL NOT claim that a restricted action was completed.
- `troubleshooting_article.md` SHALL contain a limited-information notice when reliable guidance is unavailable.
- `sources.json` SHALL contain only sanitized source metadata actually collected.
- `audit_log.json` SHALL contain sanitized workflow events.

If a safety condition prohibits normal customer-facing guidance, the response and article SHALL be limited accordingly rather than omitted or fabricated.
```

**Reason for update:** The original output set did not distinguish normal completion from escalation behavior.

---

## UPDATE-P2-REQ-05: Revised Use-Case Traceability Row

**Location:** Add to `### Use-Case Traceability`.

```markdown
| UC-06 | Confidence-aware scope control | Low-confidence or indeterminate classification |
```

**Reason for update:** The traceability matrix must include the newly added use case.

---

## UPDATE-P2-REQ-06: Optional Use-Case Summary Matrix

**Location:** Insert after the traceability table.

```markdown
### Use-Case Summary Matrix

| Use Case | Domain or Condition | Escalation Possible | Escalation Required |
|---|---|---:|---:|
| UC-01 | `order_tracking_delivery` | Yes | When account action or reliable evidence is unavailable |
| UC-02 | `returns_refunds` | Yes | For approval, status verification, exception, or adjustment |
| UC-03 | `account_checkout` | Yes | For compromise, sensitive data, authorization, or account action |
| UC-04 | Evidence failure | Yes | Always |
| UC-05 | Unsupported domain | Yes | Always |
| UC-06 | Uncertain classification | Yes | Always |
```

**Reason for update:** This provides a concise classification and escalation reference for later requirements, contracts, and tests.

