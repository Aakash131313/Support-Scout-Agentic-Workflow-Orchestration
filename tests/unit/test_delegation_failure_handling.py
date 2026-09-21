"""Tests for the deterministic delegation-failure guard.

Regression tests for TKT-DEMO-005: the Support Agent called smolagents' built-in
final_answer instead of submit_support_draft when every operational lookup returned
available=false, causing the orchestrator to retry delegate_to_support five times
before exhausting its own step budget and failing with no escalation reason at all.

These tests exercise the fix at the kernel/orchestration_tools level: a specialist
that fails repeatedly must be escalated deterministically after a bounded number of
attempts, with a specific named reason, regardless of what the orchestrator model
does or does not do about it.
"""
from __future__ import annotations

import json

from support_scout.exceptions import WorkflowError
from support_scout.schemas import EscalationReason, WorkflowState, WorkflowStatus
from support_scout.tools.orchestration_tools import build_orchestration_tools
from support_scout.workflow.kernel import WorkflowKernel
from tests.conftest import make_ticket


class _AlwaysFailingSpecialist(Exception):
    """Stand-in for AgentExecutionError: the specialist never submits."""


def _noop(_kernel):
    return {}


def _build_kernel(run_logger, *, max_delegation_failures: int = 2) -> WorkflowKernel:
    state = WorkflowState(
        run_id="test-run",
        current_state=WorkflowStatus.RESEARCHED,
        ticket=make_ticket("Can you check on my order please."),
    )
    return WorkflowKernel(
        state, logger=run_logger, max_delegation_failures=max_delegation_failures
    )


def test_escalates_after_the_configured_number_of_consecutive_failures(run_logger):
    """Regression: the real failure escalated on the 5th retry. It must now escalate
    on the 2nd, with a specific reason, rather than retrying until a budget elsewhere
    is exhausted."""
    kernel = _build_kernel(run_logger, max_delegation_failures=2)

    def always_fails(_kernel):
        raise _AlwaysFailingSpecialist("Support Agent did not submit a draft")

    tools = build_orchestration_tools(
        kernel, triage=_noop, research=_noop, support=always_fails, qa=_noop, documentation=_noop
    )
    delegate_to_support = {tool.name: tool for tool in tools}["delegate_to_support"]

    first = json.loads(delegate_to_support(reason="draft the response"))
    assert first["delegated"] is False
    assert kernel.state.current_state == WorkflowStatus.RESEARCHED  # not yet escalated

    second = json.loads(delegate_to_support(reason="retry"))
    assert second["delegated"] is False
    assert second.get("escalated") is True
    assert kernel.state.current_state == WorkflowStatus.ESCALATED
    assert kernel.state.escalation.reason_code == EscalationReason.AGENT_EXECUTION_FAILURE


def test_a_third_attempt_is_blocked_by_state_validation_not_retried(run_logger):
    """Once escalated, the workflow is terminal; a further attempt must fail fast
    at the state-validation step rather than invoking the specialist again."""
    kernel = _build_kernel(run_logger, max_delegation_failures=2)

    call_count = {"n": 0}

    def always_fails(_kernel):
        call_count["n"] += 1
        raise _AlwaysFailingSpecialist("Support Agent did not submit a draft")

    tools = build_orchestration_tools(
        kernel, triage=_noop, research=_noop, support=always_fails, qa=_noop, documentation=_noop
    )
    delegate_to_support = {tool.name: tool for tool in tools}["delegate_to_support"]

    delegate_to_support(reason="1")
    delegate_to_support(reason="2")  # escalates here
    assert call_count["n"] == 2

    third = json.loads(delegate_to_support(reason="3"))
    assert third["delegated"] is False
    assert call_count["n"] == 2, "the specialist must not run a third time after escalation"


def test_every_failure_is_still_recorded_in_the_error_audit(run_logger):
    """The escalation guard must not silently drop error auditing."""
    kernel = _build_kernel(run_logger, max_delegation_failures=2)

    def always_fails(_kernel):
        raise _AlwaysFailingSpecialist("Support Agent did not submit a draft")

    tools = build_orchestration_tools(
        kernel, triage=_noop, research=_noop, support=always_fails, qa=_noop, documentation=_noop
    )
    delegate_to_support = {tool.name: tool for tool in tools}["delegate_to_support"]

    delegate_to_support(reason="1")
    delegate_to_support(reason="2")

    assert len(run_logger.errors) == 2
    assert all(error.agent_name == "support" for error in run_logger.errors)


def test_success_resets_the_failure_streak(run_logger):
    """A specialist that fails once, then succeeds, must not carry a stale count
    into a later, unrelated failure (e.g. during a QA-requested revision)."""
    kernel = _build_kernel(run_logger, max_delegation_failures=2)

    attempts = {"n": 0}

    def fails_once_then_succeeds(_kernel):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _AlwaysFailingSpecialist("Support Agent did not submit a draft")
        return {"ok": True}

    tools = build_orchestration_tools(
        kernel,
        triage=_noop,
        research=_noop,
        support=fails_once_then_succeeds,
        qa=_noop,
        documentation=_noop,
    )
    delegate_to_support = {tool.name: tool for tool in tools}["delegate_to_support"]

    first = json.loads(delegate_to_support(reason="1"))
    assert first["delegated"] is False

    second = json.loads(delegate_to_support(reason="2"))
    assert second["delegated"] is True
    assert kernel.delegation_failure_counts.get("support", 0) == 0


def test_failure_counts_are_independent_per_specialist(run_logger):
    """One specialist's failures must not affect another's threshold."""
    kernel = _build_kernel(run_logger, max_delegation_failures=2)
    kernel.note_delegation_failure("support")
    kernel.note_delegation_failure("qa")
    kernel.note_delegation_failure("qa")

    assert kernel.delegation_failure_counts == {"support": 1, "qa": 2}


def test_agent_execution_failure_is_a_valid_escalation_reason():
    """The new reason must be a real member of the approved enum, not a bare string."""
    assert EscalationReason.AGENT_EXECUTION_FAILURE.value == "agent_execution_failure"
    assert EscalationReason.AGENT_EXECUTION_FAILURE in set(EscalationReason)


def test_max_delegation_failures_is_configurable(run_logger):
    """A threshold of 1 must escalate on the very first failure."""
    kernel = _build_kernel(run_logger, max_delegation_failures=1)

    def always_fails(_kernel):
        raise _AlwaysFailingSpecialist("boom")

    tools = build_orchestration_tools(
        kernel, triage=_noop, research=_noop, support=always_fails, qa=_noop, documentation=_noop
    )
    delegate_to_support = {tool.name: tool for tool in tools}["delegate_to_support"]

    result = json.loads(delegate_to_support(reason="1"))
    assert result.get("escalated") is True
    assert kernel.state.current_state == WorkflowStatus.ESCALATED
