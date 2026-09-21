# Support Specialist Agent Prompt

**Version:** 2.1 · **Source:** `agents/support_agent.py`

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

Live traces confirm it works. On a delayed-delivery ticket the agent calls
`get_order_status` and `get_shipment_status` and leaves the other three alone.

## Missing records

The prompt states that `available: false` is real information and should be reported
plainly. This turns an unknown order from a failure into an honest answer.

A confirmed absence is also registered as citable `OP-` evidence, so "I checked and
could not find it" is a grounded statement rather than an unsupported one.

## Submission is not optional

Every reply is delivered through `submit_support_draft`. The prompt states this for all
three paths to a draft, enumerated explicitly:

- operational tools returned data
- operational tools returned `available: false`
- no operational tool was called at all, because the question is general or no
  identifier was supplied

The third case is stated separately because the agent was observed skipping submission
on exactly that path. See the change note below.

## Grounding

Customer-specific facts require `OP-` evidence. General guidance uses `EV-` evidence.
Public web content may never be used to assert order or account status.

For a general question with no operational reference, `EV-` evidence alone is
sufficient grounding, and the prompt says so — otherwise the grounding rule reads as a
reason not to answer at all.

## Tone

Acknowledge before explaining. Match the customer's register. No sycophancy, no
over-apologising.

## Boundaries

No refund, credit or payment approval; no order or account modification; no request for
a password, PIN, card number, CVV or one-time code.

## Deterministic counterpart

`submit_support_draft` rejects unknown evidence identifiers and schema violations, and
enforces the same citation rule QA applies, so a draft QA is guaranteed to reject is
caught a full agent-round earlier. `ContentValidator` and the QA tools detect restricted
claims and secret requests regardless of phrasing.

The submission tool is idempotent: a repeat call returns `already_submitted` and the
first draft stands.

## Change notes

**2.0 —** The previous worked example told the model to say the workflow "cannot verify
order-specific shipment status". Since Phase 33 it can, so that example was training
the model toward a false limitation. Replaced with an operationally grounded one.

**2.1 —** The submission rule was rewritten after two tickets failed on it. The earlier
wording sat under a heading reading "When a record is not found:" and said "even when
every tool you called returned `available=false`". On a research-only ticket — how to
return an unopened item, a shipping policy question — no identifier is supplied, no
operational tool is called, that condition never occurs, and the warning reads as
inapplicable. The agent wrote a correct four-step answer and delivered it through
`final_answer`, so nothing was submitted and the run escalated.

The rule is now stated for every path rather than for one. The task text was also
changed: it previously closed with "call the operational tools that are actually
relevant, then submit your draft", which resolves to nothing when no lookup is
possible. With no identifier supplied it now says so plainly and names the submission
tool. Tickets that do supply an identifier receive byte-identical task text.
