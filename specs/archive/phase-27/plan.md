# Phase 27 Plan: Accuracy Evaluation

## Purpose

Measure the mission’s primary success metric with a curated, reproducible synthetic evaluation set. This phase reports observed performance only and does not claim production accuracy.

## Evaluation Scope

Measure domain classification correctness, escalation correctness, evidence relevance review, grounding compliance, and QA rejection of unsupported claims. Include all supported domains plus safety-critical and ambiguous cases.

## Implementation Sequence

1. Define evaluation case schema.
2. Create balanced synthetic cases with expected labels and prohibited claims.
3. Freeze model/search fixtures for deterministic baseline evaluation, or clearly separate live exploratory runs.
4. Implement evaluation runner.
5. Calculate metrics with numerator and denominator.
6. Record failed cases and error categories.
7. Write results and limitations.
8. Complete validation.

## Deliverables

- `evaluation/evaluation_cases.json`
- `evaluation/README.md`
- Evaluation runner or Pytest module
- Machine-readable and Markdown results
- Completed validation

## Exit Criteria

- Dataset and labels validate.
- Metrics are reproducible.
- Every result includes numerator, denominator, and run configuration.
- Failed examples remain visible.
- Results are clearly described as curated evaluation, not production performance.

## Recommended Commit

`test: add reproducible SupportScout accuracy evaluation`
