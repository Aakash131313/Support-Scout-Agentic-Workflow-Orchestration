"""CLI tests: argument parsing, ticket loading and exit-code mapping."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from support_scout.main import (
    EXIT_COMPLETED,
    EXIT_ESCALATED,
    EXIT_INPUT,
    EXIT_WORKFLOW,
    build_parser,
    load_ticket,
    run_cli,
)
from support_scout.schemas import (
    EscalationDecision,
    EscalationReason,
    WorkflowState,
    WorkflowStatus,
)
from tests.conftest import make_ticket


@dataclass
class StubResult:
    state: WorkflowState
    output_directory: Path
    run_id: str = "run-1"


class StubOrchestrator:
    def __init__(self, status: WorkflowStatus, reason: EscalationReason | None = None):
        self.status = status
        self.reason = reason
        self.ran: list[str] = []

    def run(self, ticket):
        self.ran.append(ticket.ticket_id)
        state = WorkflowState(
            run_id="run-1",
            current_state=self.status,
            ticket=ticket,
            escalation=EscalationDecision(required=bool(self.reason), reason_code=self.reason),
        )
        return StubResult(state=state, output_directory=Path("output") / ticket.ticket_id)


def write_ticket(tmp_path: Path, **overrides) -> Path:
    payload = {
        "ticket_id": "TKT-CLI-001",
        "created_at": "2026-09-17T12:00:00Z",
        "customer_message": "My delivery is late.",
    }
    payload.update(overrides)
    path = tmp_path / "ticket.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------------------
def test_parser_exposes_the_three_subcommands():
    parser = build_parser()
    for command in ("run", "chat", "serve"):
        assert parser.parse_args([command] if command != "run" else ["run", "x.json"])


def test_version_flag_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--version"])
    assert exc_info.value.code == 0


def test_no_command_prints_help_and_returns_input_error(capsys):
    assert run_cli([]) == EXIT_INPUT
    assert "usage" in capsys.readouterr().out.casefold()


# --------------------------------------------------------------------------------------
# Ticket loading
# --------------------------------------------------------------------------------------
def test_valid_ticket_loads(tmp_path):
    ticket = load_ticket(write_ticket(tmp_path))
    assert ticket.ticket_id == "TKT-CLI-001"


def test_ticket_with_customer_reference_loads(tmp_path):
    ticket = load_ticket(write_ticket(tmp_path, customer_reference="CUS-003"))
    assert ticket.customer_reference == "CUS-003"


# --------------------------------------------------------------------------------------
# Exit codes
# --------------------------------------------------------------------------------------
def test_completed_run_exits_zero(tmp_path):
    orchestrator = StubOrchestrator(WorkflowStatus.COMPLETED)
    code = run_cli(
        ["run", str(write_ticket(tmp_path)), "--skip-service-check"],
        orchestrator_factory=lambda _output: orchestrator,
    )
    assert code == EXIT_COMPLETED
    assert orchestrator.ran == ["TKT-CLI-001"]


def test_escalated_run_exits_three(tmp_path):
    code = run_cli(
        ["run", str(write_ticket(tmp_path)), "--skip-service-check"],
        orchestrator_factory=lambda _output: StubOrchestrator(
            WorkflowStatus.ESCALATED, EscalationReason.FINANCIAL_AUTHORIZATION
        ),
    )
    assert code == EXIT_ESCALATED


def test_failed_run_exits_four(tmp_path):
    code = run_cli(
        ["run", str(write_ticket(tmp_path)), "--skip-service-check"],
        orchestrator_factory=lambda _output: StubOrchestrator(WorkflowStatus.FAILED),
    )
    assert code == EXIT_WORKFLOW


def test_invalid_input_exits_two(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{broken", encoding="utf-8")
    code = run_cli(
        ["run", str(path), "--skip-service-check"],
        orchestrator_factory=lambda _output: StubOrchestrator(WorkflowStatus.COMPLETED),
    )
    assert code == EXIT_INPUT
    assert "error" in capsys.readouterr().err.casefold()


def test_missing_input_exits_two(tmp_path):
    code = run_cli(
        ["run", str(tmp_path / "nope.json"), "--skip-service-check"],
        orchestrator_factory=lambda _output: StubOrchestrator(WorkflowStatus.COMPLETED),
    )
    assert code == EXIT_INPUT


def test_summary_line_reports_the_outcome(tmp_path, capsys):
    run_cli(
        ["run", str(write_ticket(tmp_path)), "--skip-service-check"],
        orchestrator_factory=lambda _output: StubOrchestrator(
            WorkflowStatus.ESCALATED, EscalationReason.POLICY_EXCEPTION
        ),
    )
    output = capsys.readouterr().out
    assert "status=escalated" in output
    assert "escalation=policy_exception" in output
