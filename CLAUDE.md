# CLAUDE.md

Working agreement for AI coding agents contributing to SupportScout.

Read this before changing anything. The architecture encodes safety decisions that are
not obvious from the code alone, and several "simplifications" would silently remove a
guarantee.

---

## What this project is

An agentic customer-support workflow. Six `smolagents.ToolCallingAgent` instances, each
with explicit `@tool` functions, coordinated by an orchestrator that is itself an agent,
bounded by a deterministic `WorkflowKernel`.

**The governing rule: the agent chooses, the kernel decides whether the choice is
legal.**

---

## Non-negotiables

These come from `.specify/memory/constitution.md`. Violating one requires an explicit,
recorded amendment — not a quiet code change.

1. **Human authority.** Never approve, issue, promise or schedule a refund, credit or
   payment. Never modify an order, account or address. Never grant a policy exception.
2. **Evidence before confidence.** Customer-specific claims need `OP-` evidence; general
   guidance needs `EV-`. Identifiers are minted by `EvidenceRegistry`, never by a model.
3. **Deterministic controls outrank model output.** A model interprets and drafts. It
   never decides whether an escalation applies or whether a workflow may advance.
4. **Privacy by construction.** Reusable articles carry no customer identifier, verified
   deterministically.
5. **Honest limitation.** Insufficient evidence escalates. It does not get filled in.
6. **Auditability.** Every run leaves a reconstructable trace and writes artifacts
   whatever the terminal state.
7. **Offline reproducibility.** `pytest` passes with no keys and no network.

---

## Before you change anything

```bash
pip install -e ".[dev]"
pytest
```

If the suite is not green before your change, fix that first.

---

## Architecture rules

### Adding a tool

Tools are `@tool` functions built by a factory closing over a run-scoped workspace:

```python
def build_x_tools(workspace: XWorkspace, *, registry: EvidenceRegistry) -> list[Any]:

    @tool
    def do_something(thing_id: str) -> str:
        """One-line summary the model will read.

        Args:
            thing_id: What this argument is, concretely.
        """
        return json.dumps({"status": "ok"})

    return [do_something]
```

Requirements:
- Type hints on every parameter and the return.
- An `Args:` entry for every parameter. smolagents derives the schema from it.
- Return a JSON string, always.
- **Return structured failures; do not raise.** An exception kills the agent loop. A
  `{"status": "rejected", "reason": "..."}` observation lets the agent correct itself.
- Rejections must be instructive: name the valid alternatives.

Then update `EXPECTED_TOOLS` in `tests/unit/test_agentic_contract.py`. That test is
deliberately strict — it is what proves the system is still agentic.

### Adding a workflow state

1. Add to `WorkflowStatus` in `schemas.py`.
2. Add to `_ALLOWED_TRANSITIONS` in `workflow/kernel.py`.
3. Add to `REQUIRED_STATES_FOR_SPECIALIST` if a delegation depends on it.
4. Add a kernel test.
5. Update `specs/001-agentic-refactor/data-model.md`.

### Adding an escalation reason

1. Add to `EscalationReason`.
2. Decide whether it is a *restricted action*. If so, add it to
   `RESTRICTED_ACTION_REASONS` in `hitl.py` — that is what fires the human gate.
3. Add a screening rule or a QA derivation in `_escalation_reason_for`.
4. Add an adversarial test.

---

## Things that look like improvements but are not

**"This tool should raise instead of returning an error dict."** No. Raising kills the
agent loop. Structured returns are what let the agent recover from an unknown order.

**"The kernel duplicates what the prompt says."** That is the point. The prompt asks;
the kernel enforces. If they disagree, the kernel wins.

**"QA could just call the validator directly."** That was the previous implementation.
It meant QA contained no agent at all.

**"The orchestrator could sequence the specialists directly."** That is a pipeline. It
is what this refactor removed.

**"Let the model pass evidence IDs as arguments."** Then it can fabricate or collide
them, and QA's grounding check becomes a format regex instead of a real lookup.

**"Add a deterministic fallback mode for reliability."** Explicitly out of scope. See
`research.md` R-011. Agentic is the only path.

**"Replace the regex safety rules with a model classifier."** Deterministic controls
must not depend on model output.

---

## Testing expectations

| Change | Required tests |
|---|---|
| New tool | Unit test for success, failure and rejection paths; update `EXPECTED_TOOLS` |
| New state or transition | Kernel test for legal and illegal moves |
| New escalation reason | Adversarial test proving it fires and reaches the artifact |
| Safety rule change | Paraphrase tests — at least three phrasings |
| Prompt change | Update the matching `prompts/*.md`; add a decision-log entry if the rationale changed |

Integration tests use `ScriptedAgent`, which runs a chosen tool sequence against the
**real** tools. Do not replace it with mocks of the tools themselves; that would test
nothing.

---

## Style

- Explain *why*, not *what*. The code says what it does.
- Comment the non-obvious: why a check is deterministic, why an order matters, why a
  previous approach failed.
- Type hints throughout. `from __future__ import annotations` at the top.
- No bare `except:`. Catch `SupportScoutError` or a specific subclass; `except Exception`
  only at a boundary where the error is logged and converted.
- Exception messages are sanitized. They appear in logs. No keys, no message bodies.
- ASCII only in source files.

---

## Common pitfalls

**Registry identity.** Tools close over the `EvidenceRegistry` passed at construction.
The orchestrator calls `registry.reset()` between runs rather than replacing the
attribute — replacing it would leave every tool pointing at the previous run's evidence.
This was a real bug caught in testing.

**Artifacts in `finally`.** `OrchestratorAgent.run` writes artifacts in a `finally`
block. Do not move that into the success path; escalated and failed runs must leave a
record.

**Logger propagation.** Specialists receive the run's logger at the start of each run.
A specialist holding a stale logger writes to the wrong trace file.

**Prompt and doc drift.** Changing an `INSTRUCTIONS` constant without updating
`prompts/<agent>.md` leaves the documentation lying.

---

## Reference

| Question | File |
|---|---|
| What are the principles? | `.specify/memory/constitution.md` |
| What was built and why? | `specs/001-agentic-refactor/spec.md` |
| Why this design over alternatives? | `specs/001-agentic-refactor/research.md` |
| What are the contracts? | `specs/001-agentic-refactor/data-model.md` |
| How do I verify a change end to end? | `specs/001-agentic-refactor/quickstart.md` |
| Which test covers which requirement? | `tests/TRACEABILITY_MATRIX.md` |
