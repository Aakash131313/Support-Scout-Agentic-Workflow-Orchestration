# Phases 20-22 Plan: Content Generation Layer

## Purpose

Implement the evidence-grounded content pipeline comprising the Support Specialist Agent, QA Agent, and Documentation Agent. This bundle converts approved evidence into a customer response, validates that response, and generates a generic troubleshooting article and final narrative artifacts.

## Authoritative Inputs

- `mission.md`: accuracy before speed, evidence before confidence, human authority, privacy.
- `tech_stack.md`: custom orchestrator, Udacity model client, Pydantic contracts, Markdown/JSON output.
- `roadmap.md`: Phases 20, 21, and 22.
- Phase 3-4 functional and safety requirements.
- Phase 5-7 agent and contract definitions.
- Phase 8 testing strategy.
- Phase 15-19 attributed evidence pipeline.

## Pipeline

```text
Sanitized Ticket + Classification + Evidence
    -> Support Specialist Agent
    -> SupportDraft
    -> QA Agent
    -> approve | revise | escalate
    -> Documentation Agent
    -> TroubleshootingArticle + summary content
```

## Implementation Sequence

1. Implement shared prompt-loading and sanitized context helpers.
2. Implement Support Specialist Agent and deterministic post-generation checks.
3. Implement QA Agent with approve, revise, and escalate outcomes.
4. Implement one bounded revision handoff.
5. Implement Documentation Agent using approved content only.
6. Add limited-information documentation for escalation cases.
7. Add mocked unit and adversarial tests.
8. Complete validation before orchestration integration.

## Shared Design Rules

- Ticket and evidence text are untrusted data.
- Every material factual step must map to a supplied evidence ID.
- Agents cannot approve financial actions or modify accounts/orders.
- QA failure prevents normal completion.
- Documentation excludes customer-specific identifiers.
- Prompts request concise structured output, not hidden reasoning.
- Default tests use mocked model responses.

## Deliverables

- `agents/support_agent.py`
- `agents/qa_agent.py`
- `agents/documentation_agent.py`
- Three prompt files
- Shared content-validation helpers
- Unit/adversarial fixtures and tests
- Completed `phase-20-22-validation.md`

## Exit Criteria

- Supported-domain fixtures produce valid drafts.
- QA catches unsupported claims, privacy violations, and prohibited actions.
- Revision is bounded and escalation remains available.
- Documentation is generic, attributed, and privacy-safe.
- Insufficient evidence produces limited-information output rather than invented guidance.
- Offline tests pass.

## Recommended Commit

`feat: implement SupportScout content generation and QA pipeline`
