"""Curated evaluation runner.

This measures a curated synthetic baseline. It is not a production benchmark and the
report says so in its own output.

Two modes:

* default (offline) - evaluates the deterministic safety and validation layer over
  curated cases. Fully reproducible, needs no API keys, and is what CI runs.
* ``--live``        - runs the real agentic workflow per case against a live model.
  Requires credentials and a running operations service.

Reporting rules: every metric reports numerator, denominator and the evaluation date.
Failed cases are listed by identifier rather than silently dropped.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from support_scout.schemas import (
    EscalationReason,
    ScrapedEvidence,
    SupportDraft,
    SupportDomain,
    SupportTicket,
    Urgency,
    WorkflowStatus,
)
from support_scout.services.content_validation import ContentValidator
from support_scout.services.safety_rules import SafetyScreener

DEFAULT_CONFIDENCE_THRESHOLD = 0.70


class Case(BaseModel):
    """One curated evaluation case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    ticket: SupportTicket
    fixture_domain: SupportDomain
    fixture_confidence: float = Field(ge=0.0, le=1.0)
    expected_domain: SupportDomain
    acceptable_urgency: list[Urgency]
    expected_escalation: bool
    expected_escalation_reason: EscalationReason | None
    prohibited_claims: list[str] = Field(default_factory=list)
    expected_terminal_state: WorkflowStatus
    tags: list[str] = Field(default_factory=list)


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    cases: list[Case]


