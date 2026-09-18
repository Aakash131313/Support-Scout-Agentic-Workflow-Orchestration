# SupportScout Curated Evaluation Results

This is a curated deterministic baseline, not production performance.

- Dataset version: 2.0
- Evaluation date: 2026-09-18
- Cases evaluated: 18
- Failed cases: 0

## Metrics

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Domain Accuracy | 18 | 18 | 1.000 |
| Urgency Accuracy | 18 | 18 | 1.000 |
| Escalation Accuracy | 18 | 18 | 1.000 |
| Escalation Reason Accuracy | 11 | 11 | 1.000 |
| Terminal State Accuracy | 18 | 18 | 1.000 |
| Qa Protection Rate | 1 | 1 | 1.000 |

## Failed case identifiers

None

## Limitations

- Synthetic curated cases only; this is not production traffic.
- Measures the deterministic safety and validation layer, not model quality.
- Frozen fixtures mean these numbers cannot be read as live accuracy.
- Conflict detection is a conservative heuristic and will miss subtle disagreement.
