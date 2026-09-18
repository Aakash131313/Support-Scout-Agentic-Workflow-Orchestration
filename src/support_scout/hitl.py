"""The single human-in-the-loop gate.

SupportScout is customer-facing, so the flow is interrupted exactly once and only
for a restricted action: financial authorization, policy exception, account
modification or suspected account compromise. Everything else escalates silently
to a human queue without blocking the customer.

The gate is invoked by the deterministic kernel, not by the model, so an agent
cannot decide to skip it.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Protocol

from .schemas import EscalationReason, HumanApprovalDecision

#: Reasons that require a human decision before the workflow may continue.
RESTRICTED_ACTION_REASONS = frozenset(
    {
        EscalationReason.FINANCIAL_AUTHORIZATION,
        EscalationReason.POLICY_EXCEPTION,
        EscalationReason.ACCOUNT_COMPROMISE,
    }
)


def requires_human_approval(reason: EscalationReason | None) -> bool:
    """True when the reason describes a restricted action, not a routine escalation."""
    return reason in RESTRICTED_ACTION_REASONS


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalGate(Protocol):
    """Contract for every human-in-the-loop implementation."""

    def request(self, *, action: str, reason: EscalationReason, context: str) -> HumanApprovalDecision:
        ...


class AutoDenyGate:
    """Default unattended behaviour: never approve a restricted action.

    Denial is the safe default. The workflow escalates to a human queue instead of
    proceeding, which satisfies 'human authority' without needing an operator present.
    """

    approver = "unattended-policy"

    def request(self, *, action: str, reason: EscalationReason, context: str) -> HumanApprovalDecision:
        return HumanApprovalDecision(
            requested_action=action,
            reason_code=reason,
            approved=False,
            approver=self.approver,
            notes="No human reviewer attached; restricted action denied by default policy.",
            decided_at=_now(),
        )


class AutoApproveGate:
    """Non-interactive approval used by CI and the offline test suite."""

    approver = "automated-test"

    def request(self, *, action: str, reason: EscalationReason, context: str) -> HumanApprovalDecision:
        return HumanApprovalDecision(
            requested_action=action,
            reason_code=reason,
            approved=True,
            approver=self.approver,
            notes="Approved automatically because --auto-approve was supplied.",
            decided_at=_now(),
        )


class InteractiveApprovalGate:
    """Prompts a human operator on the terminal for a single yes/no decision."""

    approver = "interactive-operator"

    def __init__(self, stream=None, prompt_input=input) -> None:
        self.stream = stream or sys.stdout
        self.prompt_input = prompt_input

    def request(self, *, action: str, reason: EscalationReason, context: str) -> HumanApprovalDecision:
        self.stream.write(
            "\n"
            "==================== HUMAN APPROVAL REQUIRED ====================\n"
            f"Restricted action : {action}\n"
            f"Reason code       : {reason.value}\n"
            f"Context           : {context}\n"
            "SupportScout cannot perform this action on its own authority.\n"
            "Approve automated handling to continue, or deny to escalate.\n"
            "=================================================================\n"
        )
        self.stream.flush()
        try:
            answer = self.prompt_input("Approve? [y/N]: ").strip().casefold()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        approved = answer in {"y", "yes"}
        return HumanApprovalDecision(
            requested_action=action,
            reason_code=reason,
            approved=approved,
            approver=self.approver,
            notes="Operator approved." if approved else "Operator denied; escalating.",
            decided_at=_now(),
        )


def build_gate(*, require_approval: bool, auto_approve: bool, interactive: bool) -> ApprovalGate:
    """Select the gate implementation for a run."""
    if auto_approve:
        return AutoApproveGate()
    if require_approval and interactive:
        return InteractiveApprovalGate()
    return AutoDenyGate()
