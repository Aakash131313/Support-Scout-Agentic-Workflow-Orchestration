"""Tools the Orchestrator Agent uses to coordinate the workflow.

The orchestrator is itself a tool-calling agent. Its tools are:

* `inspect_workflow_state` - read the authoritative state from the kernel.
* `delegate_to_*`          - hand one task to one specialist agent.
* `finalize_workflow`      - close the run once it is documented or escalated.

Delegation is written as five explicit, separately named `@tool` functions rather
than a generic dispatcher, so the coordination structure is readable directly from
the source.

Each delegate tool injects authoritative workflow context itself. The orchestrator
never copies ticket data, evidence or drafts between tools, which removes the most
common way for an agent to corrupt state.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from smolagents import tool

from ..exceptions import SupportScoutError, WorkflowError
from ..schemas import EscalationReason
from ..workflow.kernel import WorkflowKernel

#: Signature every specialist adapter satisfies: it receives the kernel and applies
#: its own result through the kernel's `apply_*` method.
SpecialistCallable = Callable[[WorkflowKernel], dict[str, Any]]


def _delegate(
    kernel: WorkflowKernel,
    specialist: str,
    tool_name: str,
    runner: SpecialistCallable,
) -> str:
    """Shared delegation body: validate state, run the specialist, record the outcome.

    Repeated consecutive failures of the same specialist are bounded deterministically.
    The orchestrator's own instructions ask it to stop retrying after two failures, but
    a prompt is a request, not a guarantee -- this enforces the limit regardless of what
    the orchestrator model decides to do, escalating with a specific, named reason
    instead of silently exhausting the run's step budget.
    """
    try:
        kernel.count_tool_call(tool_name)
        kernel.require_state_for(specialist)
    except SupportScoutError as exc:
        return json.dumps({"delegated": False, "reason": str(exc)})

    try:
        summary = runner(kernel)
    except SupportScoutError as exc:
        return _handle_delegation_failure(kernel, specialist, tool_name, exc, str(exc))
    except Exception as exc:  # noqa: BLE001 - never let a specialist kill the run silently
        return _handle_delegation_failure(
            kernel, specialist, tool_name, exc, f"The {specialist} specialist failed: {type(exc).__name__}"
        )

    kernel.note_delegation_success(specialist)
    kernel.record_delegation(specialist, tool_name, status="succeeded")
    return json.dumps(
        {
            "delegated": True,
            "specialist": specialist,
            "current_state": kernel.state.current_state.value,
            "summary": summary,
        },
        default=str,
    )


def _handle_delegation_failure(
    kernel: WorkflowKernel,
    specialist: str,
    tool_name: str,
    exc: Exception,
    reason: str,
) -> str:
    """Record one delegation failure and escalate once the streak crosses the limit.

    The exception is logged to the error audit here, exactly as the previous
    implementation did -- only the escalation-on-streak behaviour is new.
    """
    kernel.logger.error(exc, agent_name=specialist)
    kernel.record_delegation(specialist, tool_name, status="failed")
    failure_count = kernel.note_delegation_failure(specialist)

    if failure_count >= kernel.max_delegation_failures:
        kernel.escalate(
            EscalationReason.AGENT_EXECUTION_FAILURE,
            summary=(
                f"The {specialist} agent failed {failure_count} times in a row "
                f"and could not produce a valid result."
            ),
            recommended_action=(
                f"Review the ticket manually; the {specialist} step could not be "
                "completed automatically."
            ),
        )
        return json.dumps(
            {
                "delegated": False,
                "reason": reason,
                "escalated": True,
                "current_state": kernel.state.current_state.value,
            }
        )

    return json.dumps({"delegated": False, "reason": reason})


def build_orchestration_tools(
    kernel: WorkflowKernel,
    *,
    triage: SpecialistCallable,
    research: SpecialistCallable,
    support: SpecialistCallable,
    qa: SpecialistCallable,
    documentation: SpecialistCallable,
) -> list[Any]:
    """Create the orchestrator's tool set bound to one run's kernel and specialists."""

    @tool
    def inspect_workflow_state(reason: str) -> str:
        """Read the authoritative workflow state, completed delegations and evidence.

        This is the only trustworthy source of workflow state. Never assume the state
        from memory; read it here and act on what it says.

        Args:
            reason: A short note on why the state is being inspected.
        """
        del reason
        return json.dumps(kernel.snapshot())

    @tool
    def delegate_to_triage(reason: str) -> str:
        """Hand the ticket to the Triage Agent for classification and sentiment.

        Valid only when current_state is "validated". On success the workflow advances
        to "triaged", or terminates as "escalated" if a safety rule fires.

        Args:
            reason: A short note on why triage is the correct next step.
        """
        del reason
        return _delegate(kernel, "triage", "delegate_to_triage", triage)

    @tool
    def delegate_to_research(reason: str) -> str:
        """Hand the ticket to the Research Agent to gather public troubleshooting guidance.

        Valid only when current_state is "triaged". On success the workflow advances to
        "researched", or terminates as "escalated" if evidence is insufficient or
        conflicting.

        Args:
            reason: A short note on why research is the correct next step.
        """
        del reason
        return _delegate(kernel, "research", "delegate_to_research", research)

    @tool
    def delegate_to_support(reason: str) -> str:
        """Hand the ticket to the Support Specialist Agent to draft the customer response.

        Valid when current_state is "researched", or "qa_revision_requested" when QA has
        asked for a revision. On success the workflow advances to "drafted".

        Args:
            reason: A short note on why drafting is the correct next step.
        """
        del reason
        return _delegate(kernel, "support", "delegate_to_support", support)

    @tool
    def delegate_to_qa(reason: str) -> str:
        """Hand the draft to the QA Agent for deterministic verification.

        Valid only when current_state is "drafted". QA may approve, request one bounded
        revision, or escalate.

        Args:
            reason: A short note on why QA review is the correct next step.
        """
        del reason
        return _delegate(kernel, "qa", "delegate_to_qa", qa)

    @tool
    def delegate_to_documentation(reason: str) -> str:
        """Hand the approved draft to the Documentation Agent for a reusable article.

        Valid only when current_state is "qa_approved". On success the workflow advances
        to "documented".

        Args:
            reason: A short note on why documentation is the correct next step.
        """
        del reason
        return _delegate(kernel, "documentation", "delegate_to_documentation", documentation)

    @tool
    def finalize_workflow(reason: str) -> str:
        """Close the workflow once it is documented, or once it has escalated.

        Args:
            reason: A short note on why the workflow is complete.
        """
        del reason
        try:
            state = kernel.finalize()
        except WorkflowError as exc:
            return json.dumps({"finalized": False, "reason": str(exc)})
        return json.dumps({"finalized": True, "current_state": state.value})

    return [
        inspect_workflow_state,
        delegate_to_triage,
        delegate_to_research,
        delegate_to_support,
        delegate_to_qa,
        delegate_to_documentation,
        finalize_workflow,
    ]