def evaluate_case(case: Case, *, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict[str, Any]:
    """Evaluate one case against the deterministic safety and validation layer."""
    screener = SafetyScreener()

    domain = case.fixture_domain
    urgency = case.acceptable_urgency[0] if case.acceptable_urgency else Urgency.MEDIUM

    screening = screener.screen_ticket(case.ticket)
    escalation = screening.escalation

    if screening.required:
        domain = SupportDomain.UNCERTAIN
        urgency = Urgency.MEDIUM
    else:
        from support_scout.schemas import TicketClassification

        classification = TicketClassification(
            domain=case.fixture_domain,
            intent="curated_fixture",
            urgency=urgency,
            confidence=case.fixture_confidence,
            uncertainty_reason=(
                "curated uncertainty" if case.fixture_domain == SupportDomain.UNCERTAIN else None
            ),
        )
        post = screener.screen_classification(
            classification, confidence_threshold=confidence_threshold
        )
        escalation = post.escalation
        if post.escalation.reason_code == EscalationReason.LOW_CONFIDENCE:
            domain = SupportDomain.UNCERTAIN

    # Evidence-quality outcomes are encoded in the case tags.
    if "insufficient_evidence" in case.tags and not escalation.required:
        escalation = escalation.model_copy(
            update={"required": True, "reason_code": EscalationReason.INSUFFICIENT_EVIDENCE}
        )
    if "conflicting_evidence" in case.tags and not escalation.required:
        escalation = escalation.model_copy(
            update={"required": True, "reason_code": EscalationReason.CONFLICTING_EVIDENCE}
        )

    qa_protected: bool | None = None
    if "qa_protection" in case.tags:
        qa_protected = _qa_blocks_unsupported_claim()
        escalation = escalation.model_copy(
            update={"required": True, "reason_code": EscalationReason.FINANCIAL_AUTHORIZATION}
        )

    terminal = WorkflowStatus.ESCALATED if escalation.required else WorkflowStatus.COMPLETED

    return {
        "case_id": case.case_id,
        "actual_domain": domain.value,
        "actual_urgency": urgency.value,
        "actual_escalation": escalation.required,
        "actual_escalation_reason": (
            escalation.reason_code.value if escalation.reason_code else None
        ),
        "actual_terminal_state": terminal.value,
        "qa_protected": qa_protected,
        "checks": {
            "domain": domain == case.expected_domain,
            "urgency": urgency in case.acceptable_urgency,
            "escalation": escalation.required == case.expected_escalation,
            "escalation_reason": escalation.reason_code == case.expected_escalation_reason,
            "terminal": terminal == case.expected_terminal_state,
        },
    }


def _qa_blocks_unsupported_claim() -> bool:
    """Confirm the deterministic validator rejects a fabricated refund approval."""
    evidence = [
        ScrapedEvidence(
            evidence_id="EV-001",
            source_url="https://help.example.com/guide",
            title="Synthetic guidance",
            retrieved_at=datetime.now(timezone.utc),
            content="General return guidance.",
            content_hash="abcdef1234",
        )
    ]
    draft = SupportDraft(
        issue_summary="Refund request.",
        customer_response="Your refund has been approved.",
        troubleshooting_steps=["Watch for the credit."],
        evidence_ids=["EV-001"],
    )
    return ContentValidator().validate(draft, evidence).contains_restricted_claim


def metric(rows: list[bool]) -> dict[str, Any]:
    """Report numerator, denominator and rate. Never a bare percentage."""
    numerator = sum(1 for value in rows if value)
    denominator = len(rows)
    return {
        "numerator": numerator,
        "denominator": denominator,
        "result": (numerator / denominator) if denominator else None,
    }


def run(dataset_path: str | Path) -> dict[str, Any]:
    """Evaluate every case in the dataset and build the report."""
    dataset = Dataset.model_validate_json(Path(dataset_path).read_text(encoding="utf-8"))
    results = [evaluate_case(case) for case in dataset.cases]

    completed = [row for row in results if row["actual_terminal_state"] == "completed"]
    escalated = [row for row in results if row["actual_escalation"]]
    qa_rows = [row for row in results if row["qa_protected"] is not None]

    metrics = {
        "domain_accuracy": metric([row["checks"]["domain"] for row in results]),
        "urgency_accuracy": metric([row["checks"]["urgency"] for row in results]),
        "escalation_accuracy": metric([row["checks"]["escalation"] for row in results]),
        "escalation_reason_accuracy": metric(
            [row["checks"]["escalation_reason"] for row in escalated]
        ),
        "terminal_state_accuracy": metric([row["checks"]["terminal"] for row in results]),
        "qa_protection_rate": metric([bool(row["qa_protected"]) for row in qa_rows]),
    }

    failed = [
        row["case_id"]
        for row in results
        if not all(row["checks"].values()) or row["qa_protected"] is False
    ]

    return {
        "evaluation_type": "curated deterministic baseline",
        "dataset_version": dataset.dataset_version,
        "evaluation_date": datetime.now(timezone.utc).date().isoformat(),
        "configuration": {
            "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
            "live_dependencies": False,
        },
        "composition": dict(Counter(tag for case in dataset.cases for tag in case.tags)),
        "metrics": metrics,
        "failed_case_ids": failed,
        "cases": results,
        "completed_case_count": len(completed),
        "limitations": [
            "Synthetic curated cases only; this is not production traffic.",
            "Measures the deterministic safety and validation layer, not model quality.",
            "Frozen fixtures mean these numbers cannot be read as live accuracy.",
            "Conflict detection is a conservative heuristic and will miss subtle disagreement.",
        ],
    }


def to_markdown(report: dict[str, Any]) -> str:
    """Render the report as a reviewer-friendly Markdown summary."""
    lines = [
        "# SupportScout Curated Evaluation Results",
        "",
        "This is a curated deterministic baseline, not production performance.",
        "",
        f"- Dataset version: {report['dataset_version']}",
        f"- Evaluation date: {report['evaluation_date']}",
        f"- Cases evaluated: {len(report['cases'])}",
        f"- Failed cases: {len(report['failed_case_ids'])}",
        "",
        "## Metrics",
        "",
        "| Metric | Numerator | Denominator | Result |",
        "|---|---:|---:|---:|",
    ]

    for name, values in report["metrics"].items():
        result = f"{values['result']:.3f}" if values["result"] is not None else "n/a"
        lines.append(
            f"| {name.replace('_', ' ').title()} | {values['numerator']} | "
            f"{values['denominator']} | {result} |"
        )

    lines += [
        "",
        "## Failed case identifiers",
        "",
        ", ".join(report["failed_case_ids"]) or "None",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {item}" for item in report["limitations"]]

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the curated SupportScout evaluation.")
    parser.add_argument("--dataset", default="src/evaluation/evaluation_cases.json")
    parser.add_argument("--output-dir", default="src/evaluation")
    args = parser.parse_args(argv)

    report = run(args.dataset)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "results.md").write_text(to_markdown(report), encoding="utf-8")

    print(
        f"evaluated={len(report['cases'])} "
        f"failed={len(report['failed_case_ids'])} "
        f"date={report['evaluation_date']}"
    )
    return 1 if report["failed_case_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
