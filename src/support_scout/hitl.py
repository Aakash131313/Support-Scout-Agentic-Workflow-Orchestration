"""The single human-in-the-loop gate.

SupportScout is customer-facing, so the flow is interrupted exactly once and only
for a restricted action: financial authorization, policy exception or suspected
account compromise. Everything else escalates silently to a human queue without
blocking the customer.

The gate is invoked by the deterministic kernel, not by the model, so an agent
cannot decide to skip it.

Prompt design note: the operator is NOT approving the restricted action itself.
SupportScout can never issue a refund, payment or policy exception regardless of the
answer given here. The operator is deciding only whether the agents may draft a reply.
The prompt says so explicitly, because an ambiguous gate is a dangerous gate.
"""
from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .logging_config import redact
from .schemas import EscalationReason, HumanApprovalDecision

#: Reasons that require a human decision before the workflow may continue.
RESTRICTED_ACTION_REASONS = frozenset(
    {
        EscalationReason.FINANCIAL_AUTHORIZATION,
        EscalationReason.POLICY_EXCEPTION,
        EscalationReason.ACCOUNT_COMPROMISE,
    }
)

#: Plain-language explanation of what each restricted reason means for the operator.
REASON_EXPLANATIONS: dict[EscalationReason, str] = {
    EscalationReason.FINANCIAL_AUTHORIZATION: (
        "The customer is asking for a refund, credit or payment decision."
    ),
    EscalationReason.POLICY_EXCEPTION: (
        "The customer is asking for a policy, deadline or eligibility rule to be waived."
    ),
    EscalationReason.ACCOUNT_COMPROMISE: (
        "The customer may be reporting unauthorized access to their account."
    ),
}

#: What SupportScout still cannot do, whatever the operator answers.
REASON_LIMITS: dict[EscalationReason, str] = {
    EscalationReason.FINANCIAL_AUTHORIZATION: (
        "No refund, credit or payment will be issued under either answer."
    ),
    EscalationReason.POLICY_EXCEPTION: (
        "No policy exception will be granted under either answer."
    ),
    EscalationReason.ACCOUNT_COMPROMISE: (
        "No account change will be made under either answer."
    ),
}


def requires_human_approval(reason: EscalationReason | None) -> bool:
    """True when the reason describes a restricted action, not a routine escalation."""
    return reason in RESTRICTED_ACTION_REASONS


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ApprovalRequest:
    """Everything an operator needs to decide, in one object."""

    ticket_id: str
    customer_message: str
    reason: EscalationReason
    action: str
    domain: str | None = None

    @property
    def explanation(self) -> str:
        return REASON_EXPLANATIONS.get(self.reason, "This request needs human judgement.")

    @property
    def limit(self) -> str:
        return REASON_LIMITS.get(
            self.reason, "No restricted action will be performed under either answer."
        )

    def render(self, width: int = 78) -> str:
        """Render the decision screen an operator actually reads."""
        rule = "=" * width
        thin = "-" * width

        message = redact(self.customer_message.strip())
        wrapped = "\n".join(
            textwrap.fill(line, width=width - 4, initial_indent="  ", subsequent_indent="  ")
            for line in message.splitlines()
            if line.strip()
        ) or "  (no message text)"

        domain = self.domain or "not yet classified (safety screening runs before triage)"

        return (
            f"\n{rule}\n"
            f"{'HUMAN APPROVAL REQUIRED'.center(width)}\n"
            f"{rule}\n\n"
            f"  Ticket   : {self.ticket_id}\n"
            f"  Domain   : {domain}\n"
            f"  Trigger  : {self.reason.value}\n"
            f"  Meaning  : {self.explanation}\n\n"
            f"  WHAT THE CUSTOMER WROTE\n"
            f"{thin}\n"
            f"{wrapped}\n"
            f"{thin}\n\n"
            f"  YOU ARE NOT APPROVING THE CUSTOMER'S REQUEST.\n"
            f"  {self.limit}\n"
            f"  That decision stays with an authorized agent either way.\n\n"
            f"  You are deciding only whether SupportScout may draft a reply:\n\n"
            f"    [y]  Continue  - the agents research and draft an evidence-grounded\n"
            f"                     reply explaining the process and next steps.\n"
            f"    [N]  Escalate  - stop now, write an escalation record, and hand the\n"
            f"                     ticket to a human queue untouched.\n\n"
            f"{rule}\n"
        )


class ApprovalGate(Protocol):
    """Contract for every human-in-the-loop implementation."""

    def request(self, *, request: ApprovalRequest) -> HumanApprovalDecision:
        ...


class AutoDenyGate:
    """Default unattended behaviour: never approve a restricted action.

    Denial is the safe default. The workflow escalates to a human queue instead of
    proceeding, which satisfies 'human authority' without needing an operator present.
    """

    approver = "unattended-policy"

    def request(self, *, request: ApprovalRequest) -> HumanApprovalDecision:
        return HumanApprovalDecision(
            requested_action=request.action,
            reason_code=request.reason,
            approved=False,
            approver=self.approver,
            notes="No human reviewer attached; restricted action denied by default policy.",
            decided_at=_now(),
        )


class AutoApproveGate:
    """Non-interactive approval used by CI and the offline test suite."""

    approver = "automated-test"

    def request(self, *, request: ApprovalRequest) -> HumanApprovalDecision:
        return HumanApprovalDecision(
            requested_action=request.action,
            reason_code=request.reason,
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

    def request(self, *, request: ApprovalRequest) -> HumanApprovalDecision:
        self.stream.write(request.render())
        self.stream.flush()

        try:
            answer = self.prompt_input("Allow SupportScout to draft a reply? [y/N]: ")
            answer = answer.strip().casefold()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        approved = answer in {"y", "yes"}

        self.stream.write(
            "\n  -> Drafting a reply. No restricted action will be performed.\n\n"
            if approved
            else "\n  -> Escalating to a human queue. No reply will be sent automatically.\n\n"
        )
        self.stream.flush()

        return HumanApprovalDecision(
            requested_action=request.action,
            reason_code=request.reason,
            approved=approved,
            approver=self.approver,
            notes=(
                "Operator allowed automated drafting to continue."
                if approved
                else "Operator escalated to a human queue."
            ),
            decided_at=_now(),
        )


def build_gate(*, require_approval: bool, auto_approve: bool, interactive: bool) -> ApprovalGate:
    """Select the gate implementation for a run."""
    if auto_approve:
        return AutoApproveGate()
    if require_approval and interactive:
        return InteractiveApprovalGate()
    return AutoDenyGate()
