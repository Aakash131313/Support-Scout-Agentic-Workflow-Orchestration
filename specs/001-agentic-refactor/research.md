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

---

## R-013: Structural tests instead of enumerated phrase lists

**Decision:** Deterministic content checks reason about sentence structure — negation,
hedging, subject agency, topical subject — rather than matching enumerated phrases.

**Alternatives:** Keep extending the phrase lists; replace the checks with a model
classifier.

**Rationale:** R-005 already replaced literal aliases with token co-occurrence for
safety screening, and that reasoning was sound. It was not carried far enough. Five
separate false positives in live runs each traced to an enumerated list that the model
simply stepped outside of:

| Enumerated list assumed | Model actually wrote |
|---|---|
| `"eligible" ... "not eligible"` anywhere in the combined text | one help page legitimately stating both sides of a conditional rule |
| `"is eligible for return"` | `"are eligible for return"` |
| `"could not find"` | `"could not locate"` |
| `"not backed by"` | `"need to be supported by"` |
| `"lacks evidence"` | `"lacks proper citation of operational evidence"` |

Each patch held until the next paraphrase. The pattern is the point: a list of surface
forms is a list of the forms already observed, and a language model's output space is
not enumerable.

What replaced them:

- *Restricted claims.* Sentence-scoped, asking whether a sentence asserts first-person
  agency over a restricted action, unhedged and unnegated. "I approved your refund"
  fires; "the order was not successfully placed or has been canceled" does not, because
  the negation is scoped to the sentence rather than lost in concatenation.
- *Inspection claims.* Excused by negation or hedging — the same rule passive
  completions already used — with the phrase list demoted to a secondary path for
  absences stated without an explicit negation. The negation signal was already being
  computed for every sentence and discarded.
- *Conflict detection.* Occurrence-level: each topic keyword is classified affirmative
  or negative by inspecting the words before it, so `"not eligible for return"` no
  longer matches the affirmative pattern by substring. A conflict requires two
  *different* sources holding opposed positions; one document stating both sides of its
  own conditional rule is normal guidance.
- *QA objections.* Topical rather than phrasal: does the objection concern evidence
  *and* concern operational status? That question survives paraphrase, where a list of
  negative phrasings did not.

A model classifier was rejected for the same reason as in R-005: deterministic controls
must not depend on model output.

**Consequence:** These checks are harder to read than a list of strings, and the
tradeoff is explicit. Each is documented with the specific live failure that motivated
it, so a future maintainer can tell a deliberate design from an accumulation of
patches.

**Residual risk, stated rather than hidden:** hedged passive constructions still pass —
"your refund may have been approved" is not flagged. That is the deliberate cost of
allowing "the order may have been canceled" as legitimate speculation. It asserts
nothing, and the operational-grounding check applies to the same draft independently.

## R-014: A confirmed absence is evidence; a service outage is not

**Decision:** `SupportDataNotFound` registers `OP-` evidence with
`facts.available = false`. `SupportDataClientError` registers nothing.

**Alternatives:** Register both, as the first implementation did. Register neither, as
the original did.

**Rationale:** These look alike at the call site and are different in kind.

"This order does not exist in the operations system" is a verified fact about the
customer's record, obtained by querying the authoritative source. It is exactly the
sort of thing a reply should be grounded in, and without a citable identifier the
statement "I checked and could not find it" is indistinguishable from a guess.

"We could not reach our own service" is a fact about our infrastructure. Nothing was
learned about the order. Citing it as evidence for a claim about the customer's order
would be a category error, and IT-007 asserts it must not happen.

Registering the absence is also what makes the stricter operational-claims rule in
R-015 satisfiable: if an operational tool was called at all, there is an identifier to
cite, so the rule can never create a loop the agent cannot exit. During an outage there
is no status to assert, so the rule does not fire and the workflow degrades to public
guidance — which is what that scenario is for.

**Consequence:** A run against an unknown order now carries two `OP-` records
describing the absence. `operational_sources.json` documents what was checked as well as
what was found.

## R-015: Deterministic checks verify content, not only identifiers

