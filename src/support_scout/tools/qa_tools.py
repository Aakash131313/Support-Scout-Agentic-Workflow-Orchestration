"""QA tools: deterministic verification checks the QA agent must run.

The pattern preserved from the previous implementation and kept deliberately: the
submit tool refuses to accept an `approve` decision while any deterministic check has
failed, and refuses to submit at all until every required check has run. Deterministic
authority is therefore enforced at the tool boundary, not by prompt discipline.

Structured arguments are declared `Any` and normalised by `json_args`, because a model
sends a native JSON array as often as a JSON string and a hard `str` type would reject
the native form before the tool ever runs.

Single-submission enforcement
-----------------------------
`submit_qa_decision` is idempotent. In a live run it was called eleven times: the model
submitted `revise`, received `{"status": "submitted"}`, and -- having no signal that it
was finished -- called it again, eventually switching the decision to `escalate` on the
sixth call. Each call silently overwrote the previous result, so the last one silently
won, and the loop burned roughly 41k input tokens before hitting a rate limit and the
agent's step ceiling.

The first decision is now final. Repeat calls return `already_submitted` with the
decision that was recorded. Note that a *rejected* call is not a submission: the
workspace is untouched and the agent is expected to call again with a valid decision.

Operational grounding
---------------------
`check_operational_claims` previously inspected only the identifiers in `evidence_ids`,
asking "are the OP- ids you cited real?". A draft citing no OP- ids at all therefore
passed vacuously, no matter what the customer response asserted -- so a reply saying
"your order is in transit and will arrive Thursday", backed by nothing but public web
sources, was approved. That contradicted both the check's own name and the mission's
"evidence before confidence" principle.

It now also reads the customer response and requires an `OP-` citation whenever the
reply states this customer's concrete operational status. That rule is satisfiable in
every case because the support tools register a confirmed absence as `OP-` evidence:
if an operational tool was called at all, there is an identifier to cite.

Unwinnable revisions
--------------------
A revision must be achievable. Batch runs showed tickets escalating as
`revision_limit_exceeded` after QA requested changes twice for reasons its own tools
had already disproved -- "operational claims are not backed by valid OP- evidence" on a
draft citing OP-001 and OP-002, while `check_operational_claims` had returned
`passed: true`. The support agent resubmitted the same citations because there was
nothing to fix, and the budget ran out.

The tool guarded one direction only: it refused `approve` while checks failed, but
placed no burden on `revise`. It now refuses a revision whose stated reason is about
operational grounding when that exact check has passed.

That test is deliberately *topical* rather than phrase-based. An earlier version
enumerated negative phrasings ("not backed by", "unsupported by") and was defeated the
very next run by "need to be supported by valid operational evidence" and "lacks proper
citation of operational evidence" -- the fifth time an enumerated word list in this
codebase was outrun by paraphrase. The rule now asks what the objection is *about*:
if it concerns evidence or citation AND concerns operational status, while the
operational check passed, it contradicts a verified result.

Editorial revisions -- tone, clarity, a missing step, even a request to cite *public*
guidance -- are unaffected, and `escalate` remains available for a concern the tools
cannot see.
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
    find_operational_claims,
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

#: Vocabulary indicating an objection is about evidential support.
_EVIDENCE_TERMS: tuple[str, ...] = (
    "evidence",
    "citation",
    "cite",
    "cited",
    "citing",
    "backed",
    "support",
    "grounded",
    "substantiat",
)

#: Vocabulary indicating an objection is about *operational* status specifically,
#: as opposed to public guidance. Both families must appear for the objection to
#: contradict a passing `check_operational_claims`.
_OPERATIONAL_TERMS: tuple[str, ...] = (
    "operational",
    "op-",
    "order status",
    "return status",
    "refund status",
    "shipment",
    "shipping status",
    "delivery status",
    "tracking",
    "account status",
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


def _is_operational_grounding_objection(statement: str) -> bool:
    """True when a statement objects to the operational grounding of a draft.

    Topical rather than phrase-based: it asks whether the objection concerns
    evidential support AND concerns operational status, in any wording. A complaint
    about citing *public* guidance mentions evidence but not operational status, so it
    is not matched.
    """
    lowered = str(statement).casefold()
    return any(term in lowered for term in _EVIDENCE_TERMS) and any(
        term in lowered for term in _OPERATIONAL_TERMS
    )


def _contradicts_operational_check(statements: list[str]) -> str | None:
    """Return the first operational-grounding objection, or None."""
    for statement in statements:
        if _is_operational_grounding_objection(statement):
            return str(statement)
    return None


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

        Two rules are enforced. Every OP- identifier the draft cites must be real, and
        any statement of this customer's concrete operational status -- shipped,
        delivered, in transit, arriving on a given day -- must be accompanied by an
        OP- citation. Public EV- evidence can support general guidance but can never
        establish the status of one specific order, shipment, return or account.

        When this check passes, the draft's operational grounding has been verified
        and is not a valid reason to request a revision. Approve, or give a different
        concrete problem.

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

        # A reply may state this customer's operational status only when it cites
        # operational evidence. Without this the check passed vacuously whenever no
        # OP- identifier was cited, regardless of what the response asserted.
        unsupported_claims = find_operational_claims(workspace.draft.customer_response)
        if unsupported_claims and not cited_operational:
            issues.append(
                "The draft states this customer's operational status but cites no OP- "
                "evidence. Either cite the operational record the statement is based "
                f'on, or remove the claim. Unsupported statement: "{unsupported_claims[0][:160]}"'
            )

        return _record(
            "check_operational_claims",
            passed=not issues,
            issues=issues,
            operational_evidence_available=sorted(operational_ids),
            operational_evidence_cited=sorted(cited_operational),
            unsupported_operational_claims=unsupported_claims[:3],
        )

    @tool
    def request_support_revision(instructions_json: Any) -> str:
        """Record specific, actionable revision instructions for the Support Agent.

        Accepts a JSON array of strings, for example ["Cite the evidence used."].

        Args:
            instructions_json: A JSON array of instruction strings.
        """
        if workspace.submitted:
            return json.dumps(
                {
                    "status": "already_submitted",
                    "reason": (
                        "A QA decision has already been submitted for this review. "
                        "Revision instructions can no longer be changed."
                    ),
                }
            )

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
        A decision of "revise" is refused when the operational grounding check passed
        and the stated reason is about operational evidence, because that has already
        been verified; approve instead, or give a different concrete problem.

        The first decision submitted is final: calling this again returns
        "already_submitted" and does not change the recorded outcome.

        Args:
            decision: One of "approve", "revise" or "escalate".
            issues_json: A JSON array of issue strings; use [] when there are none.
        """
        # The first decision wins. A repeat call is the agent failing to notice it is
        # done, so tell it plainly rather than silently overwriting the result.
        if workspace.submitted and workspace.result is not None:
            return json.dumps(
                {
                    "status": "already_submitted",
                    "reason": (
                        "A decision was already submitted for this review and cannot be "
                        "changed. Your work here is complete; stop calling this tool."
                    ),
                    "decision": workspace.result.decision.value,
                    "issues": list(workspace.result.issues),
                    "escalation_reason": (
                        workspace.result.escalation_reason.value
                        if workspace.result.escalation_reason
                        else None
                    ),
                }
            )

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

        # A revision must be achievable. When the operational grounding check passed,
        # an objection about operational evidence contradicts a verified result and the
        # support agent has nothing it can change -- it resubmits the same citations
        # and the revision budget is spent for nothing.
        operational_check = workspace.checks.get("check_operational_claims", {})
        if (
            decision_value == QADecision.REVISE
            and not blockers
            and operational_check.get("passed", False)
        ):
            contradicting = _contradicts_operational_check(
                [*issues, *workspace.revision_instructions]
            )
            if contradicting is not None:
                cited = operational_check.get("operational_evidence_cited", [])
                return json.dumps(
                    {
                        "status": "rejected",
                        "reason": (
                            "check_operational_claims passed: this draft's operational "
                            f"statements are already grounded in {cited or 'the cited evidence'}. "
                            "A revision asking for operational evidence cannot be "
                            "satisfied, because the evidence is present and verified."
                        ),
                        "contradicting_issue": contradicting[:200],
                        "operational_evidence_cited": cited,
                        "next_step": (
                            "The expected decision here is \"approve\". Choose \"revise\" "
                            "only for a different, concrete problem such as tone, "
                            "clarity, or a missing step. Choose \"escalate\" only if a "
                            "human must see something the checks cannot detect."
                        ),
                    }
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
