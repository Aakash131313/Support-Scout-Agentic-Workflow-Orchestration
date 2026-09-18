# Phase 2 Validation: Use Cases

## Status
- **Decision:** NOT RUN
- **Allowed results:** PASS, FAIL, BLOCKED, NOT RUN

## Review Checklist
| Check | Status | Evidence or correction |
|---|---|---|
| Three supported domains have primary use cases | NOT RUN | |
| Each use case has actor, trigger, preconditions, flow, alternatives, and acceptance criteria | NOT RUN | |
| At least one human-escalation scenario is defined | NOT RUN | |
| Refund approval always escalates | NOT RUN | |
| Suspected account compromise always escalates | NOT RUN | |
| Insufficient or conflicting evidence never produces invented guidance | NOT RUN | |
| Unsupported issues are not forced into a domain | NOT RUN | |
| All examples are synthetic JSON | NOT RUN | |
| Expected output files are specified | NOT RUN | |
| Use cases are testable without a live customer system | NOT RUN | |

## Sample Input Validation
Validate each file against these rules:
- Valid JSON
- Unique synthetic ticket ID
- Nonempty customer message
- No API key, token, password, real order number, or card data
- Expected category and escalation decision documented beside the fixture

| Fixture | JSON valid | Synthetic | Expected category recorded | Expected escalation recorded |
|---|---:|---:|---:|---:|
| `delayed_order.json` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `return_refund.json` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `checkout_issue.json` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `escalation_refund.json` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

## Mission Alignment
| Mission principle | Validation question | Status |
|---|---|---|
| Accuracy before speed | Are expected outcomes explicit and testable? | NOT RUN |
| Evidence before confidence | Does each research flow require source grounding? | NOT RUN |
| Human authority | Are restricted actions escalated? | NOT RUN |
| Privacy | Are secrets excluded from examples and expected outputs? | NOT RUN |
| Transparent limitations | Are uncertainty and insufficient evidence handled explicitly? | NOT RUN |

## Final Decision
- [ ] GO
- [ ] CONDITIONAL GO
- [ ] NO-GO

**Rationale:** Not yet recorded.

Proceed to combined Phases 3-4 only when all mandatory checks pass.


# Phase 2 Validation - Annotated Updates

> **Revision note:** These updates were added after reviewing Phase 2 against the approved SupportScout mission, roadmap, technology stack, and Phase 1 baseline.

## UPDATE-P2-VAL-01: Low-Confidence Review Check

**Location:** Add to `### Review Checklist`.

```markdown
| Low-confidence scenarios escalate instead of forcing a classification | NOT RUN | |
```

**Reason for update:** The new UC-06 requires an explicit validation check.

---

## UPDATE-P2-VAL-02: Public Research Boundary Check

**Location:** Add to `### Review Checklist`.

```markdown
| Use cases limit research to general public guidance and prohibit customer-specific record lookup | NOT RUN | |
```

**Reason for update:** This validates alignment with the mission and prevents implementation drift.

---

## UPDATE-P2-VAL-03: Policy Exception Check

**Location:** Add to `### Review Checklist`.

```markdown
| Policy-exception requests require human review and are never approved automatically | NOT RUN | |
```

**Reason for update:** Policy exceptions are a mission-defined escalation condition.

---

## UPDATE-P2-VAL-04: Escalation Artifact Check

**Location:** Add to `### Review Checklist`.

```markdown
| Escalated workflows define truthful, limited, and sanitized output behavior | NOT RUN | |
```

**Reason for update:** The validation should distinguish normal completion artifacts from escalation-safe outputs.

---

## UPDATE-P2-VAL-05: Low-Confidence Sample Input

**Location:** Add to `### Sample Input Validation`.

```markdown
| `low_confidence_issue.json` | NOT RUN | NOT RUN | `uncertain` | `low_confidence` |
```

**Reason for update:** UC-06 requires a synthetic fixture with an expected domain and escalation reason.

---

## UPDATE-P2-VAL-06: Expected Outcome Validation

**Location:** Add immediately below the sample-input validation table.

```markdown
### Revision: Expected Outcome Validation

For every sample fixture, confirm that the following expected values are documented:

- supported domain, `unsupported`, or `uncertain`;
- expected sentiment class when relevant;
- acceptable urgency band;
- whether escalation is required;
- expected escalation reason;
- whether web research is allowed;
- expected terminal behavior; and
- expected output artifact behavior.

**Status:** NOT RUN
```

**Reason for update:** Recording expected outcomes now makes the Phase 2 fixtures directly reusable in later integration and evaluation phases.

---

## UPDATE-P2-VAL-07: Final Decision Formatting

**Location:** Replace the current unselected decision list under `### Final Decision`.

```markdown
- [ ] **GO:** All mandatory Phase 2 checks pass.
- [ ] **CONDITIONAL GO:** Only noncritical issues remain and are documented.
- [ ] **NO-GO:** A use case is incomplete, unsafe, untestable, or inconsistent with the mission.

**Rationale:** Not yet recorded.
```

**Reason for update:** Checkboxes make it clear that exactly one decision must be selected after validation.
