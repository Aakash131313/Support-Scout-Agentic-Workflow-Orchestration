# SupportScout Constitution

Non-negotiable principles. Every specification, plan and implementation is checked
against these. A change that violates one requires an explicit, recorded amendment.

## I. Human authority over restricted actions

The system never approves, issues, promises or schedules a refund, credit or payment;
never modifies an order, account, subscription or address; never grants a policy
exception. These decisions belong to a human.

*Enforcement:* deterministic screening before any model call; restricted-claim
detection in QA; a human-in-the-loop gate that only the kernel can invoke.

## II. Evidence before confidence

Every customer-specific claim traces to `OP-` operational evidence. Every general
recommendation traces to `EV-` public evidence. Evidence identifiers are minted
deterministically by the registry; a model can cite one but never invent one.

*Enforcement:* `EvidenceRegistry` owns identifier minting; submission tools reject
unknown identifiers; QA verifies grounding before approval is possible.

## III. Deterministic controls outrank model output

A model interprets, drafts and chooses. It never decides whether an escalation applies,
whether a URL is safe, whether content is publishable, or whether a workflow may
advance.

*Enforcement:* the kernel validates transitions; a failed deterministic check cannot be
argued away by any agent.

## IV. Privacy by construction

Customer-specific data appears only in that customer's own response. Reusable
documentation is customer-agnostic and is verified so deterministically, not by prompt
instruction.

*Enforcement:* `ArticlePrivacyValidator` rejects every identifier family in body text;
`redact()` filters every log and trace write.

## V. Honest limitation

Insufficient evidence produces an escalation, not an invention. Conflicting sources are
disclosed. Evaluation reports numerator and denominator, never a bare percentage, and
never describes curated results as production performance.

## VI. Auditability

Every run produces a reconstructable record: agent steps, tool calls, delegations,
state transitions, human decisions and errors. Artifacts are written whatever the
terminal state, including escalation and failure.

*Enforcement:* run-scoped JSONL trace; append-only error audit; artifacts written in a
`finally` block.

## VII. Offline reproducibility

The default test suite runs with no API keys, no network and no live provider. Live
integration is separately marked and never implied by offline success.
