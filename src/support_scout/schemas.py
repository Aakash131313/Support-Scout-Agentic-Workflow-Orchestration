"""Pydantic contracts shared by every agent, tool and artifact.

These models are the single source of truth for data shapes. Agents may only exchange
validated instances of these models; free-form dictionaries never cross an agent
boundary.
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

_TICKET_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ORDER_REFERENCE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CUSTOMER_REFERENCE = re.compile(r"^CUS-[0-9]{1,12}$")

MAX_CUSTOMER_MESSAGE_CHARACTERS = 8000


class StrictModel(BaseModel):
    """Base contract: unknown fields are rejected rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------------------
class SupportDomain(StrEnum):
    ORDER_TRACKING_DELIVERY = "order_tracking_delivery"
    RETURNS_REFUNDS = "returns_refunds"
    ACCOUNT_CHECKOUT = "account_checkout"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SentimentIntensity(StrEnum):
    MILD = "mild"
    MODERATE = "moderate"
    STRONG = "strong"


class QADecision(StrEnum):
    APPROVE = "approve"
    REVISE = "revise"
    ESCALATE = "escalate"


class EscalationReason(StrEnum):
    FINANCIAL_AUTHORIZATION = "financial_authorization"
    POLICY_EXCEPTION = "policy_exception"
    ACCOUNT_COMPROMISE = "account_compromise"
    SENSITIVE_DATA = "sensitive_data"
    UNSUPPORTED_DOMAIN = "unsupported_domain"
    LOW_CONFIDENCE = "low_confidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    REVISION_LIMIT_EXCEEDED = "revision_limit_exceeded"
    OUTSIDE_AUTHORITY = "outside_authority"
    QA_FAILURE = "qa_failure"
    HUMAN_REJECTED = "human_rejected"
    EXECUTION_BUDGET_EXCEEDED = "execution_budget_exceeded"


