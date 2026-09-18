# Phase 8 Requirements: Test Strategy

## Test Directory
```text
tests/
├── unit/
├── integration/
├── adversarial/
└── fixtures/
evaluation/
├── evaluation_cases.json
└── README.md
```

## General Test Requirements

### TR-001: Offline Default
`pytest` shall execute without live Tavily, model, or website calls.

### TR-002: Synthetic Fixtures
All committed tickets, HTML, search responses, model responses, and outputs shall be synthetic and secret-free.

### TR-003: Clear Assertions
Tests shall assert behavior and output contracts, not merely execution without exceptions.

### TR-004: Deterministic Results
Mocks and fixtures shall produce reproducible outcomes.

### TR-005: Live-Test Isolation
Optional live checks shall be explicitly marked and excluded by default.

## Unit-Test Requirements

### Schemas
- Accept valid contract examples.
- Reject missing required fields, invalid enums, unsafe ticket IDs, excessive lengths, and malformed URLs.

### Routing Service
- Escalate refund authorization, policy exceptions, compromise, secrets, unsupported domain, low confidence, evidence conflict, insufficient evidence, and QA exhaustion.
- Confirm negative sentiment alone does not authorize or necessarily escalate.

### URL Policy
- Allow valid public HTTP(S) URL fixtures.
- Reject file, data, FTP, localhost, loopback, private, link-local, embedded-credential, and unsafe redirect targets.

### Search Tool
- Normalize Tavily fixture responses.
- Deduplicate URLs.
- Respect result limits.
- Sanitize authentication, timeout, and malformed-response failures.

### Web Scraper
- Extract relevant text from fixture HTML.
- Remove script, style, and navigation noise.
- Reject unsupported content type, oversized content, excessive redirects, and timeout.

### Evidence Service
- Assign stable evidence IDs.
- Deduplicate content.
- Preserve attribution.
- Detect empty and insufficient evidence.

### File Writer
- Write valid UTF-8 and stable JSON.
- Sanitize ticket IDs.
- Reject directory traversal.
- Avoid secret-bearing log material.

### Model Client
- Parse valid structured fixture output.
- Reject or safely handle malformed output, timeout, transport error, and exhausted retry.

### Agents
Each agent test shall use a mocked model client and validate its approved input/output contract and prohibited behavior.

## Integration-Test Requirements

### IT-001: Delayed Delivery Happy Path
Expected: completed workflow, supported domain, evidence, approved response, article, and all output files.

### IT-002: General Return Guidance
Expected: sourced process guidance without refund authorization.

### IT-003: Checkout Troubleshooting
Expected: safe general steps, no request for secrets, approved output.

### IT-004: Refund Approval Escalation
Expected: early or post-triage escalation, no claim of approval, sanitized escalation output.

### IT-005: Insufficient Evidence
Expected: limited-information article and escalation.

### IT-006: QA Revision
Expected: one bounded revision followed by approval or escalation.

### IT-007: Dependency Failure
Expected: controlled failed or escalated terminal state and sanitized audit record.

## Required Adversarial Tests

| ID | Scenario | Expected result |
|---|---|---|
| AT-001 | Invalid JSON | Controlled input error; no network/model call |
| AT-002 | Missing required fields | Validation rejection |
| AT-003 | Ticket prompt injection | Treat as untrusted data; constraints remain active |
| AT-004 | Webpage prompt injection | Exclude instruction effect; use page only as evidence |
| AT-005 | Localhost/private URL | URL blocked before request |
| AT-006 | Unsafe redirect | Redirect blocked |
| AT-007 | Oversized page | Retrieval rejected safely |
| AT-008 | Search timeout | Controlled error; no secret exposure |
| AT-009 | Scrape timeout | Continue with remaining evidence or escalate |
| AT-010 | Invalid model JSON | Structured parse failure and bounded retry/escalation |
| AT-011 | Conflicting sources | Disclose conflict and escalate |
| AT-012 | Insufficient evidence | No invented resolution; escalate |
| AT-013 | Refund approval request | Human review required |
| AT-014 | Password/token/card data | Do not reproduce; terminate or escalate safely |
| AT-015 | Path traversal ticket ID | Reject or sanitize before writing |
| AT-016 | Unsupported domain | Escalate without forced classification |
| AT-017 | Negative but routine message | Tone adapts; no unauthorized action |
| AT-018 | Neutral account-compromise message | Urgency/escalation reflects risk, not sentiment |
| AT-019 | QA finds unsupported claim | Reject draft and revise or escalate |
| AT-020 | Revision limit reached | Escalate; never mark complete |

## Accuracy Evaluation

### Evaluation Dataset
Use curated synthetic cases. Each case shall define:
- expected domain,
- acceptable urgency band,
- expected escalation,
- required evidence characteristics,
- prohibited claims,
- expected terminal state.

### Measures
- Domain classification correctness
- Escalation correctness
- Evidence relevance review
- Grounding compliance
- QA rejection of unsupported claims

### Reporting Rules
- Report actual numerator, denominator, and evaluation date.
- Do not describe curated results as production performance.
- Preserve failed examples and corrective notes.
- Do not invent an accuracy target before baseline measurement.

## Traceability Matrix
| Requirement area | Minimum test coverage |
|---|---|
| FR-001 to FR-005 | Schema, routing, adversarial |
| FR-006 to FR-010 | Search, URL, scraper, evidence unit/integration |
| FR-011 to FR-015 | Agent, QA, escalation integration/adversarial |
| FR-016 to FR-018 | File, audit, failure integration |
| NFR-001 to NFR-010 | Evaluation, offline suite, limits, architecture review |
| SR-001 to SR-010 | Adversarial suite |

## Phase Pass Criteria
- Test plan covers every critical requirement.
- All adversarial scenarios have explicit expected outcomes.
- Default suite is offline and reproducible.
- Live checks are opt-in.
- Accuracy evaluation method is documented without unsupported claims.

# Phase 8 Requirements Updates

## UPDATE-P8-REQ-01: Low-Confidence Adversarial Test
Location: Add after AT-016

```markdown
### AT-016A
Scenario: Classification confidence below configured threshold
Expected Result: Ticket classified as uncertain or escalated with low_confidence reason; no forced classification.
```

## UPDATE-P8-REQ-02: Escalation Reason Coverage
Location: Integration-Test Requirements

```markdown
#### IT-008: Escalation Reason Validation

Expected: Escalated workflows contain a valid escalation reason from the approved enumeration and preserve it in output artifacts.
```

## UPDATE-P8-REQ-03: Audit Validation Coverage
Location: Unit-Test Requirements

```markdown
#### Audit Events
- Verify secrets are excluded from audit output.
- Verify hidden reasoning is never persisted.
- Verify escalation and workflow-state transitions are recorded correctly.
```

## UPDATE-P8-REQ-04: Traceability Expansion

```markdown
| FR-003A, FR-017A | Confidence and escalation validation |
| NFR-007A | Audit sanitization tests |
```
