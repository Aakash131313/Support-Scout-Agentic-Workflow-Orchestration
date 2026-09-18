"""Logging, redaction, error auditing, human-in-the-loop, artifacts and schemas."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from support_scout.artifacts import ArtifactWriter, build_interaction_summary, write_run_artifacts
from support_scout.exceptions import FileOutputError, ModelTimeoutError, SupportDataNotFound
from support_scout.hitl import (
    AutoApproveGate,
    AutoDenyGate,
    InteractiveApprovalGate,
    build_gate,
    requires_human_approval,
)
from support_scout.logging_config import RunLogger, redact
from support_scout.schemas import (
    EscalationDecision,
    EscalationReason,
    SupportTicket,
    WorkflowState,
    WorkflowStatus,
)
from tests.conftest import make_ticket


# --------------------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [
        "api_key: sk-abcdef1234567890",
        "password=hunter2",
        "Authorization: Bearer abcdefghijklmnop",
        "card 4111 1111 1111 1111",
        "ssn 123-45-6789",
    ],
)
def test_secrets_are_redacted(value):
    assert "[REDACTED]" in redact(value)


def test_blocked_keys_are_never_recorded():
    payload = redact({"customer_message": "my password is hunter2", "domain": "returns_refunds"})
    assert payload["customer_message"] == "[REDACTED]"
    assert payload["domain"] == "returns_refunds"


def test_long_values_are_truncated():
    assert "[truncated]" in redact("x" * 5000)


def test_nested_structures_are_redacted():
    payload = redact({"outer": [{"token": "abc", "safe": 1}]})
    assert payload["outer"][0]["token"] == "[REDACTED]"
    assert payload["outer"][0]["safe"] == 1


# --------------------------------------------------------------------------------------
# Run logger
# --------------------------------------------------------------------------------------
def test_trace_is_written_as_jsonl(tmp_path):
    logger = RunLogger("run-1", log_directory=tmp_path, echo=False)
    logger.tool_called("support_agent", "get_order_status", {"order_id": "ORD-1001"})
    logger.tool_result("support_agent", "get_order_status", status="ok")

    lines = logger.trace_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["tool_name"] == "get_order_status"


def test_errors_are_appended_to_a_shared_audit(tmp_path):
    logger = RunLogger("run-1", log_directory=tmp_path, echo=False)
    logger.error(ModelTimeoutError("Model request timed out"), agent_name="triage_agent")
    logger.error(SupportDataNotFound("Operational record was not found"), tool_name="get_order_status")

    lines = logger.errors_path.read_text().strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["error_category"] == "model_timeout_error"
    assert first["retryable"] is True
    assert first["agent_name"] == "triage_agent"

    second = json.loads(lines[1])
    assert second["retryable"] is False
    assert second["tool_name"] == "get_order_status"


def test_error_audit_survives_across_runs(tmp_path):
    RunLogger("run-1", log_directory=tmp_path, echo=False).error(ModelTimeoutError("a"))
    RunLogger("run-2", log_directory=tmp_path, echo=False).error(ModelTimeoutError("b"))
    lines = (tmp_path / "errors.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2


def test_insight_is_recorded_without_printing(tmp_path, capsys):
    logger = RunLogger("run-1", log_directory=tmp_path, echo=False)
    logger.insight("triage", {"Domain": "returns_refunds"})
    assert capsys.readouterr().out == ""
    assert any(event["event"] == "insight" for event in logger.events)


def test_insight_secrets_are_redacted_before_printing(tmp_path, capsys):
    logger = RunLogger("run-1", log_directory=tmp_path, echo=True)
    logger.insight("debug", {"Detail": "api_key: sk-abcdef1234567890"})
    assert "sk-abcdef" not in capsys.readouterr().out


# --------------------------------------------------------------------------------------
# Human in the loop
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reason,expected",
    [
        (EscalationReason.FINANCIAL_AUTHORIZATION, True),
        (EscalationReason.POLICY_EXCEPTION, True),
        (EscalationReason.ACCOUNT_COMPROMISE, True),
        (EscalationReason.UNSUPPORTED_DOMAIN, False),
        (EscalationReason.LOW_CONFIDENCE, False),
        (EscalationReason.INSUFFICIENT_EVIDENCE, False),
    ],
)
def test_only_restricted_actions_require_approval(reason, expected):
    """The customer-facing flow is interrupted once, and only for a restricted action."""
    assert requires_human_approval(reason) is expected


def test_unattended_gate_denies_by_default():
    decision = AutoDenyGate().request(
        action="issue refund", reason=EscalationReason.FINANCIAL_AUTHORIZATION, context=""
    )
    assert decision.approved is False


def test_auto_approve_gate_approves():
    decision = AutoApproveGate().request(
        action="issue refund", reason=EscalationReason.FINANCIAL_AUTHORIZATION, context=""
    )
    assert decision.approved is True


@pytest.mark.parametrize("answer,expected", [("y", True), ("yes", True), ("n", False), ("", False)])
def test_interactive_gate_reads_the_operator_answer(answer, expected):
    import io

    gate = InteractiveApprovalGate(stream=io.StringIO(), prompt_input=lambda _: answer)
    decision = gate.request(
        action="issue refund", reason=EscalationReason.FINANCIAL_AUTHORIZATION, context="ctx"
    )
    assert decision.approved is expected


def test_build_gate_selects_the_right_implementation():
    assert isinstance(build_gate(require_approval=True, auto_approve=True, interactive=True), AutoApproveGate)
    assert isinstance(build_gate(require_approval=True, auto_approve=False, interactive=True), InteractiveApprovalGate)
    assert isinstance(build_gate(require_approval=True, auto_approve=False, interactive=False), AutoDenyGate)


# --------------------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------------------
def _state(status: WorkflowStatus, **overrides) -> WorkflowState:
    payload = {
        "run_id": "run-1",
        "current_state": status,
        "ticket": make_ticket("My parcel is late."),
    }
    payload.update(overrides)
    return WorkflowState.model_validate(payload)


def test_path_traversal_ticket_id_is_rejected(tmp_path):
    """AT-015."""
    writer = ArtifactWriter(tmp_path)
    with pytest.raises(FileOutputError):
        writer.ticket_directory("../../etc/passwd")


def test_invalid_filename_is_rejected(tmp_path):
    writer = ArtifactWriter(tmp_path)
    with pytest.raises(FileOutputError):
        writer.write_json("TKT-1", "../escape.json", {})


def test_json_is_stable_and_sorted(tmp_path):
    writer = ArtifactWriter(tmp_path)
    path = writer.write_json("TKT-1", "data.json", {"b": 2, "a": 1})
    assert path.read_text() == '{\n  "a": 1,\n  "b": 2\n}\n'


def test_escalated_run_still_writes_every_artifact(tmp_path):
    """The escalation path previously wrote nothing at all."""
    writer = ArtifactWriter(tmp_path)
    state = _state(
        WorkflowStatus.ESCALATED,
        escalation=EscalationDecision(
            required=True,
            reason_code=EscalationReason.FINANCIAL_AUTHORIZATION,
            summary="Needs a human.",
        ),
    )

    directory = write_run_artifacts(writer, state)
    written = {path.name for path in directory.iterdir()}

    assert {
        "interaction_summary.json",
        "customer_response.md",
        "troubleshooting_article.md",
        "sources.json",
        "operational_sources.json",
        "audit_log.json",
        "agent_trace.json",
        "escalation.json",
    } <= written


def test_escalated_response_makes_no_promise(tmp_path):
    writer = ArtifactWriter(tmp_path)
    state = _state(
        WorkflowStatus.ESCALATED,
        escalation=EscalationDecision(required=True, reason_code=EscalationReason.FINANCIAL_AUTHORIZATION),
    )
    directory = write_run_artifacts(writer, state)
    response = (directory / "customer_response.md").read_text()
    assert "No refund, payment, account or order change has been made" in response


def test_interaction_summary_records_the_run(tmp_path):
    summary = build_interaction_summary(_state(WorkflowStatus.ESCALATED))
    assert summary.ticket_id == "TKT-TEST-001"
    assert summary.run_id == "run-1"


# --------------------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------------------
def test_valid_ticket_is_accepted():
    ticket = SupportTicket(
        ticket_id="TKT-1",
        created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
        customer_message="Where is my order?",
    )
    assert ticket.ticket_id == "TKT-1"


@pytest.mark.parametrize("ticket_id", ["../escape", "with space", "a" * 100, ""])
def test_unsafe_ticket_ids_are_rejected(ticket_id):
    with pytest.raises(ValidationError):
        SupportTicket(
            ticket_id=ticket_id,
            created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
            customer_message="hello",
        )


def test_empty_message_is_rejected():
    """AT-002."""
    with pytest.raises(ValidationError):
        SupportTicket(
            ticket_id="TKT-1",
            created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
            customer_message="",
        )


def test_oversized_message_is_rejected():
    with pytest.raises(ValidationError):
        SupportTicket(
            ticket_id="TKT-1",
            created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
            customer_message="x" * 9000,
        )


def test_customer_reference_is_validated():
    ticket = SupportTicket(
        ticket_id="TKT-1",
        created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
        customer_message="Checkout fails.",
        customer_reference="cus-003",
    )
    assert ticket.customer_reference == "CUS-003"


def test_malformed_customer_reference_is_rejected():
    with pytest.raises(ValidationError):
        SupportTicket(
            ticket_id="TKT-1",
            created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
            customer_message="Checkout fails.",
            customer_reference="CUSTOMER-3",
        )


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        SupportTicket.model_validate(
            {
                "ticket_id": "TKT-1",
                "created_at": "2026-09-17T00:00:00Z",
                "customer_message": "hi",
                "injected_field": "value",
            }
        )
