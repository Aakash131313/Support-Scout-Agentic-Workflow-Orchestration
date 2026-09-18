# Research and Decisions

Decision record for the agentic refactor. Records what was chosen, what was rejected,
and why. Contains no hidden reasoning.

---

## R-001: smolagents with `@tool` functions

**Decision:** Every agent is a `smolagents.ToolCallingAgent`; every tool is a function
decorated with `@tool`.

**Alternatives:** A hand-rolled OpenAI tool-calling loop; LangGraph; keeping the custom
orchestrator.

**Rationale:** `@tool` derives the name, description and argument schema from the
function signature and docstring, so the tool contract is legible in one place. A
hand-rolled loop would add code to test without adding capability.

**Consequence:** `smolagents` becomes a hard dependency. It was previously used but
never declared in `requirements.txt`; that is now fixed.

---

## R-002: Delegation as explicit tools, not `managed_agents`

**Decision:** The orchestrator's tools are five separately named `delegate_to_*`
functions.

**Alternatives:** smolagents' native `managed_agents` wiring; a single generic
`delegate(specialist)` dispatcher.

**Rationale:** Five named tools make the coordination structure readable directly from
source, and give one clean place per specialist to validate state, record the
delegation and trace the outcome. `managed_agents` would hide that seam.

**Consequence:** Slightly more code than the generic alternative, in exchange for a
readable and individually testable delegation surface.

---

## R-003: Tool factories closing over a workspace

**Decision:** Tools are built by `build_*_tools(workspace, ...)` factory functions; the
`@tool` functions close over run-scoped state.

**Alternatives:** `Tool` subclasses holding a workspace reference (the previous
approach); global state.

**Rationale:** The previous `Tool` subclasses were chosen precisely because a class can
hold state that a bare function cannot. A closure solves the same problem while keeping
the decorator visible and each tool around ten readable lines.

---

## R-004: Deterministic evidence identifiers

**Decision:** `EvidenceRegistry` mints every `EV-` and `OP-` identifier. Tools never
accept an `evidence_id` argument.

**Alternatives:** Continue passing `evidence_id` in from the caller; let the model
supply one.

**Rationale:** The previous tools took `evidence_id` as a required argument supplied by
the deterministic orchestrator. Once the orchestrator became an agent, that argument
would have had to come from the model, which would let it fabricate or collide
identifiers. Deterministic minting makes QA's grounding check a real registry lookup
rather than a format regex.

---

## R-005: Token co-occurrence instead of phrase aliases

**Decision:** Safety screening and restricted-claim detection match token co-occurrence
and subject/verb/object patterns rather than literal phrases.

**Alternatives:** Extend the alias lists; use a model classifier.

**Rationale:** The alias lists were demonstrably porous. Screening built around
`"approve refund"` missed "please refund me", "I want my money back" and "can you
authorize a refund". Claim detection built around `"i approved your refund"` missed
"I've approved your refund", "your refund is approved" and "refund has been authorized".
Each of those is a real safety bypass. A model classifier was rejected because
deterministic controls must not depend on model output.

**Consequence:** Slightly higher false-positive risk, which is the correct direction:
an unnecessary escalation is recoverable, an unauthorized refund claim is not.

---

## R-006: Single HITL gate at restricted actions

**Decision:** One gate, fired only for `financial_authorization`, `policy_exception`
and `account_compromise`. Denial is the unattended default.

**Alternatives:** A gate before final output; gates at every escalation; no gate.

**Rationale:** SupportScout is customer-facing, so the flow should be interrupted as
little as possible. Restricted actions are where a human decision genuinely changes the
outcome. The other six escalation conditions still route to a human queue; they simply
do not block. Denying by default means the safety property holds with no operator
present.

---

## R-007: Escalation is a finalizable terminal state

**Decision:** `finalize()` accepts `ESCALATED`, and artifacts are written in a `finally`
block.

**Rationale:** Previously an escalated run raised `AgenticOrchestratorError` before
writing anything. The human picking up the escalation received no record at all. A run
that stops early must still leave a truthful trail.

---

## R-008: Triage is agentic, and sentiment is a tool

**Decision:** Triage is a `ToolCallingAgent` with `analyze_sentiment`,
`list_supported_domains` and `submit_triage`.

**Alternatives:** Keep triage as a single structured model call.

**Rationale:** Triage was the only stage with no agentic implementation. Exposing
sentiment as its own deterministic tool makes it independently testable and makes the
separation the mission requires visible: sentiment shapes tone, never authority.

**Consequence:** `services/model_client.py` had no remaining caller and was removed
rather than left as dead code.

---

## R-009: Operations service stays standalone

**Decision:** FastAPI/SQLModel service remains separate, reached over HTTP through
`SupportDataClient`, with a start-up health probe.

**Alternatives:** Collapse into an in-process SQLite module.

**Rationale:** The client boundary is what makes the offline suite possible and what
keeps SupportScout from touching a database directly. A start-up probe was added
because the client previously had no health method at all, so an unreachable service
surfaced as a confusing mid-run 404.

---

## R-010: `customer_reference` added to the ticket contract

**Decision:** `SupportTicket` gains an optional `customer_reference` validated against
`^CUS-[0-9]+$`.

**Alternatives:** Continue regex-extracting identifiers from the message body.

**Rationale:** The seed data settles this. Checkout diagnostics belong to `CUS-003` and
account diagnostics to `CUS-004`, and neither customer has any order. There is no order
to chain from, so the only path to those scenarios was scraping `CUS-003` out of prose.
Orders already had `order_reference`; customers simply never got the equivalent field.

---

## R-011: Superseded specifications

The refactor bundle in `specs/archive/refactor-1/` required three execution modes
(FR-RB-016), shadow comparison (FR-RB-017) and continued availability of the
deterministic path (NFR-RB-006).

**Status: satisfied and retired.**

Those requirements described *migration scaffolding*. Their purpose was to let agentic
behaviour be validated against deterministic behaviour before the switch. That
validation completed: the agentic path passed its gates, and the deterministic path was
removed. Retaining a shadow mode now would leave dead code whose only function is to
satisfy a requirement that has already served its purpose.

Authority for this decision: the FY27 training plan and the project owner's explicit
direction, which take precedence over the intermediate refactor bundle. The bundle is
archived rather than deleted so the history remains inspectable.

**Also superseded:** `tech_stack.md`'s "custom Python orchestrator rather than a
third-party agent framework" and its listing of smolagents and FastAPI as not selected.
Both were reversed; the document has been regenerated to match reality.

---

## R-012: Archived Phase 34 requirements were reconstructed

`specs/phase-34/requirements.md` was lost. The archived copy was reconstructed from the
surviving `plan.md` and `validation.md`, and is labelled as reconstructed rather than
presented as original.
