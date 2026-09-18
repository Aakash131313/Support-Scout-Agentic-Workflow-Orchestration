"""Support specialist tools: read-only operational diagnostics plus draft submission.

The Support Agent decides *which* operational records are relevant. Nothing here runs
automatically. That is the core behavioural difference from the old deterministic
service, which fired every tool for every identifier it could regex out of the ticket.

Missing records return a structured `available: false` result rather than raising, so
the agent can reason about a genuine miss (for example an unknown order) instead of
having its loop killed by an exception.

`submit_support_draft` accepts the draft as either a JSON object or a JSON string; a
model sends both forms and a hard `str` type would reject the native object outright.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from smolagents import tool

from ..evidence_registry import EvidenceRegistry
from ..exceptions import SupportDataClientError, SupportDataNotFound
from ..schemas import SupportDraft
from .json_args import ToolArgumentError, coerce_json_object


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
    try:
        facts = fetch(identifier)
    except SupportDataNotFound:
        workspace.records_unavailable.append(f"{record_type}:{identifier}")
        return json.dumps(
            {
                "available": False,
                "record_type": record_type,
                "record_id": identifier,
                "reason": "No such record exists in the operations system.",
            }
        )
    except SupportDataClientError as exc:
        workspace.records_unavailable.append(f"{record_type}:{identifier}")
        return json.dumps(
            {
                "available": False,
                "record_type": record_type,
                "record_id": identifier,
                "reason": f"The operations service could not be reached: {exc}",
            }
        )

    record = registry.register_operational(
        record_type=record_type,
        record_id=str(facts.get(f"{record_type}_id") or identifier),
        facts=facts,
    )
    if record is None:
        return json.dumps(
            {
                "available": True,
                "duplicate": True,
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

        Args:
            draft_json: The SupportDraft as a JSON object.
        """
        try:
            payload = coerce_json_object(draft_json, field="draft_json")
        except ToolArgumentError as exc:
            return json.dumps({"status": "rejected", "reason": str(exc)})

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
