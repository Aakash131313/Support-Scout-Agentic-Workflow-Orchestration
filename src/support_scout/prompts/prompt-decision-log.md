# Prompt Decision Log

Design decisions, alternatives and rationale. No hidden chain-of-thought.

The governing principle: **a prompt asks, a tool enforces.** Every safety, privacy or
provenance rule below has a deterministic counterpart in code. Where the two could
disagree, the code wins.

## PD-001: Enforce in tools, explain in prompts

**Decision:** Any rule that matters is implemented in a tool or validator. The prompt
explains the rule so the model can comply, but compliance is never the safety mechanism.

**Alternative:** Rely on well-written instructions.

**Rationale:** The previous implementation demonstrates why. The Documentation Agent's
prompt contained twenty-two separate privacy instructions, while its deterministic body
check was inert. A single instruction the model overlooked would have leaked a customer
identifier into reusable documentation.

**Impact:** Prompts got shorter. Tools got stricter.

## PD-002: Name the cost of each failure mode

**Decision:** Prompts state which error is worse, not merely what to avoid.

**Examples:** QA is told approving an unsupported claim is the most damaging outcome and
to prefer revise when torn. Triage is told low confidence routes to a human and is
better than a confident wrong answer.

**Rationale:** Given a symmetric-sounding choice, a model tends to pick the one that
looks more helpful. Naming the asymmetry corrects that.

## PD-003: Frame escalation as success

**Decision:** The orchestrator prompt states that escalation is a legitimate outcome and
that it should finalize rather than route around it.

**Rationale:** Framed as a failure, an agent retries, tries alternative specialists, or
loops. Framed as an outcome, it stops cleanly. The kernel would have blocked those
attempts anyway, but every blocked attempt costs a step from the budget.

## PD-004: Research must be allowed to find nothing

**Decision:** The Research Agent prompt states explicitly that reporting insufficient
evidence is a correct outcome.

**Alternative:** Instruct it to always produce guidance.

**Rationale:** "Evidence before confidence" only holds if admitting a gap is an
acceptable answer. Without that permission, a model fills the gap from memory.

**Impact:** Some tickets escalate for insufficient evidence that a less careful system
would have answered. That is the intended trade.

## PD-005: Separate urgency from sentiment, with examples in both directions

**Decision:** The triage prompt gives two concrete cases: angry plus routine equals low
urgency; calm plus compromise equals high urgency.

**Rationale:** Stated abstractly, models conflate distress with severity. The paired
examples are what make AT-017 and AT-018 pass on tone as well as on the deterministic
rule.

## PD-006: Guide tool selection with a worked example

**Decision:** The Support Agent prompt says a delayed-delivery question needs order and
shipment but not return or checkout.

**Rationale:** Told only to "call relevant tools", a model calls everything to be safe,
which reproduces exactly the behaviour the refactor removed. A concrete example of
*restraint* is what makes selection real.

## PD-007: Treat missing records as information

**Decision:** The Support Agent prompt says `available: false` is real information to
report plainly.

**Rationale:** Tools return structured misses rather than raising, so the agent needs to
know what to do with one. Without guidance, a model either retries pointlessly or
glosses over the gap.

## PD-008: Rejections must be instructive

**Decision:** Every submission tool returns a specific reason and, where useful, the
valid alternatives — allowed keys, valid evidence identifiers, the exact identifier that
breached privacy.

**Alternative:** Reject with a generic error.

**Rationale:** An agent can only correct what it can see. Naming the offending
identifier turns a dead end into a one-step fix, which is what makes the documentation
privacy recovery path work.

## PD-009: Ticket and page text are data

**Decision:** Untrusted content is wrapped in `<ticket>` delimiters and labelled as data
in every prompt that handles it.

**Rationale:** This was the one genuinely good pattern in the previous prompts and it is
carried forward unchanged. It is the prompt-side half of AT-003 and AT-004; the
deterministic half is injection screening before any model call, plus the fact that
scraped text can only ever become inert evidence.

## PD-010: No hidden reasoning in output

