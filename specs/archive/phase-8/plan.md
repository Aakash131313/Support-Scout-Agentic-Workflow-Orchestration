# Phase 8 Plan: Test Strategy

## Purpose
Define a test strategy that validates SupportScout requirements, architecture, contracts, safety controls, and accuracy objectives before implementation expands.

## Principles
- Default tests run offline.
- Model, Tavily, and HTTP dependencies are mocked by default.
- Fixtures are synthetic.
- Happy-path and adversarial behavior receive equal design attention.
- Coverage supports, but does not replace, meaningful assertions.
- Accuracy claims must come from reproducible measured cases.

## Test Levels
1. Schema and unit tests
2. Agent tests with mocked model output
3. Tool and service tests with mocked external dependencies
4. Orchestrator integration tests
5. Adversarial tests
6. Curated accuracy evaluation
7. Optional, separately marked live checks

## Work Items
1. Map critical requirements to tests.
2. Define fixtures for three supported domains.
3. Define mock response contracts.
4. Define happy-path integration scenarios.
5. Define required adversarial scenarios.
6. Define accuracy evaluation labels and metrics.
7. Define pass/fail and release-readiness criteria.

## Deliverables
- `specs/test-plan.md`
- Traceability matrix
- Fixture inventory
- Planned test directory structure
- Completed `phase-8-validation.md`

## Exit Criteria
- Every critical requirement maps to at least one test.
- All required adversarial cases have expected outcomes.
- Default tests require no live API.
- Accuracy evaluation is reproducible and makes no unmeasured claim.
- Test fixtures contain synthetic data only.

## Recommended Commit
`docs: define SupportScout test and evaluation strategy`

# Phase 8 Plan Updates

## UPDATE-P8-PLAN-01: Confidence Evaluation Coverage

Location: Add to Work Items

```markdown
- Define low-confidence classification evaluation scenarios and expected escalation behavior.
```

Reason: Confidence-driven escalation was introduced in earlier phases and should be explicitly covered by testing strategy.
