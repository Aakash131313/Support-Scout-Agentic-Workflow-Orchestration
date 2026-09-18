# Phase 2 Plan: Define Use Cases

## Purpose
Define testable e-commerce support scenarios that drive requirements, architecture, contracts, and tests.

## Source of Truth
This phase follows `mission.md`, `roadmap.md`, and `tech_stack.md`. SupportScout handles JSON tickets in three domains: order tracking and delivery, returns and refunds, and account and checkout issues. Accuracy and evidence grounding take priority, and restricted actions require human review.

## Scope
### In scope
- Three primary happy-path use cases
- Cross-domain escalation scenarios
- Synthetic JSON examples
- Expected outputs and measurable acceptance criteria
- Boundaries between automated guidance and human authority

### Out of scope
- Code, schemas, agents, prompts, APIs, and live integrations
- Real customer or payment data
- Refund approval, account modification, or order modification

## Work Items
1. Define actors and assumptions.
2. Write one primary use case per supported domain.
3. Define alternate and failure flows.
4. Create one human-escalation case per domain.
5. Create synthetic JSON examples.
6. Map each use case to mission capabilities.
7. Review for testability, privacy, and scope.

## Actors
- Customer
- Support specialist
- Senior support specialist or authorized reviewer
- SupportScout
- External public information source

## Deliverables
- `specs/use-cases.md`
- `sample_inputs/delayed_order.json`
- `sample_inputs/return_refund.json`
- `sample_inputs/checkout_issue.json`
- `sample_inputs/escalation_refund.json`
- Completed `phase-2-validation.md`

## Exit Criteria
- Every support domain has a complete happy path.
- Every use case includes preconditions, trigger, flow, alternatives, outputs, and acceptance criteria.
- At least one scenario requires human escalation.
- Examples contain synthetic data only.
- No use case authorizes a restricted action.
- Expected behavior is precise enough to become a test.

## Recommended Commit
`docs: define SupportScout use cases and sample ticket scenarios`

# Phase 2 Plan - Annotated Updates

> **Revision note:** These updates were added after reviewing Phase 2 against the approved SupportScout mission, roadmap, technology stack, and Phase 1 baseline.

## UPDATE-P2-PLAN-01: Explicit Research Boundary

**Location:** Insert after `### Source of Truth`.

```markdown
### Revision: Public Research Boundary

SupportScout researches only general information available from permitted public sources.

The Phase 2 use cases SHALL NOT imply that SupportScout can:

- query private customer systems;
- inspect a customer's order, account, payment, or refund record;
- verify a customer-specific delivery or refund status;
- retrieve internal business records; or
- treat a customer-provided reference as authoritative evidence.

Customer-provided order or account references may be retained as contextual input only when safe, but they SHALL NOT be included in public web-search queries.
```

**Reason for update:** The original use cases mention public research but did not explicitly distinguish general research from customer-specific investigation.

---

## UPDATE-P2-PLAN-02: Low-Confidence Use-Case Work Item

**Location:** Add to `### Work Items`.

```markdown
- Define an explicit low-confidence classification scenario that escalates instead of forcing a supported-domain classification.
```

**Reason for update:** Later triage and classification phases require a documented business outcome for uncertain classification.

---

## UPDATE-P2-PLAN-03: Expanded Deliverables

**Location:** Add to `### Deliverables`.

```markdown
- `sample_inputs/low_confidence_issue.json`
- Expected classification and escalation metadata for every sample input
```

**Reason for update:** The new low-confidence use case needs a corresponding synthetic fixture and expected outcome.

---

## UPDATE-P2-PLAN-04: Expanded Exit Criteria

**Location:** Add to `### Exit Criteria`.

```markdown
- Low-confidence classification is documented as an escalation path.
- Normal and escalated workflows have distinct expected output behavior.
- Public research is explicitly separated from customer-specific record lookup.
```

**Reason for update:** These criteria make the Phase 2 output testable and prevent scope drift in later implementation phases.
