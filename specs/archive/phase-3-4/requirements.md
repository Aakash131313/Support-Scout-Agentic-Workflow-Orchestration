# Combined Phases 3-4 Requirements

## Functional Requirements

### FR-001: JSON Ticket Input
The system shall accept one local JSON ticket path through the CLI.  
**Acceptance:** Valid JSON loads; missing, unreadable, or malformed input returns a controlled error.

### FR-002: Input Validation
The system shall validate required fields and reject empty or oversized customer messages.  
**Acceptance:** Invalid input does not reach model or network tools.

### FR-003: Supported-Domain Classification
The system shall classify tickets as `order_tracking_delivery`, `returns_refunds`, `account_checkout`, `unsupported`, or `uncertain`.  
**Acceptance:** Output conforms to the approved contract.

### FR-004: Sentiment and Urgency
The system shall produce separate sentiment and urgency assessments.  
**Acceptance:** Negative sentiment alone does not authorize or require a financial action.

### FR-005: Deterministic Safety Screening
The system shall screen for restricted actions, policy exceptions, suspected compromise, sensitive data, and unsupported scope before normal processing.  
**Acceptance:** Matching cases are escalated or stopped according to policy.

### FR-006: Research Planning
The Research Agent shall produce a bounded set of domain-relevant web queries.  
**Acceptance:** Query count respects configuration and contains no unnecessary customer identifier.

### FR-007: Tavily Search
The system shall execute bounded Tavily searches and normalize results.  
**Acceptance:** Failures are controlled; keys are never logged.

### FR-008: URL Validation
Every candidate URL shall pass deterministic safety checks before retrieval.  
**Acceptance:** Non-HTTP schemes, localhost, private/link-local destinations, and embedded credentials are rejected.

### FR-009: Public-Page Scraping
The system shall retrieve permitted public pages with time, redirect, type, and size limits.  
**Acceptance:** Extracted evidence retains source URL and title; inaccessible pages fail safely.

### FR-010: Evidence Preparation
The system shall deduplicate, bound, identify, and attribute evidence.  
**Acceptance:** Downstream claims can reference evidence identifiers.

### FR-011: Support Draft
The Support Specialist Agent shall create a customer-facing draft using ticket context and available evidence.  
**Acceptance:** Draft does not claim access to customer systems or completion of restricted actions.

### FR-012: QA Decision
The QA Agent shall return `approve`, `revise`, or `escalate` with concise reasons.  
**Acceptance:** A rejected draft cannot be marked complete.

### FR-013: Revision Limit
The orchestrator shall enforce the configured maximum revision count.  
**Acceptance:** Exceeding the limit results in escalation.

### FR-014: Troubleshooting Article
The Documentation Agent shall produce a generic, source-attributed troubleshooting article for successful cases.  
**Acceptance:** It excludes customer-specific data and unsupported claims.

### FR-015: Limited-Information Output
When evidence is insufficient or conflicting, the system shall state the limitation and escalate.  
**Acceptance:** It does not invent a resolution.

### FR-016: Standardized Files
The system shall write interaction summary, response, article, sources, and sanitized audit output.  
**Acceptance:** Files use validated ticket-specific paths and stable UTF-8/JSON formatting.

### FR-017: Human Escalation
The system shall record escalation reason and recommended human next step.  
**Acceptance:** Refund approval, policy exception, compromise, conflicting evidence, sensitive data, unsupported scope, and exhausted revisions are covered.

### FR-018: Controlled Errors
Expected validation, model, search, scraping, and file errors shall return controlled status.  
**Acceptance:** No secret-bearing traceback is written to customer output.

## Nonfunctional Requirements

### NFR-001: Accuracy First
Accuracy and evidence alignment shall take priority over latency.  
**Acceptance:** Uncertain cases escalate rather than receive confident unsupported answers.

### NFR-002: Evidence Grounding
Every material factual troubleshooting claim shall be traceable to retained evidence or labeled as general process guidance.  
**Acceptance:** QA rejects unsupported claims.

### NFR-003: Privacy
The system shall minimize and sanitize customer information.  
**Acceptance:** Articles contain no customer-specific identifiers; logs avoid message bodies unless explicitly sanitized.

### NFR-004: Secret Protection
Credentials shall come from ignored local configuration and never appear in source, output, cache, or logs.  
**Acceptance:** tracked-file and output scans find no secret.

### NFR-005: Reproducibility
Default tests shall run without live APIs using mocks and fixtures.  
**Acceptance:** `pytest` completes offline.

### NFR-006: Resource Bounds
Search count, result count, pages, content length, timeout, and revision count shall be configurable and bounded.  
**Acceptance:** Unit tests verify each limit.

