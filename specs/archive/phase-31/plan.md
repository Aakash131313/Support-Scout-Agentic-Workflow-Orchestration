# Phase 31: Live Integration Validation

## Objective

Validate SupportScout against live external services instead of mocked dependencies.

This phase transitions the system from offline deterministic testing into a real-world research workflow using:

- Udacity Vocareum OpenAI-compatible endpoint
- GPT-4o-mini
- Tavily Search API
- Public website scraping

The goal is to demonstrate that the complete agent architecture works with live services while preserving all deterministic safety controls.

---

## Scope

### In Scope

- Live model inference
- Live Tavily research
- Live website scraping
- Evidence preparation
- Support draft generation
- QA validation
- Troubleshooting article generation
- Standardized output artifacts

### Out of Scope

- Multi-turn conversations
- Customer account access
- Real order data
- Refund authorization
- Payment processing
- Production deployment

---

## Deliverables

### Infrastructure

- live.py
- OpenAI-compatible Udacity transport
- Tavily integration
- Environment-based configuration

### Documentation

- Live setup instructions
- Environment variable documentation
- Validation results

### Validation

- Live delayed-delivery workflow
- Restricted-action escalation workflow
- Manual output review

---

## Success Criteria

### Functional

- SupportScout completes a ticket using live services
- Tavily returns search results
- Pages are scraped successfully
- Evidence is created
- Support responses are generated
- Articles are generated
- Output files are written

### Quality

- Evidence citations are retained
- No secrets appear in outputs
- No customer-specific claims are generated
- No restricted actions are approved

### Safety

- Refund authorization requests escalate
- Account compromise requests escalate
- Sensitive-data requests escalate
- Policy exception requests escalate

---

## Risks

### Model Schema Drift

Mitigation:

- Explicit JSON schemas in prompts
- Pydantic validation
- Deterministic escalation

### Search Result Quality

Mitigation:

- QA validation layer
- Evidence sufficiency checks
- Conflict detection

### Provider Availability

Mitigation:

- Escalation pathway
- Retry logic
- Transport exception handling