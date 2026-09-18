# Orchestrator Agent Prompt

**Version:** 2.0 (agentic refactor) · **Source:** `agents/orchestrator_agent.py`

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

## Escalation handling
The prompt states plainly that escalation is a *successful* outcome, not an error. This
matters: framed as a failure, a model tries to route around it. Framed as an outcome, it
finalizes cleanly.

## Error recovery
Read the reason, do not repeat an identical failing call, inspect state once, take the
valid action. Stop after two failures of the same action rather than looping.

## Deterministic counterpart
Delegation preconditions, transition legality, budgets and escalation are all enforced
by `WorkflowKernel`. The prompt cannot grant what the kernel denies.

## Change note
Rewritten from a ~100-line state-machine table. The table duplicated rules the kernel
already enforced, which made the prompt fragile without making the workflow safer.
