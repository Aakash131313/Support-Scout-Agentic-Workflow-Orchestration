# Phases 25-26 Requirements

## Fixture Requirements

Fixtures shall include synthetic tickets, Tavily responses, HTML pages, model responses, expected outputs, unsafe URL cases, and error objects. Every fixture shall have a documented purpose. Secrets, real order identifiers, and real customer data are prohibited.

## Happy-Path Integration Tests

**IT-001 Delayed delivery:** complete with grounded response and article.

**IT-002 General return guidance:** complete without refund authorization.

**IT-003 Checkout troubleshooting:** complete without requesting secrets.

Each test shall validate terminal state, classification, evidence attribution, QA approval, output files, and sanitized audit log.

## Escalation and Failure Integration Tests

Implement refund authorization, suspected compromise, unsupported domain, insufficient evidence, conflicting evidence, QA revision, revision exhaustion, partial scrape failure, total dependency failure, and file-writing failure. Each test shall assert terminal truthfulness and absence of prohibited completion claims.

## Adversarial Tests

Implement every Phase 8 scenario: invalid JSON, missing fields, ticket prompt injection, webpage prompt injection, localhost/private URL, unsafe redirect, oversized page, search timeout, scrape timeout, invalid model JSON, conflicting sources, insufficient evidence, refund approval, sensitive data, path traversal, unsupported domain, negative routine sentiment, neutral compromise report, QA unsupported-claim rejection, and revision exhaustion.

## Assertion Requirements

Tests shall assert contracts, terminal states, evidence IDs, outputs, audit categories, call counts, and forbidden behavior. Exact prose comparisons should be avoided except for deterministic templates. Tests shall verify that invalid input prevents downstream calls and terminal states prevent further calls.

## Isolation Requirements

The default test run shall make no network or model call. Live tests, if retained, shall use an explicit marker and be excluded by default. Temporary directories shall isolate file effects, and monkeypatch/mocks shall isolate environment variables.

## Traceability

Each critical FR, NFR, and SR shall map to at least one executable test. Test names or metadata should include relevant requirement IDs where practical. A missing critical mapping blocks completion of this bundle.

## Acceptance Criteria

`pytest` passes offline; all mandatory adversarial tests execute; no fixture contains sensitive data; expected terminal behaviors match the approved requirements; and the traceability matrix has no uncovered critical requirement.
