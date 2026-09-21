"""The deterministic workflow kernel.

The orchestrator agent *chooses* what to do next. The kernel decides whether that is
allowed. Every state change, every delegation record, every escalation and the single
human-in-the-loop gate run through here, so no prompt change can bypass them.

Three defects from the previous implementation are fixed here explicitly:

* Escalation was recorded and then ignored: triage always advanced to `triaged`
  regardless of the escalation decision, so a refund-approval ticket continued into
  research and drafting. `apply_triage` now escalates before anything else can run.
* An escalated run could never finalize, so no artifacts were written at all. The
  kernel now treats escalation as a legitimate finalizable terminal state.
* Every QA escalation was recorded as `qa_failure`. The specific reason is now
  preserved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..exceptions import ExecutionBudgetExceeded, WorkflowError
from ..hitl import ApprovalGate, ApprovalRequest, AutoDenyGate, requires_human_approval
from ..schemas import (
    AuditEvent,
    DelegationRecord,
    EscalationDecision,
    EscalationReason,
    QADecision,
    QAResult,
    SupportDraft,
    TERMINAL_STATUSES,
    TicketClassification,
    TroubleshootingArticle,
    WorkflowState,
    WorkflowStatus,
)

_ALLOWED_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.RECEIVED: {WorkflowStatus.VALIDATED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED},
    WorkflowStatus.VALIDATED: {WorkflowStatus.TRIAGED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED},
    WorkflowStatus.TRIAGED: {WorkflowStatus.RESEARCHED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED},
    WorkflowStatus.RESEARCHED: {WorkflowStatus.DRAFTED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED},
    WorkflowStatus.DRAFTED: {
        WorkflowStatus.QA_APPROVED,
        WorkflowStatus.QA_REVISION_REQUESTED,
        WorkflowStatus.ESCALATED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.QA_REVISION_REQUESTED: {
        WorkflowStatus.DRAFTED,
        WorkflowStatus.ESCALATED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.QA_APPROVED: {WorkflowStatus.DOCUMENTED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED},
    WorkflowStatus.DOCUMENTED: {WorkflowStatus.COMPLETED, WorkflowStatus.ESCALATED, WorkflowStatus.FAILED},
}

#: States from which each specialist delegation may legally run.
#: Support appears twice because a QA-requested revision re-enters drafting.
REQUIRED_STATES_FOR_SPECIALIST: dict[str, set[WorkflowStatus]] = {
    "triage": {WorkflowStatus.VALIDATED},
    "research": {WorkflowStatus.TRIAGED},
    "support": {WorkflowStatus.RESEARCHED, WorkflowStatus.QA_REVISION_REQUESTED},
    "qa": {WorkflowStatus.DRAFTED},
    "documentation": {WorkflowStatus.QA_APPROVED},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowKernel:
    """Owns workflow state, transition legality, budgets, escalation and the HITL gate."""

    def __init__(
        self,
        state: WorkflowState,
        *,
        logger: Any,
        approval_gate: ApprovalGate | None = None,
        max_revisions: int = 1,
        max_total_tool_calls: int = 40,
        max_delegation_failures: int = 2,
    ) -> None:
        self.state = state
        self.logger = logger
        self.approval_gate = approval_gate or AutoDenyGate()
        self.max_revisions = max_revisions
        self.max_total_tool_calls = max_total_tool_calls
        self.max_delegation_failures = max_delegation_failures
        self.products: dict[str, Any] = {}
        self.finalized = False
        self.tool_call_count = 0
        self.delegation_failure_counts: dict[str, int] = {}

    # -- audit -------------------------------------------------------------------
    def audit(self, step: str, status: str, details: dict[str, Any] | None = None) -> None:
        self.state.audit_events.append(
            AuditEvent(timestamp=_now(), step=step, status=status, details=details or {})
        )

    # -- budgets -----------------------------------------------------------------
    def count_tool_call(self, tool_name: str) -> None:
        """Track total tool usage and stop a runaway agent loop."""
        self.tool_call_count += 1
        if self.tool_call_count > self.max_total_tool_calls:
            raise ExecutionBudgetExceeded(
                f"Run exceeded the maximum of {self.max_total_tool_calls} tool calls"
            )

    # -- transitions -------------------------------------------------------------
    def transition(self, target: WorkflowStatus) -> WorkflowStatus:
        """Move to `target` when the transition is legal; raise otherwise."""
        current = self.state.current_state

        if current in TERMINAL_STATUSES:
            self.logger.state_transition(current.value, target.value, accepted=False)
            raise WorkflowError(f"Terminal workflow cannot transition from {current.value}")

        if target not in _ALLOWED_TRANSITIONS.get(current, set()):
            self.logger.state_transition(current.value, target.value, accepted=False)
            raise WorkflowError(f"Invalid workflow transition: {current.value} -> {target.value}")

        self.state.current_state = target
        self.logger.state_transition(current.value, target.value, accepted=True)
        self.audit("transition", "succeeded", {"from": current.value, "to": target.value})
        return target

    # -- escalation --------------------------------------------------------------
    def escalate(
        self,
        reason: EscalationReason,
        *,
        summary: str = "",
        recommended_action: str = "",
    ) -> EscalationDecision:
        """Terminate the run for human review, preserving the specific reason."""
        decision = EscalationDecision(
            required=True,
            reason_code=reason,
            summary=summary or "This request requires human review.",
            recommended_human_action=recommended_action
            or "An authorized specialist must review the sanitized ticket context.",
        )
        self.state.escalation = decision

        if self.state.current_state not in TERMINAL_STATUSES:
            self.state.current_state = WorkflowStatus.ESCALATED
            self.logger.state_transition(
                self.state.current_state.value, WorkflowStatus.ESCALATED.value, accepted=True
            )

        self.audit("escalation", "succeeded", {"reason_code": reason.value})
        self.logger.insight(
            "escalation",
            {"Reason": reason.value, "Recommended action": decision.recommended_human_action},
        )
        return decision

    def fail(self, error_category: str) -> None:
        """Terminate the run as failed without leaking the underlying exception text."""
        if self.state.current_state not in TERMINAL_STATUSES:
            self.state.current_state = WorkflowStatus.FAILED
        self.state.error_summary = error_category
        self.audit("workflow", "failed", {"error_category": error_category})

    # -- human in the loop -------------------------------------------------------
    def request_human_approval(self, reason: EscalationReason, *, action: str) -> bool:
        """Run the single HITL gate. Returns True only when a human approves.

        Called by the kernel rather than by an agent, so the model cannot skip it.
        The gate receives the full ticket context because an operator cannot decide
        responsibly about a request they cannot read.
        """
        previous_state = self.state.current_state
        self.state.current_state = WorkflowStatus.AWAITING_HUMAN_APPROVAL

        decision = self.approval_gate.request(
            request=ApprovalRequest(
                ticket_id=self.state.ticket.ticket_id,
                customer_message=self.state.ticket.customer_message,
                reason=reason,
                action=action,
                domain=(
                    self.state.classification.domain.value
                    if self.state.classification
                    else None
                ),
            )
        )

        self.state.human_approval = decision
        self.state.current_state = previous_state
        self.logger.human_decision(
            action=action,
            reason_code=reason.value,
            approved=decision.approved,
            approver=decision.approver,
        )
        self.audit(
            "human_approval",
            "approved" if decision.approved else "denied",
            {"reason_code": reason.value, "approver": decision.approver},
        )
        return decision.approved

    # -- delegation products -----------------------------------------------------
    def require_state_for(self, specialist: str) -> None:
        """Reject a delegation issued from the wrong workflow state."""
        allowed = REQUIRED_STATES_FOR_SPECIALIST.get(specialist)
        if allowed is None:
            return
        current = self.state.current_state
        if current not in allowed:
            expected = " or ".join(sorted(status.value for status in allowed))
            raise WorkflowError(
                f"{specialist} delegation requires state {expected} "
                f"but the workflow is in '{current.value}'"
            )

    def record_delegation(self, specialist: str, tool_name: str, *, status: str) -> None:
        record = DelegationRecord(
            run_id=self.state.run_id,
            specialist=specialist,
            tool_name=tool_name,
            requested_at=_now(),
            status=status,
            resulting_state=self.state.current_state,
        )
        self.state.delegations.append(record)
        self.logger.delegation(
            specialist, tool_name, status=status, state=self.state.current_state.value
        )

    def has_delegated(self, specialist: str) -> bool:
        return any(record.specialist == specialist for record in self.state.delegations)

    def note_delegation_failure(self, specialist: str) -> int:
        """Increment and return the consecutive-failure streak for one specialist.

        A model may retry a failing delegation, but not forever. This streak is what
        `orchestration_tools._delegate` checks to force a deterministic escalation once
        the streak crosses `max_delegation_failures`, rather than trusting a prompt
        instruction alone to make the orchestrator stop retrying.
        """
        current = self.delegation_failure_counts.get(specialist, 0) + 1
        self.delegation_failure_counts[specialist] = current
        return current

    def note_delegation_success(self, specialist: str) -> None:
        """Reset a specialist's failure streak once it succeeds.

        Without this, a specialist that fails once, succeeds, and later fails again
        (for an unrelated reason, e.g. during a QA-requested revision) would inherit
        a stale count from its first attempt.
        """
        self.delegation_failure_counts[specialist] = 0

    # -- specialist results ------------------------------------------------------
    def apply_triage(
        self,
        *,
        classification: TicketClassification,
        sentiment: Any,
        escalation: EscalationDecision,
    ) -> WorkflowStatus:
        """Hydrate triage output and honour a mandatory escalation immediately."""
        self.state.classification = classification
        self.state.sentiment = sentiment
        self.products["triage"] = classification

        self.logger.insight(
            "triage",
            {
                "Domain": classification.domain.value,
                "Intent": classification.intent,
                "Urgency": classification.urgency.value,
                "Confidence": f"{classification.confidence:.2f}",
                "Sentiment": (
                    f"{sentiment.label.value} ({sentiment.intensity.value})"
                    if sentiment
                    else "not available"
                ),
            },
        )

        if escalation.required and escalation.reason_code is not None:
            reason = escalation.reason_code
            # Restricted actions get the one human gate; everything else escalates directly.
            if requires_human_approval(reason):
                approved = self.request_human_approval(
                    reason, action=f"Continue automated handling despite {reason.value}"
                )
                if not approved:
                    self.escalate(
                        reason,
                        summary=escalation.summary,
                        recommended_action=escalation.recommended_human_action,
                    )
                    return self.state.current_state
            else:
                self.escalate(
                    reason,
                    summary=escalation.summary,
                    recommended_action=escalation.recommended_human_action,
                )
                return self.state.current_state

        return self.transition(WorkflowStatus.TRIAGED)

    def apply_research(
        self,
        *,
        search_results: list[Any],
        evidence: list[Any],
        insufficient: bool,
        conflicting: bool,
    ) -> WorkflowStatus:
        """Hydrate research output and escalate when evidence cannot ground an answer."""
        self.state.search_results = list(search_results)
        self.state.evidence = list(evidence)
        self.products["research"] = evidence

        self.logger.insight(
            "research",
            {
                "Search results": len(search_results),
                "Evidence prepared": len(evidence),
                "Evidence IDs": ", ".join(item.evidence_id for item in evidence) or "none",
                "Insufficient": insufficient,
                "Conflict detected": conflicting,
            },
        )

        if insufficient:
            self.escalate(
                EscalationReason.INSUFFICIENT_EVIDENCE,
                summary="No reliable public guidance was retrieved.",
                recommended_action="Answer manually using internal knowledge sources.",
            )
            return self.state.current_state

        if conflicting:
            self.escalate(
                EscalationReason.CONFLICTING_EVIDENCE,
                summary="Retrieved sources materially disagree.",
                recommended_action="Confirm the authoritative policy before replying.",
            )
            return self.state.current_state

        return self.transition(WorkflowStatus.RESEARCHED)

    def apply_support(
        self, *, draft: SupportDraft, operational_evidence: list[Any]
    ) -> WorkflowStatus:
        """Hydrate the support draft and any operational evidence it gathered."""
        self.state.support_draft = draft
        if operational_evidence:
            self.state.operational_evidence = list(operational_evidence)
        self.products["support"] = draft

        self.logger.insight(
            "support",
            {
                "Issue": draft.issue_summary,
                "Evidence cited": ", ".join(draft.evidence_ids) or "none",
                "Steps": len(draft.troubleshooting_steps),
                "Operational records": len(operational_evidence),
            },
        )
        return self.transition(WorkflowStatus.DRAFTED)

    def apply_qa(self, *, result: QAResult) -> WorkflowStatus:
        """Apply the QA decision, including a bounded revision loop."""
        self.state.qa_result = result
        self.products["qa"] = result

        self.logger.insight(
            "qa",
            {
                "Decision": result.decision.value,
                "Issues": "; ".join(result.issues) or "none",
                "Revision": f"{self.state.revision_count}/{self.max_revisions}",
            },
        )

        if result.decision == QADecision.APPROVE:
            return self.transition(WorkflowStatus.QA_APPROVED)

        if result.decision == QADecision.REVISE:
            if self.state.revision_count >= self.max_revisions:
                self.escalate(
                    EscalationReason.REVISION_LIMIT_EXCEEDED,
                    summary="QA could not approve the draft within the revision limit.",
                    recommended_action="Write the customer response manually.",
                )
                return self.state.current_state
            self.state.revision_count += 1
            self.transition(WorkflowStatus.QA_REVISION_REQUESTED)
            return self.state.current_state

        # Escalate: preserve the *specific* reason QA identified.
        self.escalate(
            result.escalation_reason or EscalationReason.QA_FAILURE,
            summary="QA blocked the draft.",
            recommended_action="Review the QA issues before replying to the customer.",
        )
        return self.state.current_state

    def apply_documentation(self, *, article: TroubleshootingArticle) -> WorkflowStatus:
        self.state.article = article
        self.products["documentation"] = article
        self.logger.insight(
            "documentation",
            {
                "Title": article.title,
                "Cited sources": ", ".join(article.source_evidence_ids) or "none",
            },
        )
        return self.transition(WorkflowStatus.DOCUMENTED)

    # -- completion --------------------------------------------------------------
    def finalize(self) -> WorkflowStatus:
        """Finalize the run. Escalated runs finalize legitimately, they do not error."""
        if self.state.current_state == WorkflowStatus.ESCALATED:
            self.finalized = True
            self.audit("finalize", "escalated", {})
            return self.state.current_state

        if self.state.current_state != WorkflowStatus.DOCUMENTED:
            raise WorkflowError(
                "Workflow may be finalized only after documentation or escalation "
                f"(current state: {self.state.current_state.value})"
            )

        missing = [
            name
            for name, value in {
                "classification": self.state.classification,
                "support_draft": self.state.support_draft,
                "qa_result": self.state.qa_result,
                "article": self.state.article,
            }.items()
            if value is None
        ]
        if missing:
            raise WorkflowError(f"Workflow state is incomplete: {', '.join(missing)}")

        self.transition(WorkflowStatus.COMPLETED)
        self.finalized = True
        self.audit("finalize", "completed", {})
        return self.state.current_state

    # -- introspection -----------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Sanitized view of the run, returned to the orchestrator by its state tool."""
        return {
            "current_state": self.state.current_state.value,
            "delegations": [record.specialist for record in self.state.delegations],
            "products": sorted(self.products),
            "revision_count": self.state.revision_count,
            "max_revisions": self.max_revisions,
            "escalation_required": self.state.escalation.required,
            "escalation_reason": (
                self.state.escalation.reason_code.value
                if self.state.escalation.reason_code
                else None
            ),
            "public_evidence_ids": [item.evidence_id for item in self.state.evidence],
            "operational_evidence_ids": [
                item.evidence_id for item in self.state.operational_evidence
            ],
            "finalized": self.finalized,
        }
