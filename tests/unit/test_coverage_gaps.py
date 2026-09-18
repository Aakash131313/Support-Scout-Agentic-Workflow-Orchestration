"""Direct tests for components otherwise only exercised indirectly.

Exception categories, trace/audit schema shapes, the stdout logging filter and the
`chat` CLI loop are all reachable through the workflow, but a failure in them would
surface as a confusing error somewhere else. These tests pin them down directly.
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone

import pytest

from support_scout import exceptions as exc
from support_scout.logging_config import RedactingFilter, configure_logging
from support_scout.main import EXIT_COMPLETED, command_chat, run_cli
from support_scout.schemas import (
    AgentRunRecord,
    AuditEvent,
    DelegationRecord,
    EscalationDecision,
    EscalationReason,
    HumanApprovalDecision,
    InteractionSummary,
    OperationalEvidence,
    StructuredError,
    SupportDomain,
    ToolCallRecord,
    WorkflowState,
    WorkflowStatus,
)
from tests.unit.test_cli import StubOrchestrator


# --------------------------------------------------------------------------------------
# Exception hierarchy
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "error_class,category,retryable",
    [
        (exc.ConfigurationError, "configuration_error", False),
        (exc.FileOutputError, "file_output_error", False),
        (exc.ModelAuthenticationError, "model_authentication_error", False),
        (exc.ModelTimeoutError, "model_timeout_error", True),
        (exc.ModelTransportError, "model_transport_error", True),
        (exc.ModelResponseError, "model_response_error", True),
        (exc.SearchAuthenticationError, "search_authentication_error", False),
        (exc.SearchTimeoutError, "search_timeout_error", True),
        (exc.SearchResponseError, "search_response_error", False),
        (exc.ScrapeTimeoutError, "scrape_timeout_error", True),
        (exc.ScrapeSizeError, "scrape_size_error", False),
        (exc.ScrapeContentTypeError, "scrape_content_type_error", False),
        (exc.UnsafeURLError, "unsafe_url_error", False),
        (exc.SupportDataClientError, "support_data_client_error", True),
        (exc.SupportDataNotFound, "support_data_not_found", False),
        (exc.WorkflowError, "workflow_error", False),
        (exc.ExecutionBudgetExceeded, "execution_budget_exceeded", False),
    ],
)
def test_exception_categories_and_retryability(error_class, category, retryable):
    """The error audit records these fields, so they must be correct."""
    error = error_class("message")
    assert error.category == category
    assert error.retryable is retryable
    assert isinstance(error, exc.SupportScoutError)


def test_not_found_is_not_retryable_despite_its_parent():
    """A missing record will not appear on retry; a transport failure might."""
    assert exc.SupportDataClientError.retryable is True
    assert exc.SupportDataNotFound.retryable is False
    assert issubclass(exc.SupportDataNotFound, exc.SupportDataClientError)


# --------------------------------------------------------------------------------------
# Logging filter
# --------------------------------------------------------------------------------------
def test_redacting_filter_scrubs_a_log_record():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="connecting with api_key: sk-abcdef1234567890",
        args=(),
        exc_info=None,
    )
    assert RedactingFilter().filter(record) is True
    assert "sk-abcdef" not in record.msg
    assert "[REDACTED]" in record.msg


def test_configure_logging_is_idempotent():
    configure_logging()
    root = logging.getLogger()
    installed = [h for h in root.handlers if getattr(h, "_support_scout", False)]
    configure_logging()
    still_installed = [h for h in root.handlers if getattr(h, "_support_scout", False)]
    assert len(installed) == len(still_installed) == 1


def test_configured_handler_redacts_stdout(capsys):
    configure_logging()
    logging.getLogger("test.redaction").warning("token=abcdef1234567890")
    captured = capsys.readouterr()
    assert "abcdef1234567890" not in (captured.out + captured.err)


# --------------------------------------------------------------------------------------
# Trace, audit and summary contracts
# --------------------------------------------------------------------------------------
def test_tool_call_record_serializes():
    record = ToolCallRecord(
        run_id="run-1",
        agent_name="support_agent",
        step_number=2,
        tool_name="get_order_status",
        tool_arguments={"order_id": "ORD-1001"},
        status="ok",
    )
    assert json.loads(record.model_dump_json())["tool_name"] == "get_order_status"


def test_agent_run_record_defaults_to_started():
    record = AgentRunRecord(
        run_id="run-1", agent_name="qa_agent", started_at=datetime.now(timezone.utc)
    )
    assert record.status == "started"
    assert record.step_count == 0


def test_delegation_record_captures_resulting_state():
    record = DelegationRecord(
        run_id="run-1",
        specialist="triage",
        tool_name="delegate_to_triage",
        requested_at=datetime.now(timezone.utc),
        status="succeeded",
        resulting_state=WorkflowStatus.TRIAGED,
    )
    assert record.resulting_state == WorkflowStatus.TRIAGED


def test_structured_error_shape_matches_the_audit_contract():
    error = StructuredError(
        run_id="run-1",
        error_category="model_timeout_error",
        agent_name="research_agent",
        tool_name="web_search",
        retryable=True,
        safe_message="Model request timed out",
        occurred_at=datetime.now(timezone.utc),
    )
    payload = json.loads(error.model_dump_json())
    assert set(payload) == {
        "run_id",
        "error_category",
        "agent_name",
        "tool_name",
        "retryable",
        "safe_message",
        "occurred_at",
    }


def test_human_approval_decision_records_the_approver():
    decision = HumanApprovalDecision(
        requested_action="issue refund",
        reason_code=EscalationReason.FINANCIAL_AUTHORIZATION,
        approved=False,
        approver="unattended-policy",
        decided_at=datetime.now(timezone.utc),
    )
    assert decision.approved is False
    assert decision.approver == "unattended-policy"


def test_audit_event_accepts_arbitrary_detail():
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc),
        step="transition",
        status="succeeded",
        details={"from": "validated", "to": "triaged"},
    )
    assert event.details["to"] == "triaged"


def test_operational_evidence_requires_the_op_prefix():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OperationalEvidence(
            evidence_id="EV-001",
            source_system="support-data-api",
            record_type="order",
            record_id="ORD-1001",
            retrieved_at=datetime.now(timezone.utc),
            facts={},
        )


def test_interaction_summary_defaults_are_safe():
    summary = InteractionSummary(
        ticket_id="TKT-1",
        run_id="run-1",
        domain=SupportDomain.UNCERTAIN,
        workflow_status=WorkflowStatus.ESCALATED,
    )
    assert summary.escalation == EscalationDecision()
    assert summary.revision_count == 0
    assert summary.delegations == []


def test_workflow_state_rejects_an_invalid_assignment():
    """validate_assignment catches malformed mutation where it happens."""
    from pydantic import ValidationError

    from tests.conftest import make_ticket

    state = WorkflowState(
        run_id="run-1", current_state=WorkflowStatus.RECEIVED, ticket=make_ticket("hello")
    )
    with pytest.raises(ValidationError):
        state.current_state = "not_a_real_state"


# --------------------------------------------------------------------------------------
# Chat command
# --------------------------------------------------------------------------------------
class ChatHarness:
    """Feeds scripted lines to the chat loop."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __call__(self, _prompt=""):
        try:
            return next(self.lines)
        except StopIteration as stop:
            raise EOFError from stop


