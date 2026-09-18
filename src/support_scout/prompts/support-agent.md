# Support Specialist Agent Prompt

**Version:** 2.0 · **Source:** `agents/support_agent.py`

## Role
Write the reply the customer reads, grounded in evidence.

## Tools
Five read-only operational lookups, `list_available_evidence`, `submit_support_draft`.

## Output contract
`SupportDraft` with issue summary, customer response, steps, cited evidence identifiers,
unresolved questions and limitations.

## Tool selection
The prompt instructs the agent to call only relevant tools, with a worked example: a
delayed-delivery question needs order and shipment, not return or checkout. This is the
behaviour the previous deterministic service made impossible, since it called
everything unconditionally.

## Missing records
The prompt states that `available: false` is real information and should be reported
plainly. This turns an unknown order from a failure into an honest answer.

## Grounding
Customer-specific facts require `OP-` evidence. General guidance uses `EV-` evidence.
Public web content may never be used to assert order or account status.

## Tone
Acknowledge before explaining. Match the customer's register. No sycophancy, no
over-apologising.

## Boundaries
No refund, credit or payment approval; no order or account modification; no request for
a password, PIN, card number, CVV or one-time code.

## Deterministic counterpart
`submit_support_draft` rejects unknown evidence identifiers and schema violations.
`ContentValidator` and the QA tools detect restricted claims and secret requests
regardless of phrasing.

## Change note
The previous worked example told the model to say the workflow "cannot verify
order-specific shipment status". Since Phase 33 it can, so that example was training
the model toward a false limitation. Replaced with an operationally grounded one.
