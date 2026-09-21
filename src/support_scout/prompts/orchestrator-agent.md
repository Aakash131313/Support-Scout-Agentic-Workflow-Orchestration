# Orchestrator Agent Prompt

**Version:** 2.1 (agentic refactor) · **Source:** `agents/orchestrator_agent.py`

## Role

Coordinate five specialists by selecting delegation tools. It performs no support work
of its own.

## Tools

`inspect_workflow_state`, `delegate_to_triage`, `delegate_to_research`,
`delegate_to_support`, `delegate_to_qa`, `delegate_to_documentation`,
`finalize_workflow`.

## Contract

The kernel is the only source of truth for workflow state. The prompt instructs the
agent to read state rather than assume it, and each tool observation reports the
resulting state.

## Boundaries

- Never performs triage, research, drafting, review or documentation itself.
- Never copies data between tools; delegation tools inject their own context.
- Never bypasses a rejected transition.

## Finalization is the only exit

`finalize_workflow` is the sole tool that completes a run. The prompt states that
`final_answer` must never be used in its place, because doing so ends the turn with the
workflow unfinalized and the run is recorded as a failure.

This was the last agent to receive that instruction, and its absence was expensive. See
the change note.

## Escalation handling

The prompt states plainly that escalation is a *successful* outcome, not an error. This
matters: framed as a failure, a model tries to route around it. Framed as an outcome, it
finalizes cleanly.

## Error recovery

Read the reason, do not repeat an identical failing call, inspect state once, take the
valid action. Stop after two failures of the same action rather than looping.

That instruction alone proved insufficient — a run was observed retrying the same failing
delegation five times — so the kernel now enforces the limit independently.

## Deterministic counterpart

Delegation preconditions, transition legality, budgets and escalation are all enforced
by `WorkflowKernel`. The prompt cannot grant what the kernel denies.

The kernel also counts consecutive failures per specialist. After two, it escalates with
`agent_execution_failure` and a specific summary, rather than allowing retries to
consume the run's budget and end with an unexplained failure.

## Change notes

**2.0 —** Rewritten from a ~100-line state-machine table. The table duplicated rules the
kernel already enforced, which made the prompt fragile without making the workflow
safer.

**2.1 —** Added the `finalize_workflow` instruction.

An earlier pass added a "never call `final_answer` instead of your submit tool" warning
to all five specialist prompts and missed the orchestrator. The consequence appeared on
a ticket where every specialist succeeded: triage, research, support, QA and
documentation all completed, the workflow reached `documented`, and then the
orchestrator called `final_answer` instead of `finalize_workflow`. Because
`kernel.finalized` stayed false, the post-run guard recorded the run as `failed` with no
escalation reason — the least informative possible outcome for a run that had done
everything correctly.

The same trace confirmed the warning works where it was applied: every specialist called
its own submit tool and only then `final_answer`, which is harmless because the
submission had already happened.
