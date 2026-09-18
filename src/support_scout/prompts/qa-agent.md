# QA Agent Prompt

**Version:** 2.0 · **Source:** `agents/qa_agent.py`

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

## Revision quality
Instructions must say what is wrong *and* what would fix it. A revision instruction that
only restates the problem produces another failing draft.

## Authority
A failed deterministic check cannot be argued away. The prompt says so, and the submit
tool enforces it.

## Deterministic counterpart
`submit_qa_decision` refuses submission until all four checks have run and refuses
`approve` while any is failing. The escalation reason is derived from which check failed,
not chosen by the model.

## Change note
The previous QA Agent contained no model call at all — it was a direct
`ContentValidator.validate()` call. Its validation logic survives as the deterministic
authority the agent now operates within. Escalation reasons are no longer flattened to
`qa_failure`.
