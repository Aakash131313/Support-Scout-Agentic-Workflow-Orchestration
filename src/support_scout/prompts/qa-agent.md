# QA Agent Prompt

**Version:** 2.1 · **Source:** `agents/qa_agent.py`

## Role

Senior reviewer. The last check before a reply reaches a customer.

## Tools

`check_evidence_grounding`, `check_restricted_claims`, `check_sensitive_data`,
`check_operational_claims`, `request_support_revision`, `submit_qa_decision`.

## Output contract

`QAResult` with decision, issues, revision instructions and, when escalating, the
specific reason.

## Decision guidance

The prompt defines each decision and, importantly, gives a tie-breaker: when genuinely
torn between approve and revise, choose revise. It also names the worst failure mode
explicitly — approving an unsupported claim — because a model needs to know which error
is more costly.

That tie-breaker has a bound. When every deterministic check has passed, preferring
revise is no longer conservative; it is a cost with no safety benefit, and on three
tickets it exhausted the revision budget on drafts that needed no change. The submit
tool now enforces that bound. See the change note.

## Revision quality

Instructions must say what is wrong *and* what would fix it. A revision instruction that
only restates the problem produces another failing draft.

A revision must also be *achievable*. Asking for evidence the deterministic checks have
already confirmed is present gives the Support Agent nothing to act on; it resubmits the
same draft and a revision round is spent for nothing.

## Authority

A failed deterministic check cannot be argued away. The prompt says so, and the submit
tool enforces it.

The converse now holds too: a *passing* check is a verified result, and its subject is
not available as grounds for a revision. `check_operational_claims` states this in its
own description, so the agent learns it from the tool observation rather than from the
prompt alone.

## Deterministic counterpart

`submit_qa_decision` refuses submission until all four checks have run and refuses
approve while any is failing. The escalation reason is derived from which check failed,
not chosen by the model.

It is also idempotent: the first decision is final and a repeat call returns
`already_submitted`. A *rejected* call is not a submission — the workspace is untouched
and the agent is expected to call again with a valid decision.

`check_operational_claims` reads the customer response, not only the citation list. Any
concrete statement of this customer's operational status requires an `OP-` citation.

## Change notes

**2.0 —** The previous QA Agent contained no model call at all — it was a direct
`ContentValidator.validate()` call. Its validation logic survives as the deterministic
authority the agent now operates within. Escalation reasons are no longer flattened to
`qa_failure`.

**2.1 —** Two behaviours were bounded after live runs.

*Repeat submission.* `submit_qa_decision` was observed being called eleven times in a
single run. Each call returned `{"status": "submitted"}`, so the agent had no signal it
was finished; it called again, switched its decision from `revise` to `escalate` on the
sixth call, and silently overwrote its own earlier result. Roughly 41k input tokens were
spent before a rate limit and the step ceiling stopped it. The first decision is now
final.

*Unwinnable revisions.* Three tickets escalated as `revision_limit_exceeded` while every
deterministic check passed. QA's stated objection was that operational claims were "not
backed by valid OP- evidence" — on drafts citing OP-001 and OP-002, with
`check_operational_claims` returning `passed: true`. The submit tool now refuses a
revision whose stated reason is about operational grounding when that check passed, and
its rejection names `approve` as the expected decision rather than presenting three
neutral options. Editorial revisions and `escalate` are untouched.
