"""QA tools: deterministic verification checks the QA agent must run.

The pattern preserved from the previous implementation and kept deliberately: the
submit tool refuses to accept an `approve` decision while any deterministic check has
failed, and refuses to submit at all until every required check has run. Deterministic
authority is therefore enforced at the tool boundary, not by prompt discipline.

Structured arguments are declared `Any` and normalised by `json_args`, because a model
sends a native JSON array as often as a JSON string and a hard `str` type would reject
the native form before the tool ever runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from smolagents import tool

from ..evidence_registry import EvidenceRegistry
from ..schemas import EscalationReason, QADecision, QAResult, SupportDraft
from ..services.content_validation import (
    contains_restricted_claim,
    requests_secret,
)
from ..services.safety_rules import contains_sensitive_data
from .json_args import ToolArgumentError, coerce_json_string_list

#: Every check that must run before a QA decision may be submitted.
REQUIRED_CHECKS = (
    "check_evidence_grounding",
    "check_restricted_claims",
    "check_sensitive_data",
    "check_operational_claims",
)


@dataclass
class QAWorkspace:
    """Mutable state shared by the QA tools during a single agent run."""

    draft: SupportDraft | None = None
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    revision_instructions: list[str] = field(default_factory=list)
    result: QAResult | None = None
    submitted: bool = False

    def reset(self, draft: SupportDraft) -> None:
        self.draft = draft
        self.checks.clear()
        self.revision_instructions.clear()
        self.result = None
        self.submitted = False

    @property
    def blocking_issues(self) -> list[str]:
        """Issues from failed deterministic checks. These cannot be argued away."""
        issues: list[str] = []
        for outcome in self.checks.values():
            if not outcome.get("passed", False):
                issues.extend(str(item) for item in outcome.get("issues", []))
        return issues


def _draft_text(draft: SupportDraft) -> str:
    return "\n".join(
        [
            draft.issue_summary,
            draft.customer_response,
            *draft.troubleshooting_steps,
            *draft.unresolved_questions,
            *draft.limitations,
        ]
    )


def build_qa_tools(
    workspace: QAWorkspace,
    *,
    registry: EvidenceRegistry,
) -> list[Any]:
    """Create the QA tool set bound to one run's workspace and evidence registry."""

    def _record(name: str, *, passed: bool, issues: list[str], **extra: Any) -> str:
        outcome = {"passed": passed, "issues": issues, **extra}
        workspace.checks[name] = outcome
        return json.dumps(outcome)

    @tool
    def check_evidence_grounding(reason: str) -> str:
        """Verify every evidence identifier the draft cites was actually issued this run.

        Args:
            reason: A short note on why grounding is being verified.
        """
        del reason
        if workspace.draft is None:
            return _record("check_evidence_grounding", passed=False, issues=["No draft to review."])

        unknown = registry.unknown_ids(workspace.draft.evidence_ids)
        issues = [f"Draft cites an evidence identifier that was never issued: {item}" for item in unknown]

        has_steps = any(step.strip() for step in workspace.draft.troubleshooting_steps)
        if has_steps and not workspace.draft.evidence_ids:
            issues.append("Troubleshooting steps are present but no evidence is cited.")

        return _record(
            "check_evidence_grounding",
            passed=not issues,
            issues=issues,
            known_evidence_ids=sorted(registry.known_ids),
        )

    @tool
    def check_restricted_claims(reason: str) -> str:
        """Verify the draft does not claim or promise a restricted action.

        Restricted actions are refunds, credits, payments, policy exceptions and any
        modification of an order or account.

        Args:
            reason: A short note on why restricted claims are being checked.
        """
        del reason
        if workspace.draft is None:
            return _record("check_restricted_claims", passed=False, issues=["No draft to review."])

        text = _draft_text(workspace.draft)
        issues = []
        if contains_restricted_claim(text):
            issues.append("The draft claims or promises a restricted action was performed.")
        return _record("check_restricted_claims", passed=not issues, issues=issues)

    @tool
    def check_sensitive_data(reason: str) -> str:
        """Verify the draft contains no credentials and asks for none.

        Args:
            reason: A short note on why sensitive data is being checked.
        """
        del reason
        if workspace.draft is None:
            return _record("check_sensitive_data", passed=False, issues=["No draft to review."])

        text = _draft_text(workspace.draft)
        issues = []
        if contains_sensitive_data(text):
            issues.append("The draft contains credential-like or full payment data.")
        if requests_secret(text):
            issues.append("The draft asks the customer to disclose a credential.")
        return _record("check_sensitive_data", passed=not issues, issues=issues)

    @tool
    def check_operational_claims(reason: str) -> str:
        """Verify customer-specific claims are backed by OP- operational evidence.

        Public EV- evidence may support general guidance, but it can never establish
        the status of a specific order, shipment, return, account or checkout attempt.

        Args:
            reason: A short note on why operational grounding is being checked.
        """
        del reason
        if workspace.draft is None:
            return _record("check_operational_claims", passed=False, issues=["No draft to review."])

        operational_ids = registry.operational_ids()
        cited_operational = {
            item for item in workspace.draft.evidence_ids if item.startswith("OP-")
        }
        issues = [
            f"Draft cites operational evidence that does not exist: {item}"
            for item in sorted(cited_operational - operational_ids)
        ]

        return _record(
            "check_operational_claims",
            passed=not issues,
            issues=issues,
            operational_evidence_available=sorted(operational_ids),
        )

    @tool
    def request_support_revision(instructions_json: Any) -> str:
        """Record specific, actionable revision instructions for the Support Agent.

        Accepts a JSON array of strings, for example ["Cite the evidence used."].

        Args:
            instructions_json: A JSON array of instruction strings.
        """
        try:
            instructions = coerce_json_string_list(
                instructions_json, field="instructions_json", allow_empty=False
            )
        except ToolArgumentError as exc:
            return json.dumps({"status": "rejected", "reason": str(exc)})

        workspace.revision_instructions = instructions
        return json.dumps({"status": "recorded", "instructions": instructions})

    @tool
    def submit_qa_decision(decision: str, issues_json: Any) -> str:
        """Submit the final QA decision. Call this exactly once, at the end.

        A decision of "approve" is refused while any deterministic check has failed.

        Args:
            decision: One of "approve", "revise" or "escalate".
            issues_json: A JSON array of issue strings; use [] when there are none.
        """
        missing = sorted(set(REQUIRED_CHECKS) - set(workspace.checks))
        if missing:
            return json.dumps(
                {"status": "rejected", "reason": f"These required checks have not run: {missing}"}
            )

        try:
            decision_value = QADecision(str(decision).strip().casefold())
        except ValueError:
            return json.dumps(
                {"status": "rejected", "reason": 'decision must be "approve", "revise" or "escalate".'}
            )

        try:
            issues = coerce_json_string_list(issues_json, field="issues_json")
        except ToolArgumentError:
            issues = []

        blockers = workspace.blocking_issues

        if decision_value == QADecision.APPROVE and blockers:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": "Deterministic checks failed, so the draft cannot be approved.",
                    "blocking_issues": blockers,
                }
            )

        if decision_value == QADecision.REVISE and not (
            workspace.revision_instructions or issues
        ):
            return json.dumps(
                {"status": "rejected", "reason": "A revision requires specific instructions."}
            )

        combined = list(dict.fromkeys([*issues, *blockers]))
        escalation_reason = (
            _escalation_reason_for(workspace) if decision_value == QADecision.ESCALATE else None
        )

        workspace.result = QAResult(
            decision=decision_value,
            issues=combined,
            revision_instructions=workspace.revision_instructions,
            escalation_reason=escalation_reason,
        )
        workspace.submitted = True

        return json.dumps(
            {
                "status": "submitted",
                "decision": decision_value.value,
                "issues": combined,
                "escalation_reason": escalation_reason.value if escalation_reason else None,
            }
        )

    return [
        check_evidence_grounding,
        check_restricted_claims,
        check_sensitive_data,
        check_operational_claims,
        request_support_revision,
        submit_qa_decision,
    ]


def _escalation_reason_for(workspace: QAWorkspace) -> EscalationReason:
    """Derive the *specific* escalation reason from which deterministic check failed.

    The previous implementation recorded every QA escalation as `qa_failure`, which
    erased the information a human reviewer actually needs.
    """
    checks = workspace.checks
    if not checks.get("check_sensitive_data", {}).get("passed", True):
        return EscalationReason.SENSITIVE_DATA
    if not checks.get("check_restricted_claims", {}).get("passed", True):
        return EscalationReason.FINANCIAL_AUTHORIZATION
    if not checks.get("check_operational_claims", {}).get("passed", True):
        return EscalationReason.INSUFFICIENT_EVIDENCE
    if not checks.get("check_evidence_grounding", {}).get("passed", True):
        return EscalationReason.INSUFFICIENT_EVIDENCE
    return EscalationReason.QA_FAILURE