def run_chat(monkeypatch, lines, orchestrator):
    monkeypatch.setattr("builtins.input", ChatHarness(lines))
    args = type("Args", (), {"output": None})()
    return command_chat(args, orchestrator_factory=lambda _output: orchestrator)


def test_chat_exits_on_quit(monkeypatch):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    assert run_chat(monkeypatch, ["quit"], orchestrator) == EXIT_COMPLETED
    assert orchestrator.ran == []


def test_chat_help_does_not_run_a_ticket(monkeypatch, capsys):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    run_chat(monkeypatch, ["help", "quit"], orchestrator)
    assert orchestrator.ran == []
    assert "order tracking" in capsys.readouterr().out.casefold()


def test_chat_ignores_blank_input(monkeypatch):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    run_chat(monkeypatch, ["", "   ", "quit"], orchestrator)
    assert orchestrator.ran == []


def test_chat_runs_a_ticket_per_message(monkeypatch):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    run_chat(monkeypatch, ["where is my order", "quit"], orchestrator)
    assert len(orchestrator.ran) == 1
    assert orchestrator.ran[0].startswith("TKT-")


def test_chat_reports_an_escalation(monkeypatch, capsys):
    orchestrator = StubOrchestrator(
        WorkflowStatus.ESCALATED, EscalationReason.FINANCIAL_AUTHORIZATION
    )
    run_chat(monkeypatch, ["please approve a refund", "quit"], orchestrator)
    assert "financial_authorization" in capsys.readouterr().out


def test_chat_handles_end_of_input(monkeypatch):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    assert run_chat(monkeypatch, [], orchestrator) == EXIT_COMPLETED


def test_chat_generates_unique_ticket_ids(monkeypatch):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    run_chat(monkeypatch, ["first question", "second question", "quit"], orchestrator)
    assert len(set(orchestrator.ran)) == 2