class WorkflowStatus(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    TRIAGED = "triaged"
    RESEARCHED = "researched"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    DRAFTED = "drafted"
    QA_REVISION_REQUESTED = "qa_revision_requested"
    QA_APPROVED = "qa_approved"
    DOCUMENTED = "documented"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    FAILED = "failed"


TERMINAL_STATUSES = frozenset(
    {WorkflowStatus.COMPLETED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED}
)


# --------------------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------------------
class SupportTicket(StrictModel):
    """A synthetic inbound support ticket."""

    ticket_id: str
    created_at: datetime
    customer_message: str = Field(min_length=1, max_length=MAX_CUSTOMER_MESSAGE_CHARACTERS)
    order_reference: str | None = None
    customer_reference: str | None = None

    @field_validator("ticket_id")
    @classmethod
    def _validate_ticket_id(cls, value: str) -> str:
        if not _TICKET_ID.fullmatch(value):
            raise ValueError("ticket_id must be 1-64 characters of A-Z, a-z, 0-9, '-' or '_'")
        return value

    @field_validator("order_reference")
    @classmethod
    def _validate_order_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not _ORDER_REFERENCE.fullmatch(value):
            raise ValueError("order_reference contains unsupported characters")
        return value

    @field_validator("customer_reference")
    @classmethod
    def _validate_customer_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not _CUSTOMER_REFERENCE.fullmatch(value):
            raise ValueError("customer_reference must look like CUS-001")
        return value


# --------------------------------------------------------------------------------------
# Triage
# --------------------------------------------------------------------------------------
class TicketClassification(StrictModel):
    domain: SupportDomain
    intent: str = Field(min_length=1, max_length=200)
    urgency: Urgency
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty_reason: str | None = None


class SentimentAssessment(StrictModel):
    """Sentiment is advisory: it shapes tone and priority, never authority."""

    label: SentimentLabel
    intensity: SentimentIntensity
    rationale_summary: str = Field(default="", max_length=400)


class EscalationDecision(StrictModel):
    required: bool = False
    reason_code: EscalationReason | None = None
    summary: str = ""
    recommended_human_action: str = ""


# --------------------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------------------
class SearchResult(StrictModel):
    title: str
    url: HttpUrl
    snippet: str = ""
    rank: int = Field(ge=1)


class ScrapedEvidence(StrictModel):
    """Public web evidence. Always carries an EV- prefixed identifier."""

    evidence_id: str = Field(pattern=r"^EV-[0-9]{3,}$")
    source_url: HttpUrl
    title: str
    retrieved_at: datetime
    content: str
    content_hash: str = Field(min_length=8)


class OperationalEvidence(StrictModel):
    """Customer-specific operational record. Always carries an OP- prefixed identifier."""

    evidence_id: str = Field(pattern=r"^OP-[0-9]{3,}$")
    source_system: str
    record_type: str
    record_id: str
    retrieved_at: datetime
    facts: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------------------
class SupportDraft(StrictModel):
    issue_summary: str = Field(min_length=1, max_length=400)
    customer_response: str = Field(min_length=1, max_length=4000)
    troubleshooting_steps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class QAResult(StrictModel):
    decision: QADecision
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    escalation_reason: EscalationReason | None = None


class TroubleshootingArticle(StrictModel):
    """Reusable, customer-agnostic documentation. May cite only EV- evidence."""

    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = Field(min_length=1)
    source_evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# Tracing, auditing and human-in-the-loop
# --------------------------------------------------------------------------------------
class ToolCallRecord(StrictModel):
    run_id: str
    agent_name: str
    step_number: int
    tool_name: str
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    status: str
    detail: str = ""


class AgentRunRecord(StrictModel):
    run_id: str
    agent_name: str
    started_at: datetime
    finished_at: datetime | None = None
    step_count: int = 0
    tool_names: list[str] = Field(default_factory=list)
    status: str = "started"


class DelegationRecord(StrictModel):
    run_id: str
    specialist: str
    tool_name: str
    requested_at: datetime
    status: str
    resulting_state: WorkflowStatus


class HumanApprovalDecision(StrictModel):
    """Record of the single human-in-the-loop gate."""

    requested_action: str
    reason_code: EscalationReason
    approved: bool
    approver: str = "unattended"
    notes: str = ""
    decided_at: datetime


class StructuredError(StrictModel):
    """Shape written to errors.jsonl for every caught failure."""

    run_id: str
    error_category: str
    agent_name: str | None = None
    tool_name: str | None = None
    retryable: bool = False
    safe_message: str
    occurred_at: datetime


class AuditEvent(StrictModel):
    timestamp: datetime
    step: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class InteractionSummary(StrictModel):
    """The written summary of the support interaction (FY27 required artifact)."""

    ticket_id: str
    run_id: str
    domain: SupportDomain
    intent: str = ""
    urgency: Urgency | None = None
    sentiment_label: SentimentLabel | None = None
    sentiment_intensity: SentimentIntensity | None = None
    workflow_status: WorkflowStatus
    qa_decision: QADecision | None = None
    escalation: EscalationDecision = Field(default_factory=EscalationDecision)
    human_approval: HumanApprovalDecision | None = None
    revision_count: int = 0
    source_count: int = 0
    operational_source_count: int = 0
    delegations: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# Workflow state
# --------------------------------------------------------------------------------------
class WorkflowState(BaseModel):
    """Authoritative run state. Owned by the kernel; agents never mutate it directly."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    run_id: str
    current_state: WorkflowStatus
    ticket: SupportTicket
    classification: TicketClassification | None = None
    sentiment: SentimentAssessment | None = None
    escalation: EscalationDecision = Field(default_factory=EscalationDecision)
    search_results: list[SearchResult] = Field(default_factory=list)
    evidence: list[ScrapedEvidence] = Field(default_factory=list)
    operational_evidence: list[OperationalEvidence] = Field(default_factory=list)
    support_draft: SupportDraft | None = None
    qa_result: QAResult | None = None
    article: TroubleshootingArticle | None = None
    human_approval: HumanApprovalDecision | None = None
    revision_count: int = 0
    audit_events: list[AuditEvent] = Field(default_factory=list)
    delegations: list[DelegationRecord] = Field(default_factory=list)
    error_summary: str | None = None
