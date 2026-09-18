# Phase 33: Build Operational Troubleshooting Platform

## Objective

Transform SupportScout from a research-driven support assistant into an operational troubleshooting platform by integrating a synthetic support data system.

The platform will provide structured business context such as orders, shipments, returns, account diagnostics, and checkout diagnostics.

SupportScout will continue to use web search and scraping, but operational troubleshooting data will become a first-class evidence source.

---

## Scope

### In Scope

- FastAPI support platform
- SQLite database
- SQLModel models
- Synthetic support data
- Customer records
- Orders
- Shipments
- Returns
- Account diagnostics
- Checkout diagnostics
- Read-only APIs
- Support data client
- Operational evidence generation

### Out of Scope

- Real customer data
- Production databases
- Refund approvals
- Account modifications
- Order modifications
- Payment processing
- Authentication systems

---

## Deliverables

### Data Server

```text
data_server/
├── app.py
├── database.py
├── models.py
├── schemas.py
├── seed.py
└── supportscout.db
```

### API Endpoints

```text
GET /health

GET /orders/{order_id}

GET /orders/{order_id}/shipment

GET /orders/{order_id}/return

GET /customers/{customer_id}

GET /customers/{customer_id}/account-diagnostics

GET /customers/{customer_id}/checkout-diagnostics
```

### SupportScout Integration

```text
src/support_scout/clients/support_data_client.py
```

### Operational Evidence

```python
OperationalEvidence
```

---

## Success Criteria

### Functional

- Support server starts successfully
- Synthetic data loads
- API endpoints return expected data
- SupportScout can retrieve operational records

### Quality

- Structured record validation
- Consistent synthetic data
- Deterministic API responses

### Safety

- Read-only APIs only
- No real customer data
- No restricted actions

---

## Risks

### Data Quality

Mitigation:

- Seeded deterministic data
- Fixed reference scenarios

### Future Tool Integration

Mitigation:

- Client abstraction layer
- Stable endpoint contracts
