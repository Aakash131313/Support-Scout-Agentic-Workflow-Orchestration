"""Safe artifact writing.

Every path is validated against a configured root, every write is atomic, and JSON is
emitted with stable key ordering so artifacts diff cleanly between runs.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .exceptions import FileOutputError
from .schemas import (
    InteractionSummary,
    SupportDomain,
    WorkflowState,
    WorkflowStatus,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

ESCALATION_RESPONSE = (
    "Thanks for contacting us. Your request needs review by an authorized support "
    "specialist, and it has been passed to that team. No refund, payment, account or "
    "order change has been made automatically."
)

ESCALATION_ARTICLE = (
    "# Human Review Required\n\n"
    "Automated troubleshooting guidance was not completed for this request because it "
    "requires a human decision. No reusable article was generated."
)


def _safe_ticket_id(ticket_id: str) -> str:
    if not _SAFE_ID.fullmatch(ticket_id):
        raise FileOutputError("Unsafe ticket identifier")
    return ticket_id


def _ensure_below_root(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise FileOutputError("Output path escapes the configured root")
    return candidate_resolved


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(text)
            temp_name = handle.name
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise FileOutputError("Unable to write output artifact") from exc


class ArtifactWriter:
    """Writes the standardized artifact set beneath a safe output root."""

    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)

    def ticket_directory(self, ticket_id: str) -> Path:
        safe_id = _safe_ticket_id(ticket_id)
        return _ensure_below_root(self.output_root, self.output_root / safe_id)

    def write_json(self, ticket_id: str, filename: str, value: Any) -> Path:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise FileOutputError("Invalid JSON filename")
        target = _ensure_below_root(
            self.output_root, self.ticket_directory(ticket_id) / filename
        )
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        try:
            payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        except (TypeError, ValueError) as exc:
            raise FileOutputError("Output is not JSON serializable") from exc
        _atomic_write(target, payload)
        return target

    def write_markdown(self, ticket_id: str, filename: str, content: str) -> Path:
        if Path(filename).name != filename or not filename.endswith(".md"):
            raise FileOutputError("Invalid Markdown filename")
        target = _ensure_below_root(
            self.output_root, self.ticket_directory(ticket_id) / filename
        )
        _atomic_write(target, content.rstrip() + "\n")
        return target


def build_interaction_summary(state: WorkflowState) -> InteractionSummary:
    """Build the written ticket-interaction summary artifact."""
    classification = state.classification
    sentiment = state.sentiment
    return InteractionSummary(
        ticket_id=state.ticket.ticket_id,
        run_id=state.run_id,
        domain=classification.domain if classification else SupportDomain.UNCERTAIN,
        intent=classification.intent if classification else "",
        urgency=classification.urgency if classification else None,
        sentiment_label=sentiment.label if sentiment else None,
        sentiment_intensity=sentiment.intensity if sentiment else None,
        workflow_status=state.current_state,
        qa_decision=state.qa_result.decision if state.qa_result else None,
        escalation=state.escalation,
        human_approval=state.human_approval,
        revision_count=state.revision_count,
        source_count=len(state.evidence),
        operational_source_count=len(state.operational_evidence),
        delegations=[record.specialist for record in state.delegations],
    )


def write_run_artifacts(
    writer: ArtifactWriter,
    state: WorkflowState,
    *,
    trace_events: list[dict[str, Any]] | None = None,
) -> Path:
    """Write the full artifact set for a run, whatever its terminal state.

    Escalated and failed runs produce artifacts too. A run that stops early must still
    leave a truthful record behind for the human who picks it up.
    """
    ticket_id = state.ticket.ticket_id

    writer.write_json(ticket_id, "interaction_summary.json", build_interaction_summary(state))

    response = (
        state.support_draft.customer_response
        if state.support_draft and state.current_state == WorkflowStatus.COMPLETED
        else ESCALATION_RESPONSE
    )
    writer.write_markdown(ticket_id, "customer_response.md", response)

    article = (
        state.article.body_markdown
        if state.article and state.current_state == WorkflowStatus.COMPLETED
        else ESCALATION_ARTICLE
    )
    writer.write_markdown(ticket_id, "troubleshooting_article.md", article)

    writer.write_json(
        ticket_id, "sources.json", [item.model_dump(mode="json") for item in state.evidence]
    )
    writer.write_json(
        ticket_id,
        "operational_sources.json",
        [item.model_dump(mode="json") for item in state.operational_evidence],
    )
    writer.write_json(
        ticket_id, "audit_log.json", [item.model_dump(mode="json") for item in state.audit_events]
    )
    writer.write_json(
        ticket_id,
        "agent_trace.json",
        {
            "run_id": state.run_id,
            "terminal_state": state.current_state.value,
            "delegations": [item.model_dump(mode="json") for item in state.delegations],
            "events": trace_events or [],
        },
    )

    if state.current_state == WorkflowStatus.ESCALATED:
        writer.write_json(
            ticket_id,
            "escalation.json",
            {
                "ticket_id": ticket_id,
                "run_id": state.run_id,
                "reason_code": (
                    state.escalation.reason_code.value if state.escalation.reason_code else None
                ),
                "summary": state.escalation.summary,
                "recommended_human_action": state.escalation.recommended_human_action,
                "human_approval": (
                    state.human_approval.model_dump(mode="json")
                    if state.human_approval
                    else None
                ),
            },
        )

    return writer.ticket_directory(ticket_id)