**Decision:** `check_operational_claims` reads the customer response and requires an
`OP-` citation for any concrete statement of this customer's operational status.

**Alternative:** Leave it validating cited identifiers only.

**Rationale:** The check passed vacuously. Its logic was "every `OP-` identifier you
cited must be real", so a draft citing none passed trivially regardless of what it
asserted. A reply stating "your order is in transit and will arrive Thursday", backed
by nothing but public web pages, satisfied a check whose docstring claimed to verify
that customer-specific claims were operationally grounded.

That contradicted both the check's own name and Principle II. The gap was latent rather
than actively failing — the Support Agent's prompt tells it to ground claims and it
generally does — but nothing enforced it, and "generally does" is not a control.

**Consequence:** Requires a claim detector with the failure modes R-013 describes. The
same structural discipline applies, and the detector is scoped to concrete status
assertions: it skips sentences reporting an absence, hedging, or describing how orders
behave in general rather than how this one does.

## R-016: Bound retries in the kernel, not only in the prompt

**Decision:** The kernel counts consecutive delegation failures per specialist and
escalates after two with `agent_execution_failure`.

**Alternative:** Rely on the orchestrator prompt, which already said "stop after two
failures of the same action".

**Rationale:** The prompt said it. A live run retried a failing delegation five times
anyway, spending roughly 50k tokens before the step budget collapsed, and the run ended
as `failed` with no escalation reason at all — the least useful outcome available.

This is PD-001 applied to liveness rather than safety. A rule that matters belongs in
code; the prompt explains it so the model can comply, but compliance is not the
mechanism.

**Consequence:** A new `EscalationReason.AGENT_EXECUTION_FAILURE`, and a bounded cost
for any similar failure — two attempts instead of however many the budget allows.

## R-017: Read agent state from the agent

**Decision:** `extract_tool_names` reads `agent.memory.steps` rather than the object
returned by `agent.run(...)`.

**Rationale:** An eighteen-ticket batch recorded zero tool calls across every run,
including four that completed with evidence gathered and drafts approved. Tools
demonstrably ran; the run result did not carry their history. `agent.memory` is what
smolagents' own console renderer reads, which is why the "Calling tool: ..." panels were
visible while the trace files were empty.

**Consequence:** 0 traced tool calls became 503. Extraction tries several known shapes
for a recorded call, because the attribute is not guaranteed across versions, and logs a
diagnostic naming the unrecognised type if none match — so the next run says what to fix
rather than silently reporting zero again.

**Note on the test double.** This broke
`test_run_trace_records_tool_calls_from_multiple_agents`, because `ScriptedAgent` kept
its memory in a local variable and returned it in the run result. The fix went into the
double, not into `base.py`. Adding a fallback to `run_result.memory` would have made the
test pass while exercising a path production never takes — which is precisely how the
original tracing bug survived a green suite in the first place.

## R-018: The offline suite proves mechanism; live runs prove judgment

**Observation, recorded because it shaped every decision above.**

The agentic refactor shipped with a fully green test suite. Running the same eighteen
curated tickets against a live model produced 10 of 18 expected outcomes.

None of the failures were safety failures. Every safety escalation was correct
throughout, with the right reason code and zero delegations, in every run. The offline
suite verified exactly what it was built to verify.

What it could not verify was judgment under real model output: a model choosing
`final_answer` because a warning was scoped to a case it did not recognise; a model
paraphrasing past a phrase list; a model calling a submit tool eleven times because
nothing told it to stop; a QA agent objecting to something its own tools had disproved.
Every one of these is invisible to a scripted harness, because the harness supplies the
tool sequence.

This is an argument for the evaluation harness, not against the test strategy. The
offline suite is what made each fix safe to make — 596 tests confirming that no
correctness fix weakened a safety control. The live harness is what found the defects.
Both are necessary and neither substitutes for the other.

**Practical consequence:** `verify_demos.py` compares every ticket against its
documented expected outcome and flags retry loops, repeated submissions, exhausted
revision budgets, uncited operational evidence and empty traces. Every defect fixed in
this pass has a corresponding detector, so a regression surfaces as a named flag rather
than as a number that looks slightly wrong.
