"""Workflow kernel tests.

These cover the three defects the refactor set out to fix:
  * a mandatory escalation must stop the workflow, not be recorded and ignored;
  * an escalated run must be finalizable so artifacts are written;
  * a QA escalation must keep its specific reason rather than collapsing to qa_failure.
"""
from __future__ import annotations

import pytest

from support_scout.exceptions import ExecutionBudgetExceeded, WorkflowError
from support_scout.hitl import AutoApproveGate, AutoDenyGate
from support_scout.schemas import (
    EscalationDecision,
    ScrapedEvidence,
    EscalationReason,
    QADecision,
    QAResult,
    SentimentAssessment,
    SentimentIntensity,
    SentimentLabel,
    SupportDomain,
    SupportDraft,
    TicketClassification,
    TroubleshootingArticle,
    Urgency,
    WorkflowState,
    WorkflowStatus,
)
from support_scout.workflow.kernel import WorkflowKernel
from tests.conftest import make_ticket


def build_kernel(run_logger, *, gate=None, max_revisions: int = 1) -> WorkflowKernel:
    state = WorkflowState(
        run_id="test-run",
        current_state=WorkflowStatus.RECEIVED,
        ticket=make_ticket("My parcel is late."),
    )
    return WorkflowKernel(
        state,
        logger=run_logger,
        approval_gate=gate or AutoDenyGate(),
        max_revisions=max_revisions,
    )


def _classification(domain=SupportDomain.ORDER_TRACKING_DELIVERY, confidence=0.95):
    return TicketClassification(
        domain=domain, intent="locate parcel", urgency=Urgency.MEDIUM, confidence=confidence
    )


def _sentiment():
    return SentimentAssessment(
        label=SentimentLabel.NEUTRAL, intensity=SentimentIntensity.MILD, rationale_summary="n/a"
    )


def _evidence():
    return ScrapedEvidence(
        evidence_id="EV-001",
        source_url="https://help.example.com/guide",
        title="Guide",
        retrieved_at="2026-09-17T12:00:00Z",
        content="General tracking guidance.",
        content_hash="abcdef1234",
    )


def _draft():
    return SupportDraft(
        issue_summary="Late parcel.",
        customer_response="Your parcel is in transit.",
        troubleshooting_steps=["Check the carrier site."],
        evidence_ids=["EV-001"],
    )


def _article():
    return TroubleshootingArticle(
        title="Tracking guidance",
        body_markdown="# Tracking guidance\n\nTracking pauses between scans.",
        source_evidence_ids=["EV-001"],
    )


# --------------------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------------------
def test_valid_transition_is_accepted(run_logger):
    kernel = build_kernel(run_logger)
    assert kernel.transition(WorkflowStatus.VALIDATED) == WorkflowStatus.VALIDATED


def test_skipping_a_state_is_rejected(run_logger):
    kernel = build_kernel(run_logger)
    with pytest.raises(WorkflowError):
        kernel.transition(WorkflowStatus.DRAFTED)


def test_terminal_state_cannot_transition(run_logger):
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)
    kernel.escalate(EscalationReason.UNSUPPORTED_DOMAIN)
    with pytest.raises(WorkflowError):
        kernel.transition(WorkflowStatus.TRIAGED)


# --------------------------------------------------------------------------------------
# Escalation actually stops the workflow
# --------------------------------------------------------------------------------------
def test_mandatory_escalation_stops_triage_from_advancing(run_logger):
    """The previous implementation advanced to 'triaged' regardless. This is the fix."""
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)

    kernel.apply_triage(
        classification=_classification(),
        sentiment=_sentiment(),
        escalation=EscalationDecision(
            required=True, reason_code=EscalationReason.FINANCIAL_AUTHORIZATION
        ),
    )

    assert kernel.state.current_state == WorkflowStatus.ESCALATED
    assert kernel.state.escalation.reason_code == EscalationReason.FINANCIAL_AUTHORIZATION


