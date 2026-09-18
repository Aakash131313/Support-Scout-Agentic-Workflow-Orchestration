# Phase 34: Implement Tool-Based Agent Diagnostics

## Objective

Enable SupportScout agents to retrieve operational information using structured tools and integrate operational evidence with public research evidence.

---

## Scope

### In Scope

- Support data client
- Domain tools
- Operational evidence
- Hybrid troubleshooting
- Tool-enabled workflows
- Diagnostic evaluations

### Out of Scope

- Refund authorization
- Order modification
- Account modification
- Payment processing

---

## Deliverables

### Tools

```text
src/support_scout/tools/
├── order_tools.py
├── shipment_tools.py
├── return_tools.py
├── account_tools.py
└── checkout_tools.py
```

### Operational Evidence

```python
OperationalEvidence
```

### Future Tool Compatibility

```python
@tool
```

compatible interfaces

### Diagnostic Scenarios

- Order delays
- Tracking failures
- Missing deliveries
- Return processing
- Checkout failures
- Login failures

---

## Success Criteria

### Functional

- Tools retrieve data successfully
- Evidence generated successfully
- Diagnostics include operational facts

### Quality

- Operational facts remain traceable
- Evidence IDs preserved
- Hybrid evidence supported

### Safety

- Restricted actions still escalate
- No approval actions introduced