"""Support specialist tools: read-only operational diagnostics plus draft submission.

The Support Agent decides *which* operational records are relevant. Nothing here runs
automatically. That is the core behavioural difference from the old deterministic
service, which fired every tool for every identifier it could regex out of the ticket.

Missing records return a structured `available: false` result rather than raising, so
the agent can reason about a genuine miss (for example an unknown order) instead of
having its loop killed by an exception.

Confirmed absences are evidence
-------------------------------
A lookup that returns "no such record" is a real operational finding: the query ran
against the operations system and the record does not exist. It is now registered as
`OP-` evidence in its own right, with `facts.available = false`.

Previously the not-found path returned early without registering anything, so a run
against an unknown order ended with an empty operational registry. The agent had
nothing citable for "I checked and could not find it", and QA could not tell an honest
report of an absence apart from an ungrounded guess. Registering the miss closes that
gap and is what makes QA's stricter operational-claim rule satisfiable: if an
operational tool was called at all, there is always an `OP-` identifier to cite.

`submit_support_draft` accepts the draft as either a JSON object or a JSON string; a
model sends both forms and a hard `str` type would reject the native object outright.
Its nested list fields are also normalised, because a live run showed the model
supplying a valid top-level object whose `troubleshooting_steps`, `unresolved_questions`
and `limitations` were bare strings rather than single-item lists.

`submit_support_draft` is idempotent, and it enforces the same citation rule QA will
apply. See the notes on each below.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from smolagents import tool

from ..evidence_registry import EvidenceRegistry
from ..exceptions import SupportDataClientError, SupportDataNotFound
from ..schemas import SupportDraft
from .json_args import ToolArgumentError, coerce_json_object, normalize_list_fields

#: SupportDraft fields the schema requires as lists. A model frequently sends a bare
#: string for these when there is exactly one item.
SUPPORT_DRAFT_LIST_FIELDS: tuple[str, ...] = (
    "troubleshooting_steps",
    "evidence_ids",
    "unresolved_questions",
    "limitations",
)


@dataclass
class SupportWorkspace:
    """Mutable state shared by the support tools during a single agent run."""

    draft: SupportDraft | None = None
    submitted: bool = False
    tools_attempted: list[str] = field(default_factory=list)
    records_unavailable: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.draft = None
        self.submitted = False
        self.tools_attempted.clear()
        self.records_unavailable.clear()


def _existing_operational_id(
    registry: EvidenceRegistry, record_type: str, record_id: str
) -> str | None:
    """Return the identifier already issued for this record, if there is one.

    `register_operational` returns None when a record duplicates one already stored,
    without saying which. The agent still needs an identifier it can cite, so the
    existing record is looked up rather than leaving the tool result without one.
    """
    for item in registry.operational_evidence:
        if item.record_type == record_type and item.record_id == record_id:
            return item.evidence_id
    return None


def _operational_lookup(
    workspace: SupportWorkspace,
    registry: EvidenceRegistry,
    *,
    tool_name: str,
    record_type: str,
    identifier: str,
    fetch: Callable[[str], dict[str, Any]],
) -> str:
    """Shared body for every read-only operational tool."""
    workspace.tools_attempted.append(tool_name)

    def _register_absence(reason: str) -> str:
        """Record a confirmed absence as citable operational evidence."""
        workspace.records_unavailable.append(f"{record_type}:{identifier}")
        record = registry.register_operational(
            record_type=record_type,
            record_id=identifier,
            facts={
                "available": False,
                "looked_up": identifier,
                "reason": reason,
            },
        )
        evidence_id = (
            record.evidence_id
            if record is not None
            else _existing_operational_id(registry, record_type, identifier)
        )
        return json.dumps(
            {
                "available": False,
                "evidence_id": evidence_id,
                "record_type": record_type,
                "record_id": identifier,
                "reason": reason,
                "guidance": (
                    "This confirmed absence is itself operational evidence. Cite "
                    f"{evidence_id} if your reply mentions that the record could not "
                    "be located."
                ),
            }
        )

    try:
        facts = fetch(identifier)
    except SupportDataNotFound:
        # A confirmed absence is a verified fact about this record, so it is
        # registered as citable operational evidence.
        return _register_absence("No such record exists in the operations system.")
    except SupportDataClientError as exc:
        # An outage is a fact about our own infrastructure, not about the customer's
        # record. Nothing was learned about the order, so nothing is registered; the
        # agent should degrade to public guidance rather than cite our downtime.
        workspace.records_unavailable.append(f"{record_type}:{identifier}")
        return json.dumps(
            {
                "available": False,
                "evidence_id": None,
                "record_type": record_type,
                "record_id": identifier,
                "reason": f"The operations service could not be reached: {exc}",
                "guidance": (
                    "This is a service outage, not a finding about the record, so it "
                    "is not evidence. Do not state anything about this customer's "
                    "order status; answer with general guidance instead."
                ),
            }
        )

    record = registry.register_operational(
        record_type=record_type,
        record_id=str(facts.get(f"{record_type}_id") or identifier),
        facts=facts,
    )
    if record is None:
        resolved_id = str(facts.get(f"{record_type}_id") or identifier)
        return json.dumps(
            {
                "available": True,
                "duplicate": True,
                "evidence_id": _existing_operational_id(registry, record_type, resolved_id),
                "record_type": record_type,
                "reason": "This record was already retrieved earlier in the run.",
            }
        )

    return json.dumps(
        {
            "available": True,
            "evidence_id": record.evidence_id,
            "record_type": record.record_type,
            "record_id": record.record_id,
            "facts": record.facts,
        },
        default=str,
    )


def build_support_tools(
    workspace: SupportWorkspace,
    *,
    registry: EvidenceRegistry,
    data_client: Any,
) -> list[Any]:
    """Create the support tool set bound to one run's workspace and data client."""

    @tool
    def get_order_status(order_id: str) -> str:
        """Look up the read-only status record for one order.

        If no such order exists, that confirmed absence is returned with its own
        evidence identifier, which you should cite when your reply mentions it.

        Args:
            order_id: An order identifier such as ORD-1001.
        """
        return _operational_lookup(
            workspace,
            registry,
            tool_name="get_order_status",
            record_type="order",
            identifier=order_id,
            fetch=data_client.get_order,
        )

    @tool
    def get_shipment_status(order_id: str) -> str:
        """Look up read-only shipment and tracking information for one order.

        If no shipment exists for the order, that confirmed absence is returned with
        its own evidence identifier, which you should cite when your reply mentions it.

        Args:
            order_id: An order identifier such as ORD-1001.
        """
        return _operational_lookup(
            workspace,
            registry,
            tool_name="get_shipment_status",
            record_type="shipment",
            identifier=order_id,
            fetch=data_client.get_shipment,
        )

    @tool
    def get_return_status(order_id: str) -> str:
        """Look up read-only return and refund-processing status for one order.

        This reports status only. It never authorizes or issues a refund.

        Args:
            order_id: An order identifier such as ORD-2001.
        """
        return _operational_lookup(
            workspace,
            registry,
            tool_name="get_return_status",
            record_type="return",
            identifier=order_id,
            fetch=data_client.get_return,
        )

    @tool
    def get_account_diagnostics(customer_id: str) -> str:
        """Look up safe, read-only account and login diagnostics for one customer.

        Authentication secrets are never returned by this tool.

        Args:
            customer_id: A customer identifier such as CUS-004.
        """
        return _operational_lookup(
            workspace,
            registry,
            tool_name="get_account_diagnostics",
            record_type="account_diagnostic",
            identifier=customer_id,
            fetch=data_client.get_account_diagnostic,
        )

    @tool
    def get_checkout_diagnostics(customer_id: str) -> str:
        """Look up safe, read-only checkout failure diagnostics for one customer.

        Payment card data is never returned by this tool.

        Args:
            customer_id: A customer identifier such as CUS-003.
        """
        return _operational_lookup(
            workspace,
            registry,
            tool_name="get_checkout_diagnostics",
            record_type="checkout_diagnostic",
            identifier=customer_id,
            fetch=data_client.get_checkout_diagnostic,
        )

    @tool
    def list_available_evidence(reason: str) -> str:
        """List every evidence identifier available to cite in the draft.

        Args:
            reason: A short note on why the evidence list is needed.
        """
        del reason
        return json.dumps(
            {
                "public_evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "title": item.title,
                        "excerpt": item.content[:400],
                    }
                    for item in registry.public_evidence
                ],
                "operational_evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "record_type": item.record_type,
                        "facts": item.facts,
                    }
                    for item in registry.operational_evidence
                ],
            },
            default=str,
        )

    @tool
    def submit_support_draft(draft_json: Any) -> str:
        """Submit the finished customer response. Call this exactly once, at the end.

        The JSON object must contain exactly these keys: issue_summary,
        customer_response, troubleshooting_steps, evidence_ids, unresolved_questions,
        limitations. Cite sources only by identifier inside evidence_ids.

        troubleshooting_steps, evidence_ids, unresolved_questions and limitations are
        lists. A single bare string is accepted for any of them and wrapped
        automatically, so one item does not need to be written as an array by hand.

        If your draft has troubleshooting steps, it must cite at least one evidence
        identifier while any evidence exists. Removing citations is never the right way
        to answer a revision request.

        If your reply states anything about this customer's actual order, shipment,
        return or account -- including that a record could not be found -- cite the
        OP- identifier the relevant tool returned.

        The first submission is final: calling this again returns "already_submitted"
        and does not change the recorded draft.

        Args:
            draft_json: The SupportDraft as a JSON object.
        """
        # The first submission wins. A repeat call means the agent has not noticed it
        # is finished; say so plainly instead of silently overwriting the result.
        if workspace.submitted and workspace.draft is not None:
            return json.dumps(
                {
                    "status": "already_submitted",
                    "reason": (
                        "A draft was already submitted for this ticket and cannot be "
                        "changed. Your work here is complete; stop calling this tool."
                    ),
                    "evidence_ids": list(workspace.draft.evidence_ids),
                }
            )

        try:
            payload = coerce_json_object(draft_json, field="draft_json")
        except ToolArgumentError as exc:
            return json.dumps({"status": "rejected", "reason": str(exc)})

        # Tolerate a bare string where the schema wants a list, rather than spending a
        # retry on a shape the tool can correct itself.
        payload = normalize_list_fields(payload, SUPPORT_DRAFT_LIST_FIELDS)

        try:
            draft = SupportDraft.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - message is returned to the agent to correct
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": "The draft did not match the required schema.",
                    "detail": str(exc)[:500],
                    "allowed_keys": [
                        "issue_summary",
                        "customer_response",
                        "troubleshooting_steps",
                        "evidence_ids",
                        "unresolved_questions",
                        "limitations",
                    ],
                }
            )

        unknown = registry.unknown_ids(draft.evidence_ids)
        if unknown:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": f"The draft cites evidence identifiers that do not exist: {unknown}",
                    "valid_evidence_ids": sorted(registry.known_ids),
                }
            )

        # Enforce the same citation rule QA's check_evidence_grounding applies, so a
        # draft that QA is guaranteed to reject is caught here instead of a full agent
        # round later. In a live run the Support Agent, asked for operational evidence
        # that did not exist, over-corrected by dropping its valid public citations.
        # The tool accepted that draft; QA then failed it, the revision budget was
        # already spent, and the ticket escalated as revision_limit_exceeded.
        #
        # Only enforced while evidence actually exists, so the rejection is always
        # fixable. When no evidence was gathered at all the agent has nothing to cite,
        # and QA's own check correctly escalates rather than looping here.
        has_steps = any(step.strip() for step in draft.troubleshooting_steps)
        if has_steps and not draft.evidence_ids and registry.known_ids:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": (
                        "Troubleshooting steps require at least one evidence citation. "
                        "Add the identifiers your steps are based on to evidence_ids."
                    ),
                    "available_evidence_ids": sorted(registry.known_ids),
                }
            )

        workspace.draft = draft
        workspace.submitted = True
        return json.dumps({"status": "submitted", "evidence_ids": draft.evidence_ids})

    return [
        get_order_status,
        get_shipment_status,
        get_return_status,
        get_account_diagnostics,
        get_checkout_diagnostics,
        list_available_evidence,
        submit_support_draft,
    ]
