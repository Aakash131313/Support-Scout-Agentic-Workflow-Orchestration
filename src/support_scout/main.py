"""SupportScout command line interface.

Three subcommands, one entry point:

    support-scout run <ticket.json>   run the agentic workflow over one ticket
    support-scout chat                interactive mode, one ticket per message
    support-scout serve               start the synthetic operations service
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from . import __version__
from .config import Settings
from .exceptions import ConfigurationError, FileOutputError, SupportScoutError
from .schemas import SupportTicket, WorkflowStatus

EXIT_COMPLETED = 0
EXIT_INPUT = 2
EXIT_ESCALATED = 3
EXIT_WORKFLOW = 4
EXIT_OUTPUT = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="support-scout",
        description="Agentic, evidence-grounded e-commerce support automation.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the workflow over one JSON ticket")
    run_parser.add_argument("input", help="Path to a synthetic JSON support ticket")
    run_parser.add_argument("--output", help="Override the output root directory")
    run_parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Approve restricted actions without prompting (CI and testing only)",
    )
    run_parser.add_argument(
        "--skip-service-check",
        action="store_true",
        help="Do not probe the operations service before running",
    )

    chat_parser = subparsers.add_parser("chat", help="Interactive support session")
    chat_parser.add_argument("--output", help="Override the output root directory")

    serve_parser = subparsers.add_parser("serve", help="Start the synthetic operations service")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8001)
    serve_parser.add_argument(
        "--reseed", action="store_true", help="Rebuild the synthetic database before serving"
    )

    return parser


def load_ticket(path: str | Path) -> SupportTicket:
    """Load and validate one JSON ticket from disk."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
        return SupportTicket.model_validate(json.loads(raw))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ConfigurationError(
            f"Input ticket is missing, unreadable or invalid: {type(exc).__name__}"
        ) from exc


def _exit_code_for(status: WorkflowStatus) -> int:
    return {
        WorkflowStatus.COMPLETED: EXIT_COMPLETED,
        WorkflowStatus.ESCALATED: EXIT_ESCALATED,
        WorkflowStatus.FAILED: EXIT_WORKFLOW,
    }.get(status, EXIT_WORKFLOW)


def command_run(args: argparse.Namespace, orchestrator_factory=None) -> int:
    """Run the workflow over a single ticket file."""
    from .workflow.assembly import build_orchestrator, check_operations_service

    settings = Settings.from_env()

    if not args.skip_service_check and orchestrator_factory is None:
        healthy, message = check_operations_service(settings)
        if not healthy:
            print(f"error: {message}", file=sys.stderr)
            return EXIT_INPUT
        print(f"[STARTUP] {message}")

    ticket = load_ticket(args.input)

    orchestrator = (
        orchestrator_factory(args.output)
        if orchestrator_factory
        else build_orchestrator(
            settings,
            output_override=args.output,
            interactive=sys.stdin.isatty(),
            auto_approve=args.auto_approve,
        )
    )

    result = orchestrator.run(ticket)
    reason = (
        result.state.escalation.reason_code.value
        if result.state.escalation.reason_code
        else "none"
    )
    print(
        f"\nticket={result.state.ticket.ticket_id} "
        f"run={result.run_id} "
        f"status={result.state.current_state.value} "
        f"escalation={reason} "
        f"output={result.output_directory}"
    )
    return _exit_code_for(result.state.current_state)


def command_chat(args: argparse.Namespace, orchestrator_factory=None) -> int:
    """Interactive session: each message becomes one ticket."""
    from .workflow.assembly import build_orchestrator

    settings = Settings.from_env()
    orchestrator = (
        orchestrator_factory(args.output)
        if orchestrator_factory
        else build_orchestrator(
            settings, output_override=args.output, interactive=True
        )
    )

    print("SupportScout interactive mode")
    print("Type 'help' for supported topics, or 'quit' to exit.\n")

    while True:
        try:
            message = input("SupportScout> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not message:
            continue
        if message.casefold() in {"quit", "exit"}:
            break
        if message.casefold() == "help":
            print(
                "\nSupportScout can help with:\n"
                "  - Order tracking and delivery: delays, missing tracking, "
                "packages marked delivered\n"
                "  - Returns and refunds: how to return, eligibility, refund status\n"
                "  - Account and checkout: sign-in trouble, checkout failures\n\n"
                "Anything needing a refund decision or policy exception is routed to a "
                "human.\n"
            )
            continue

        ticket = SupportTicket(
            ticket_id=f"TKT-{uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc),
            customer_message=message,
        )
        result = orchestrator.run(ticket)
        print(f"\nStatus: {result.state.current_state.value}")
        if result.state.escalation.reason_code:
            print(f"Escalated: {result.state.escalation.reason_code.value}")
        if result.state.support_draft:
            print(f"\n{result.state.support_draft.customer_response}\n")

    return EXIT_COMPLETED


def command_serve(args: argparse.Namespace) -> int:
    """Start the synthetic operations service."""
    import uvicorn

    from data_server.seed import seed_database

    seed_database(force=args.reseed)
    print(f"Serving synthetic operations data on http://{args.host}:{args.port}")
    uvicorn.run("data_server.app:app", host=args.host, port=args.port, log_level="warning")
    return EXIT_COMPLETED


def run_cli(argv=None, orchestrator_factory=None) -> int:
    """Parse arguments and dispatch, mapping every failure to a stable exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_INPUT

    try:
        if args.command == "run":
            return command_run(args, orchestrator_factory)
        if args.command == "chat":
            return command_chat(args, orchestrator_factory)
        if args.command == "serve":
            return command_serve(args)
    except FileOutputError as exc:
        print(f"output error: {exc}", file=sys.stderr)
        return EXIT_OUTPUT
    except (ConfigurationError, ValidationError) as exc:
        print(f"input/configuration error: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except SupportScoutError as exc:
        print(f"workflow error: {exc}", file=sys.stderr)
        return EXIT_WORKFLOW

    parser.print_help()
    return EXIT_INPUT


def main(argv=None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