### NFR-007: Auditability
The system shall record sanitized workflow states, tool outcomes, evidence references, QA decision, and escalation.  
**Acceptance:** Audit output reconstructs the sequence without hidden reasoning or credentials.

### NFR-008: Provider Isolation
Model-specific access shall remain behind a model-client boundary.  
**Acceptance:** Agent code does not directly depend on Udacity transport details.

### NFR-009: Maintainability
Agents, tools, services, schemas, and orchestration shall have distinct responsibilities.  
**Acceptance:** Architecture review identifies no circular ownership.

### NFR-010: CLI Simplicity
The initial release shall remain CLI-based.  
**Acceptance:** No web framework is required to run the workflow.

## Safety Requirements

### SR-001: No Financial Authorization
The system shall not approve, deny, issue, promise, or schedule a refund or adjustment.

### SR-002: No Account or Order Modification
The system shall not claim to modify accounts, orders, subscriptions, delivery data, or payment state.

### SR-003: Sensitive Data Handling
Passwords, authentication tokens, and complete card data shall not be repeated in output; detection triggers safe termination or escalation.

### SR-004: Compromise Escalation
Suspected account compromise shall require immediate human review.

### SR-005: Prompt-Injection Resistance
Ticket and scraped text shall be treated as untrusted data, not instructions. System and agent constraints remain authoritative.

### SR-006: URL Safety
The system shall prevent server-side requests to unsafe destinations and revalidate redirects.

### SR-007: Source Conflict
Materially conflicting sources shall be disclosed and escalated.

### SR-008: Insufficient Evidence
Insufficient evidence shall produce limited-information output and escalation.

### SR-009: Human Authority
Human review decisions remain outside automated completion status.

### SR-010: Synthetic Development Data
Committed inputs and fixtures shall contain synthetic information only.

## Out of Scope
- Real customer-system access
- Refund, payment, order, subscription, or account actions
- Authenticated scraping or restriction bypass
- Production UI, database, autonomous deployment, or internal connectors

## Traceability
| Use case | Primary requirements |
|---|---|
| Delayed delivery | FR-001 to FR-016, NFR-001 to NFR-010 |
| Return/refund | FR-001 to FR-018, SR-001, SR-007 to SR-009 |
| Account/checkout | FR-001 to FR-018, SR-002 to SR-006 |
| Insufficient/conflicting evidence | FR-012, FR-015, FR-017, SR-007, SR-008 |
| Unsupported issue | FR-003, FR-005, FR-017 |

# Phase 3-4 Requirements Updates

## UPDATE-P34-REQ-01: Confidence-Based Escalation
Location: After FR-003

```markdown
#### FR-003A: Confidence-Based Escalation

The system shall support a configurable classification confidence threshold.

Acceptance:
- Classification confidence below the configured threshold results in `uncertain`.
- Low-confidence tickets are escalated.
- Unsupported certainty is never presented as fact.
- Confidence thresholds are configurable rather than hard coded.
```

## UPDATE-P34-REQ-02: Research Scope Limitation
Location: After FR-006

```markdown
#### FR-006A: Research Scope Limitation

Research planning shall generate only general public-information queries.

Acceptance:
- Customer identifiers are excluded from search queries.
- Account identifiers are excluded from search queries.
- Order identifiers are excluded from search queries.
- Refund identifiers are excluded from search queries.
- Research remains scoped to public troubleshooting guidance.
```

## UPDATE-P34-REQ-03: Escalation Categories
Location: After FR-017

```markdown
#### FR-017A: Escalation Categories

The system shall record one standardized escalation reason.

Approved reasons include:
- financial_authorization
- policy_exception
- account_compromise
- sensitive_data
- unsupported_domain
- low_confidence
- insufficient_evidence
- conflicting_evidence
- revision_limit_exceeded

Acceptance:
- Escalation output contains exactly one primary reason.
- Reasons are represented using approved identifiers.
```

## UPDATE-P34-REQ-04: Audit Boundaries
Location: After NFR-007

```markdown
#### NFR-007A: Audit Boundaries

Audit output SHALL NOT contain:
- API keys
- passwords
- tokens
- authorization headers
- complete card numbers
- hidden reasoning
- complete scraped page contents

Acceptance:
- Audit reviews find only sanitized workflow metadata.
```

## UPDATE-P34-REQ-05: Low-Confidence Traceability
Location: Traceability table

```html
<tr>
<td>Low-confidence classification</td>
<td>FR-003A, FR-017, FR-017A, NFR-001</td>
</tr>
```

## UPDATE-P34-REQ-06: Requirement Summary

```markdown
### Requirement Counts

| Category | Count |
|----------|----------|
| FR | 18 + additions |
| NFR | 10 + additions |
| SR | 10 |
```