**Decision:** Prompts request concise rationale summaries, never internal deliberation,
and nothing resembling private reasoning is persisted to an artifact or log.

**Rationale:** Audit records must be reviewable without exposing model internals, and a
rationale field that invites deliberation tends to leak customer data into it.

## PD-011: Describe capability accurately

**Decision:** Prompts state what the system *can* do, including reading real operational
records.

**Rationale:** The previous Support Agent prompt included a worked example ending "this
automated workflow cannot verify order-specific shipment status". That stopped being
true at Phase 33. A prompt that understates capability produces unhelpful replies and
teaches the model a false limitation.

## PD-012: Shorten the orchestrator prompt

**Decision:** Replaced a ~100-line state-action table with a compact progression plus
error-recovery guidance.

**Rationale:** The table restated rules the kernel already enforced. Duplicated rules
drift: a change to the transition table would have silently contradicted the prompt.
The kernel rejects invalid moves and explains why, so the agent learns from the
observation rather than from a memorised table.

## PD-013: Every agent is told its submit tool is the only exit

**Decision:** Every agent prompt states that `final_answer` must never be used in place
of its own submit tool, and that an answer delivered through `final_answer` is
discarded.

**Origin:** Live traces, repeatedly. The Support Agent looked up an unknown order,
received two `available: false` results, wrote a correct and helpful explanation, and
delivered it through `final_answer`. The draft was never submitted, the delegation
failed, and the run escalated. The same shape appeared on research-only tickets, and —
most expensively — on the orchestrator, where calling `final_answer` instead of
`finalize_workflow` recorded a fully successful run as `failed`.

**Alternative considered:** Detect the pattern in the kernel and treat a terminal
`final_answer` as an implicit submission.

**Rejected because** it would invent a result the agent never committed to. A draft
that was never submitted has not passed the submission tool's validation, so
manufacturing one would bypass the citation and schema checks that make submission
meaningful.

**Rationale for the wording:** the first version of this warning was scoped to the
missing-record case and read "even when every tool you called returned
`available=false`". On a pure research ticket the agent calls no operational tool at
all, never sees that condition, and the warning appears inapplicable. The instruction
now enumerates all three paths explicitly — data returned, absence returned, and no
operational tool called — because a model follows the case it recognises.

## PD-014: Tell QA when its own checks have already answered the question

**Decision:** `check_operational_claims` states in its description that a passing result
means operational grounding has been verified and is not a valid reason to request a
revision. `submit_qa_decision` enforces it.

**Origin:** Three tickets escalated as `revision_limit_exceeded` while every
deterministic check passed. QA's objection, in its own words, was "operational claims
regarding the order status are not backed by valid OP- evidence" — on a draft citing
OP-001 and OP-002. The Support Agent resubmitted with the same citations because there
was nothing to change, and the budget ran out on a ticket that needed no revision.

**Alternative considered:** Prompt-only guidance, with no tool enforcement.

**Rejected because** the orchestrator prompt already said "stop after two failures of
the same action" and was observed retrying five times. A prompt is a request.

**Deliberate limit:** only *operational grounding* objections are blocked, and only when
that specific check passed. Editorial revisions — tone, clarity, a missing step, or a
request to cite public evidence — are untouched, and `escalate` is never blocked. QA
keeps every power except the one to demand something its own tools have disproved.

## PD-015: A prompt fix and a deterministic guard are not alternatives

**Decision:** Where a prompt-level failure had a bounded deterministic backstop
available, both were implemented.

**Examples:** The orchestrator is told to stop retrying a failing delegation, *and* the
kernel escalates after two consecutive failures. QA is told a passing check is not
grounds for revision, *and* the submit tool refuses one.

**Rationale:** The prompt fixes the common case cheaply and preserves the model's
judgment. The guard bounds the cost when the prompt does not take. Neither alone was
sufficient in practice: prompts were observed being ignored, and guards alone produced
correct-but-unhelpful outcomes, such as a model choosing `escalate` because a rejection
message listed it as an equally valid option. The rejection text now names the expected
decision rather than presenting three neutral alternatives.