def test_research_delegation_is_rejected_after_escalation(run_logger):
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)
    kernel.apply_triage(
        classification=_classification(),
        sentiment=_sentiment(),
        escalation=EscalationDecision(
            required=True, reason_code=EscalationReason.ACCOUNT_COMPROMISE
        ),
    )
    with pytest.raises(WorkflowError):
        kernel.require_state_for("research")


def test_escalated_run_can_finalize(run_logger):
    """Previously an escalated run raised instead of finalizing, so nothing was written."""
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)
    kernel.escalate(EscalationReason.UNSUPPORTED_DOMAIN)

    assert kernel.finalize() == WorkflowStatus.ESCALATED
    assert kernel.finalized is True


# --------------------------------------------------------------------------------------
# Human in the loop
# --------------------------------------------------------------------------------------
def test_denied_restricted_action_escalates(run_logger):
    kernel = build_kernel(run_logger, gate=AutoDenyGate())
    kernel.transition(WorkflowStatus.VALIDATED)

    kernel.apply_triage(
        classification=_classification(),
        sentiment=_sentiment(),
        escalation=EscalationDecision(
            required=True, reason_code=EscalationReason.FINANCIAL_AUTHORIZATION
        ),
    )

    assert kernel.state.current_state == WorkflowStatus.ESCALATED
    assert kernel.state.human_approval is not None
    assert kernel.state.human_approval.approved is False


def test_approved_restricted_action_continues(run_logger):
    kernel = build_kernel(run_logger, gate=AutoApproveGate())
    kernel.transition(WorkflowStatus.VALIDATED)

    kernel.apply_triage(
        classification=_classification(),
        sentiment=_sentiment(),
        escalation=EscalationDecision(
            required=True, reason_code=EscalationReason.POLICY_EXCEPTION
        ),
    )

    assert kernel.state.current_state == WorkflowStatus.TRIAGED
    assert kernel.state.human_approval.approved is True


def test_non_restricted_escalation_does_not_prompt(run_logger):
    """Only restricted actions interrupt the customer-facing flow."""
    kernel = build_kernel(run_logger, gate=AutoApproveGate())
    kernel.transition(WorkflowStatus.VALIDATED)

    kernel.apply_triage(
        classification=_classification(),
        sentiment=_sentiment(),
        escalation=EscalationDecision(
            required=True, reason_code=EscalationReason.UNSUPPORTED_DOMAIN
        ),
    )

    assert kernel.state.current_state == WorkflowStatus.ESCALATED
    assert kernel.state.human_approval is None


# --------------------------------------------------------------------------------------
# Evidence gates
# --------------------------------------------------------------------------------------
def test_insufficient_evidence_escalates(run_logger):
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)
    kernel.apply_triage(
        classification=_classification(), sentiment=_sentiment(), escalation=EscalationDecision()
    )

    kernel.apply_research(search_results=[], evidence=[], insufficient=True, conflicting=False)

    assert kernel.state.current_state == WorkflowStatus.ESCALATED
    assert kernel.state.escalation.reason_code == EscalationReason.INSUFFICIENT_EVIDENCE


def test_conflicting_evidence_escalates(run_logger):
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)
    kernel.apply_triage(
        classification=_classification(), sentiment=_sentiment(), escalation=EscalationDecision()
    )

    kernel.apply_research(search_results=[], evidence=[], insufficient=False, conflicting=True)

    assert kernel.state.escalation.reason_code == EscalationReason.CONFLICTING_EVIDENCE


# --------------------------------------------------------------------------------------
# QA decisions, including the bounded revision loop
# --------------------------------------------------------------------------------------
def _advance_to_drafted(kernel: WorkflowKernel) -> None:
    kernel.transition(WorkflowStatus.VALIDATED)
    kernel.apply_triage(
        classification=_classification(), sentiment=_sentiment(), escalation=EscalationDecision()
    )
    kernel.apply_research(
        search_results=[], evidence=[_evidence()], insufficient=False, conflicting=False
    )
    kernel.apply_support(draft=_draft(), operational_evidence=[])


