# Phase 27 Requirements

## Case Schema

Each case shall include case ID, synthetic ticket, expected domain, acceptable urgency band, expected escalation and reason, required evidence characteristics, prohibited claims, expected terminal state, and tags such as domain, safety, ambiguity, or adversarial.

## Dataset Composition

The set shall include every supported domain; routine and negative-sentiment cases; neutral but security-critical cases; refund/policy escalation; unsupported scope; low confidence; insufficient/conflicting evidence; prompt injection; and QA unsupported-claim cases. Composition counts shall be reported rather than implied.

## Metrics

- **Domain accuracy:** correct domain cases / eligible domain cases.
- **Escalation accuracy:** correct required/not-required decision / all cases.
- **Escalation reason accuracy:** correct reason / cases requiring escalation.
- **Grounding compliance:** cases with no unsupported material claim / cases producing content.
- **QA protection rate:** unsupported drafts rejected / injected unsupported-draft cases.
- **Evidence relevance:** documented reviewer rubric or deterministic fixture expectation.

## Execution Modes

A deterministic baseline shall use frozen mocked model/search/scrape responses. Any live model run shall be labeled exploratory, record non-secret model identifier and run date, and remain separate from the reproducible baseline.

## Reporting

Reports shall provide formula, numerator, denominator, exclusions, failed-case IDs, and limitations. They shall not call curated results production accuracy, generalize beyond the dataset, hide failures, or invent a target after results are known.

## Privacy and Security

All cases shall be synthetic. Results shall not contain credentials, real customer data, hidden reasoning, or full sensitive fixture values.

## Acceptance Criteria

The same deterministic configuration produces the same measured results; all cases have expected labels; metrics can be independently recomputed; and limitations accurately state the evaluation boundaries.
