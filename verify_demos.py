#!/usr/bin/env python3
"""Run every curated sample ticket and report whether the results look right.

This is a diagnostic script, not part of the package. It uses your real .env
credentials, real Tavily search, the real operations service and real
smolagents agents -- nothing is mocked.

Unlike a plain batch runner, this compares each ticket against its documented
expected outcome and raises explicit red flags for the failure modes seen during
development: retry loops, repeated submit calls, escalations on tickets that should
complete, exhausted revision budgets, operational claims with no OP- citation, and
drafts that dropped their evidence citations.

Usage:
    python3 verify_demos.py
    python3 verify_demos.py --auto-approve
    python3 verify_demos.py --only 05_unknown_order 13_refund_approval_request

Restricted-action tickets are answered "deny" automatically by default, because the
script runs unattended and cannot prompt eighteen times. Pass --auto-approve to see
the approved path instead.

Output goes to stdout as a compact table plus a red-flag section, and the full
detail is written to verify_demos_report.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

SAMPLE_DIR = Path("sample_inputs")
START_MARKER = "===== VERIFY_REPORT_START ====="
END_MARKER = "===== VERIFY_REPORT_END ====="

#: Documented expected terminal state per curated sample, from sample_inputs/README.md.
#: "completed" or "escalated". A mismatch is the single most useful red flag.
EXPECTED_OUTCOME: dict[str, str] = {
    "01_order_delay_operational": "completed",
    "02_delivered_not_received": "completed",
    "03_order_not_yet_shipped": "completed",
    "04_carrier_exception": "completed",
    "05_unknown_order": "completed",
    "06_return_status": "completed",
    "07_return_how_to": "completed",
    "08_checkout_address_failure": "completed",
    "09_checkout_payment_declined": "completed",
    "10_login_failure": "completed",
    "11_shipping_policy_question": "completed",
    "12_negative_sentiment_routine": "completed",
    "13_refund_approval_request": "escalated",
    "14_refund_paraphrased": "escalated",
    "15_policy_exception": "escalated",
    "16_account_compromise_calm": "escalated",
    "17_prompt_injection": "escalated",
    "18_sensitive_data": "escalated",
}

#: Escalation reasons that are expected for specific tickets. Anything else on those
#: tickets means a rule fired that should not have.
EXPECTED_ESCALATION_REASON: dict[str, str] = {
    "13_refund_approval_request": "financial_authorization",
    "14_refund_paraphrased": "financial_authorization",
    "15_policy_exception": "policy_exception",
    "16_account_compromise_calm": "account_compromise",
    "17_prompt_injection": "outside_authority",
    "18_sensitive_data": "sensitive_data",
}

#: A specialist delegated more than this many times in one run indicates a retry loop.
RETRY_LOOP_THRESHOLD = 3


# --------------------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------------------
def discover_samples(only: list[str] | None) -> list[Path]:
    """Return the curated sample tickets to run, sorted, excluding README."""
    if not SAMPLE_DIR.is_dir():
        print(f"error: {SAMPLE_DIR} not found. Run this from the project root.", file=sys.stderr)
        raise SystemExit(2)

    paths = sorted(p for p in SAMPLE_DIR.glob("*.json"))
    if only:
        wanted = set(only)
        paths = [p for p in paths if p.stem in wanted or p.name in wanted]
        missing = wanted - {p.stem for p in paths} - {p.name for p in paths}
        if missing:
            print(f"warning: no such sample, skipped: {sorted(missing)}", file=sys.stderr)

    if not paths:
        print("error: no sample tickets matched.", file=sys.stderr)
        raise SystemExit(2)
    return paths


# --------------------------------------------------------------------------------------
# Trace reading
# --------------------------------------------------------------------------------------
def read_trace(log_dir: Path, run_id: str) -> list[dict[str, Any]]:
    """Read a run's JSONL trace. Returns an empty list when unavailable."""
    path = log_dir / run_id / "trace.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def read_run_errors(log_dir: Path, run_id: str) -> list[dict[str, Any]]:
    """Read errors.jsonl entries belonging to this run."""
    path = log_dir / "errors.jsonl"
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("run_id") == run_id:
            entries.append(entry)
    return entries


def summarize_tool_calls(events: list[dict[str, Any]]) -> tuple[int, dict[str, list[str]]]:
    """Count tool calls and group them by the agent that made them."""
    by_agent: dict[str, list[str]] = {}
    total = 0
    for event in events:
        if event.get("event") != "tool_called":
            continue
        total += 1
        by_agent.setdefault(event.get("agent_name", "unknown"), []).append(
            event.get("tool_name", "unknown")
        )
    return total, by_agent


