# Operations Service API

Read-only synthetic operational data. Base URL: `http://127.0.0.1:8001`.

There is no POST, PUT, PATCH or DELETE route. The service cannot modify anything.

| Method | Path | Returns | 404 when |
|---|---|---|---|
| GET | `/health` | `{status, service}` | never |
| GET | `/customers/{customer_id}` | customer with masked email | unknown customer |
| GET | `/orders/{order_id}` | order incl. `customer_id` | unknown order |
| GET | `/orders/{order_id}/shipment` | shipment with masked tracking | no shipment for that order |
| GET | `/orders/{order_id}/return` | return + refund status | no return for that order |
| GET | `/customers/{customer_id}/checkout-diagnostics` | latest attempt, safe message | no diagnostics |
| GET | `/customers/{customer_id}/account-diagnostics` | latest account event | no diagnostics |

## Seeded data

| Record | Detail |
|---|---|
| `CUS-001` … `CUS-004` | Active customers, emails masked |
| `ORD-1001` | Shipped, `SHP-1001` in transit, due 2026-09-14 |
| `ORD-1002` | Delivered, `SHP-1002` delivered at front door |
| `ORD-2001` | Returned, `RET-2001` received, refund `pending_review` |
| `ORD-1003` | Processing, **no shipment record** |
| `ORD-3001` | Shipped, `SHP-3001` carrier exception |
| `CHK-3001` | `CUS-003`, address validation failed |
| `CHK-3002` | `CUS-001`, payment declined |
| `ACC-4001` | `CUS-004`, recovery completed, latest login failed |

## Intentionally absent

`ORD-9999` and `CUS-999` do not exist. Their absence is what makes the missing-record
scenarios a genuine test rather than a simulated one.

## Safety properties

- Emails are masked at rest (`d***1@example.test`).
- Tracking numbers are partially redacted at rest (`TRK-****1001`).
- No endpoint returns a password, token, session or full payment card number.
- `refund_status` is reported, never set.
