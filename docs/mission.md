# Mission

SupportScout is an agentic customer-support workflow for e-commerce. It reads a
support ticket, gathers evidence from both public documentation and read-only
operational records, drafts a reply, reviews that reply against deterministic checks,
and publishes a reusable troubleshooting article.

It assists human support specialists. It does not replace their authority.

## Principles

**Accuracy before speed.** An uncertain answer delivered quickly is worse than an
honest escalation. Low confidence routes a ticket to a human rather than producing a
confident guess.

**Evidence before confidence.** Customer-specific claims must be grounded in `OP-`
operational evidence. General guidance must be grounded in `EV-` public evidence. A
claim with no evidence behind it does not ship.

**Human authority.** SupportScout never approves a refund, authorizes a payment, grants
a policy exception, or modifies an order or account. Where a restricted action is
requested, a human decides.

**Privacy by construction.** Customer-specific data stays in the customer's own
response. Reusable documentation is scrubbed of every identifier deterministically, not
by asking a model nicely.

**Transparent limitations.** The system states what it could not determine. Conflict
detection is a heuristic and is documented as one.

## Scope

Supported domains:

- `order_tracking_delivery` — delays, missing tracking, delivered-but-not-received
- `returns_refunds` — how to return, eligibility, status of an in-flight return
- `account_checkout` — sign-in problems, checkout and payment failures

Anything else is classified `unsupported` and escalated without a forced guess.

## Escalation conditions

Nine conditions halt automated handling and route the ticket to a human:

1. Refund or financial authorization
2. Policy exception
3. Suspected account compromise
4. Sensitive data in the ticket
5. Unsupported domain
6. Classification confidence below threshold
7. Insufficient evidence
8. Conflicting evidence
9. QA rejection past the revision limit

Three of these are *restricted actions* (1, 2, 3) and trigger the single
human-in-the-loop gate, which asks an operator whether automated handling may continue.
The other six escalate directly to a human queue without interrupting the customer.

## Sentiment

Sentiment is measured and it shapes tone and priority. It never confers authority.

An angry customer asking a routine tracking question receives a warmer reply and normal
handling. A calm customer reporting unauthorized account access is escalated
immediately. Risk drives escalation; feeling does not.

## Out of scope

- Real customer systems, payment processing, or order modification
- Refund, credit, policy-exception or account authorization of any kind
- Authenticated scraping, paywall circumvention or access-control bypass
- Production deployment, multi-tenancy or a web interface