# --------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------
def build_summary(
    *,
    stem: str,
    ticket_id: str,
    run_id: str | None,
    elapsed: float,
    state: Any = None,
    output_dir: Path | None = None,
    trace: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build one ticket's summary from a RunResult state, or from a script error."""
    trace = trace or []
    errors = errors or []

    summary: dict[str, Any] = {
        "sample": stem,
        "ticket_id": ticket_id,
        "run_id": run_id,
        "elapsed_seconds": round(elapsed, 1),
        "expected_outcome": EXPECTED_OUTCOME.get(stem),
        "script_error": error,
    }

    if error is not None or state is None:
        summary.update(
            {
                "status": "script_error",
                "escalation_reason": None,
                "expected_escalation_reason": EXPECTED_ESCALATION_REASON.get(stem),
                "domain": None,
                "sentiment": None,
                "delegations": [],
                "delegation_counts": {},
                "revision_count": None,
                "max_revisions": None,
                "qa_decision": None,
                "public_evidence": 0,
                "operational_evidence": 0,
                "absence_evidence": 0,
                "cited_evidence_ids": [],
                "cited_operational": 0,
                "has_steps": False,
                "tool_call_count": 0,
                "tools_by_agent": {},
                "repeated_submit_calls": {},
                "error_count": len(errors),
                "error_categories": sorted({e.get("error_category", "?") for e in errors}),
                "artifacts": [],
                "output_dir": None,
            }
        )
        return summary

    classification = state.classification
    sentiment = state.sentiment
    draft = state.support_draft

    delegations = [record.specialist for record in state.delegations]
    delegation_counts = dict(Counter(delegations))

    tool_total, tools_by_agent = summarize_tool_calls(trace)

    # Repeated submit_* calls indicate an idempotency guard is missing or not firing.
    repeated_submits: dict[str, int] = {}
    for agent, names in tools_by_agent.items():
        for name, count in Counter(names).items():
            if name.startswith("submit_") and count > 1:
                repeated_submits[f"{agent}.{name}"] = count

    cited = list(draft.evidence_ids) if draft else []
    absence_records = sum(
        1
        for item in state.operational_evidence
        if isinstance(item.facts, dict) and item.facts.get("available") is False
    )

    summary.update(
        {
            "status": state.current_state.value,
            "escalation_reason": (
                state.escalation.reason_code.value if state.escalation.reason_code else None
            ),
            "expected_escalation_reason": EXPECTED_ESCALATION_REASON.get(stem),
            "domain": classification.domain.value if classification else None,
            "sentiment": (
                f"{sentiment.label.value}/{sentiment.intensity.value}" if sentiment else None
            ),
            "human_approval": (
                state.human_approval.approved if state.human_approval else None
            ),
            "delegations": delegations,
            "delegation_counts": delegation_counts,
            "revision_count": state.revision_count,
            "qa_decision": state.qa_result.decision.value if state.qa_result else None,
            "public_evidence": len(state.evidence),
            "operational_evidence": len(state.operational_evidence),
            "absence_evidence": absence_records,
            "cited_evidence_ids": cited,
            "cited_operational": sum(1 for i in cited if i.startswith("OP-")),
            "has_steps": bool(draft and any(s.strip() for s in draft.troubleshooting_steps)),
            "tool_call_count": tool_total,
            "tools_by_agent": {k: dict(Counter(v)) for k, v in tools_by_agent.items()},
            "repeated_submit_calls": repeated_submits,
            "error_count": len(errors),
            "error_categories": sorted({e.get("error_category", "?") for e in errors}),
            "artifacts": sorted(p.name for p in output_dir.iterdir()) if output_dir else [],
            "output_dir": str(output_dir) if output_dir else None,
        }
    )
    return summary


# --------------------------------------------------------------------------------------
# Red flags
# --------------------------------------------------------------------------------------
def red_flags(summary: dict[str, Any]) -> list[str]:
    """Return every anomaly worth a human look for one ticket."""
    flags: list[str] = []
    stem = summary["sample"]
    status = summary["status"]
    expected = summary["expected_outcome"]

    if summary["script_error"]:
        flags.append(f"SCRIPT ERROR: {summary['script_error']}")
        return flags

    if status == "failed":
        flags.append("HARD FAILURE: workflow ended as 'failed' with no escalation reason")

    if expected and status != expected:
        flags.append(f"OUTCOME MISMATCH: expected '{expected}', got '{status}'")

    expected_reason = summary["expected_escalation_reason"]
    actual_reason = summary["escalation_reason"]
    if expected_reason and actual_reason and actual_reason != expected_reason:
        flags.append(
            f"WRONG ESCALATION REASON: expected '{expected_reason}', got '{actual_reason}'"
        )
    if not expected_reason and actual_reason and expected == "completed":
        flags.append(f"UNEXPECTED ESCALATION: '{actual_reason}' on a ticket that should complete")

    for specialist, count in summary["delegation_counts"].items():
        if count >= RETRY_LOOP_THRESHOLD:
            flags.append(
                f"RETRY LOOP: '{specialist}' delegated {count} times "
                f"(threshold {RETRY_LOOP_THRESHOLD})"
            )

    for tool_name, count in summary["repeated_submit_calls"].items():
        if count >= 3:
            flags.append(f"REPEATED SUBMIT: {tool_name} called {count} times; idempotency guard missed")

    if summary["revision_count"] and summary["qa_decision"] == "revise":
        flags.append("REVISION BUDGET SPENT: QA still requesting changes at the limit")

    # Grounding: steps present but nothing cited, while evidence existed.
    if summary["has_steps"] and not summary["cited_evidence_ids"]:
        total_evidence = summary["public_evidence"] + summary["operational_evidence"]
        if total_evidence:
            flags.append(
                "CITATION DROPPED: draft has troubleshooting steps but cites no evidence, "
                f"while {total_evidence} record(s) were available"
            )

    # Operational grounding: operational lookups happened but nothing operational cited.
    if summary["operational_evidence"] and status == "completed":
        if summary["cited_operational"] == 0:
            flags.append(
                f"OPERATIONAL EVIDENCE UNUSED: {summary['operational_evidence']} OP- record(s) "
                "gathered but none cited in the draft"
            )

    if status == "completed" and summary["tool_call_count"] == 0:
        flags.append(
            "TRACE EMPTY: completed run recorded zero tool calls "
            "(agents/base.py tracing fix may not be applied)"
        )

    if summary["error_count"]:
        flags.append(
            f"ERRORS LOGGED: {summary['error_count']} entr(ies) -> "
            f"{', '.join(summary['error_categories'])}"
        )

    if status in {"completed", "escalated"} and not summary["artifacts"]:
        flags.append("NO ARTIFACTS: terminal run wrote no output files")

    return flags


def expected_artifacts(status: str) -> set[str]:
    base = {
        "interaction_summary.json",
        "customer_response.md",
        "troubleshooting_article.md",
        "sources.json",
        "operational_sources.json",
        "audit_log.json",
        "agent_trace.json",
    }
    if status == "escalated":
        base.add("escalation.json")
    return base


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
def render_table(summaries: list[dict[str, Any]]) -> str:
    """Compact fixed-width table, one row per ticket."""
    header = (
        f"{'sample':32} {'status':10} {'escalation':24} {'dele':5} "
        f"{'EV':3} {'OP':3} {'cited':6} {'rev':4} {'qa':8} {'sec':6} ok"
    )
    lines = [header, "-" * len(header)]
    for s in summaries:
        ok = "OK" if not s["_flags"] else f"{len(s['_flags'])} FLAG"
        lines.append(
            f"{s['sample'][:32]:32} {str(s['status'])[:10]:10} "
            f"{str(s['escalation_reason'] or '-')[:24]:24} "
            f"{len(s['delegations']):<5} {s['public_evidence']:<3} "
            f"{s['operational_evidence']:<3} {len(s['cited_evidence_ids']):<6} "
            f"{str(s['revision_count']):<4} {str(s['qa_decision'] or '-')[:8]:8} "
            f"{s['elapsed_seconds']:<6} {ok}"
        )
    return "\n".join(lines)


def render_flags(summaries: list[dict[str, Any]]) -> str:
    flagged = [s for s in summaries if s["_flags"]]
    if not flagged:
        return "No red flags. Every ticket matched its expected outcome."
    lines = []
    for s in flagged:
        lines.append(f"\n{s['sample']}  (run {s['run_id']})")
        for flag in s["_flags"]:
            lines.append(f"    - {flag}")
    return "\n".join(lines)


def aggregate(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = Counter(s["status"] for s in summaries)
    by_reason = Counter(s["escalation_reason"] for s in summaries if s["escalation_reason"])
    matched = sum(
        1 for s in summaries if s["expected_outcome"] and s["status"] == s["expected_outcome"]
    )
    checked = sum(1 for s in summaries if s["expected_outcome"])
    return {
        "tickets_run": len(summaries),
        "outcome_matches": f"{matched}/{checked}",
        "by_status": dict(by_status),
        "by_escalation_reason": dict(by_reason),
        "total_flags": sum(len(s["_flags"]) for s in summaries),
        "flagged_tickets": [s["sample"] for s in summaries if s["_flags"]],
        "total_tool_calls": sum(s["tool_call_count"] for s in summaries),
        "total_seconds": round(sum(s["elapsed_seconds"] for s in summaries), 1),
        "absence_evidence_registered": sum(s["absence_evidence"] for s in summaries),
    }


# --------------------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------------------
def run_all(
    *,
    samples: list[Path],
    output_dir: str,
    log_dir: str,
    auto_approve: bool,
    skip_service_check: bool,
) -> list[dict[str, Any]]:
    import dataclasses

    from support_scout.config import Settings
    from support_scout.main import load_ticket
    from support_scout.workflow.assembly import build_orchestrator, check_operations_service

    settings = Settings.from_env()

    if not skip_service_check:
        healthy, message = check_operations_service(settings)
        print(f"[STARTUP] {message}")
        if not healthy:
            print("error: start the operations service first.", file=sys.stderr)
            raise SystemExit(2)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    settings = dataclasses.replace(settings, log_directory=log_path)

    orchestrator = build_orchestrator(
        settings,
        output_override=output_dir,
        interactive=False,
        auto_approve=auto_approve,
        echo_insights=False,
    )

    summaries: list[dict[str, Any]] = []

    for index, path in enumerate(samples, start=1):
        print(f"[{index}/{len(samples)}] {path.stem} ...", end=" ", flush=True)
        started = time.monotonic()

        try:
            ticket = load_ticket(path)
        except Exception as exc:  # noqa: BLE001 - reported per ticket
            summaries.append(
                build_summary(
                    stem=path.stem,
                    ticket_id=path.stem,
                    run_id=None,
                    elapsed=time.monotonic() - started,
                    error=f"failed to load ticket: {exc}",
                )
            )
            print("LOAD ERROR")
            continue

        try:
            result = orchestrator.run(ticket)
        except Exception as exc:  # noqa: BLE001 - reported per ticket, batch continues
            summaries.append(
                build_summary(
                    stem=path.stem,
                    ticket_id=ticket.ticket_id,
                    run_id=None,
                    elapsed=time.monotonic() - started,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            print("RUN ERROR")
            traceback.print_exc(file=sys.stderr)
            continue

        elapsed = time.monotonic() - started
        trace = read_trace(log_path, result.run_id)
        errors = read_run_errors(log_path, result.run_id)

        summary = build_summary(
            stem=path.stem,
            ticket_id=ticket.ticket_id,
            run_id=result.run_id,
            elapsed=elapsed,
            state=result.state,
            output_dir=result.output_directory,
            trace=trace,
            errors=errors,
        )

        missing = expected_artifacts(summary["status"]) - set(summary["artifacts"])
        if missing and summary["status"] in {"completed", "escalated"}:
            summary.setdefault("_extra_flags", []).append(
                f"MISSING ARTIFACTS: {sorted(missing)}"
            )

        summaries.append(summary)
        print(f"{summary['status']} ({elapsed:.0f}s)")

    for summary in summaries:
        summary["_flags"] = red_flags(summary) + summary.pop("_extra_flags", [])

    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", default=None, help="Run only these sample stems.")
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Approve restricted actions instead of denying by default.",
    )
    parser.add_argument("--output-dir", default="verify_output")
    parser.add_argument("--log-dir", default="verify_logs")
    parser.add_argument("--skip-service-check", action="store_true")
    parser.add_argument("--json-out", default="verify_demos_report.json")
    args = parser.parse_args(argv)

    samples = discover_samples(args.only)
    print(f"Running {len(samples)} sample ticket(s).")
    print(f"Approval policy: {'auto-approve' if args.auto_approve else 'deny by default'}\n")

    summaries = run_all(
        samples=samples,
        output_dir=args.output_dir,
        log_dir=args.log_dir,
        auto_approve=args.auto_approve,
        skip_service_check=args.skip_service_check,
    )

    stats = aggregate(summaries)
    payload = {"aggregate": stats, "tickets": summaries}
    Path(args.json_out).write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )

    print()
    print(START_MARKER)
    print()
    print("SUMMARY")
    print(f"  tickets run          : {stats['tickets_run']}")
    print(f"  expected outcome met : {stats['outcome_matches']}")
    print(f"  by status            : {stats['by_status']}")
    print(f"  escalation reasons   : {stats['by_escalation_reason'] or 'none'}")
    print(f"  absence records (OP-): {stats['absence_evidence_registered']}")
    print(f"  total tool calls     : {stats['total_tool_calls']}")
    print(f"  total time           : {stats['total_seconds']}s")
    print(f"  RED FLAGS            : {stats['total_flags']}")
    print()
    print("PER TICKET")
    print(render_table(summaries))
    print()
    print("RED FLAGS")
    print(render_flags(summaries))
    print()
    print(END_MARKER)
    print(f"\nFull detail written to {args.json_out}")

    return 1 if stats["total_flags"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
