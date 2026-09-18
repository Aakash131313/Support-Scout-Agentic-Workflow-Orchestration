# Combined Phases 5-7 Plan: Architecture, Agents, and Data Contracts

## Purpose
Define one coherent system design. The phases are combined because component boundaries, agent responsibilities, and handoff contracts must be designed together.

## Architecture Goals
- CLI-first, custom orchestration
- Deterministic controls around model behavior
- Provider-isolated Udacity model client
- Tavily search plus safe public-page scraping
- In-memory workflow state and validated file outputs
- Human escalation as an explicit terminal state
- Mockable dependencies and offline default tests

## Work Items
1. Define components and ownership.
2. Define the end-to-end workflow and failure paths.
3. Define each agent's input, output, authority, and limitations.
4. Define tools and services separately from agents.
5. Define Pydantic-ready data contracts.
6. Define output and audit contracts.
7. Define retry, revision, and escalation transitions.
8. Create Mermaid and PNG architecture diagrams.
9. Validate every handoff against a contract.

## Deliverables
- `specs/architecture.md`
- `specs/data-contracts.md`
- Agent sections and initial prompt files
- `diagrams/architecture.mmd`
- `diagrams/architecture.png`
- Completed `phase-5-7-validation.md`

## Exit Criteria
- Every component has one primary responsibility.
- Every agent handoff uses a named contract.
- Restricted actions cannot be completed by an agent.
- Failure and escalation paths are explicit.
- Sensitive data is excluded or sanitized.
- Architecture supports mocked testing.

## Recommended Commit
`docs: define SupportScout architecture agents and data contracts`

# Phase 5-7 Plan Updates

## UPDATE-P57-PLAN-01: Confidence Threshold Ownership Work Item

Location: Add to Work Items

```markdown
- Define ownership and validation rules for confidence thresholds and low-confidence escalation behavior.
```

Reason: Phase 3-4 introduced confidence-based escalation and architecture should explicitly allocate responsibility.