def test_qa_approve_advances(run_logger):
    kernel = build_kernel(run_logger)
    _advance_to_drafted(kernel)
    kernel.apply_qa(result=QAResult(decision=QADecision.APPROVE))
    assert kernel.state.current_state == WorkflowStatus.QA_APPROVED


def test_qa_revise_enters_revision_state(run_logger):
    kernel = build_kernel(run_logger, max_revisions=1)
    _advance_to_drafted(kernel)
    kernel.apply_qa(
        result=QAResult(decision=QADecision.REVISE, revision_instructions=["Cite the evidence."])
    )
    assert kernel.state.current_state == WorkflowStatus.QA_REVISION_REQUESTED
    assert kernel.state.revision_count == 1


def test_support_may_redraft_from_revision_state(run_logger):
    """The revision loop was unreachable before: no path existed out of this state."""
    kernel = build_kernel(run_logger, max_revisions=1)
    _advance_to_drafted(kernel)
    kernel.apply_qa(
        result=QAResult(decision=QADecision.REVISE, revision_instructions=["Cite the evidence."])
    )
    kernel.require_state_for("support")
    kernel.apply_support(draft=_draft(), operational_evidence=[])
    assert kernel.state.current_state == WorkflowStatus.DRAFTED


def test_exceeding_revision_limit_escalates(run_logger):
    kernel = build_kernel(run_logger, max_revisions=1)
    _advance_to_drafted(kernel)
    kernel.apply_qa(result=QAResult(decision=QADecision.REVISE, revision_instructions=["Fix."]))
    kernel.apply_support(draft=_draft(), operational_evidence=[])
    kernel.apply_qa(result=QAResult(decision=QADecision.REVISE, revision_instructions=["Fix."]))

    assert kernel.state.current_state == WorkflowStatus.ESCALATED
    assert kernel.state.escalation.reason_code == EscalationReason.REVISION_LIMIT_EXCEEDED


def test_qa_escalation_preserves_specific_reason(run_logger):
    """Previously every QA escalation was recorded as qa_failure."""
    kernel = build_kernel(run_logger)
    _advance_to_drafted(kernel)
    kernel.apply_qa(
        result=QAResult(
            decision=QADecision.ESCALATE,
            escalation_reason=EscalationReason.SENSITIVE_DATA,
        )
    )
    assert kernel.state.escalation.reason_code == EscalationReason.SENSITIVE_DATA


# --------------------------------------------------------------------------------------
# Completion and budgets
# --------------------------------------------------------------------------------------
def test_finalize_requires_documentation(run_logger):
    kernel = build_kernel(run_logger)
    _advance_to_drafted(kernel)
    kernel.apply_qa(result=QAResult(decision=QADecision.APPROVE))
    with pytest.raises(WorkflowError):
        kernel.finalize()


def test_full_happy_path_completes(run_logger):
    kernel = build_kernel(run_logger)
    _advance_to_drafted(kernel)
    kernel.apply_qa(result=QAResult(decision=QADecision.APPROVE))
    kernel.apply_documentation(article=_article())
    assert kernel.finalize() == WorkflowStatus.COMPLETED


def test_tool_call_budget_is_enforced(run_logger):
    kernel = build_kernel(run_logger)
    kernel.max_total_tool_calls = 2
    kernel.count_tool_call("a")
    kernel.count_tool_call("b")
    with pytest.raises(ExecutionBudgetExceeded):
        kernel.count_tool_call("c")


def test_snapshot_exposes_state_without_secrets(run_logger):
    kernel = build_kernel(run_logger)
    kernel.transition(WorkflowStatus.VALIDATED)
    snapshot = kernel.snapshot()
    assert snapshot["current_state"] == "validated"
    assert "customer_message" not in snapshot
