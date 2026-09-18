"""Reusable tool-call scripts for the offline agent harness.

Each function returns a script: a generator that yields `(tool_name, kwargs)` and
receives the tool observation back, so it can adapt to real evidence identifiers
instead of hard-coding them.
"""
from __future__ import annotations

import json
from typing import Any


def triage_script(
    domain: str = "order_tracking_delivery",
    intent: str = "find out where a late parcel is",
    urgency: str = "medium",
    confidence: float = 0.92,
    uncertainty_reason: str = "",
):
    """Standard triage: list domains, measure sentiment, submit."""

    def script(ctx):
        yield "list_supported_domains", {"reason": "confirm allowed domains"}
        yield "analyze_sentiment", {"reason": "measure customer tone"}
        yield "submit_triage", {
            "domain": domain,
            "intent": intent,
            "urgency": urgency,
            "confidence": confidence,
            "uncertainty_reason": uncertainty_reason,
        }

    return script


def research_script(query: str = "parcel tracking not updating what to do", pages: int = 1):
    """Standard research: search, validate, fetch, assess, submit."""

    def script(ctx):
        observation = yield "web_search", {"query": query}
        payload = json.loads(observation)
        urls = [item["url"] for item in payload.get("results", [])][:pages]

        for url in urls:
            yield "validate_source_url", {"url": url}
            yield "fetch_web_page", {"url": url}

        yield "assess_evidence", {"reason": "pages gathered"}
        yield "submit_research_result", {"summary": "General tracking guidance located."}

    return script


def research_script_no_results():
    """Research that finds nothing usable and honestly reports insufficiency."""

    def script(ctx):
        yield "web_search", {"query": "obscure topic with no guidance"}
        yield "assess_evidence", {"reason": "nothing usable was retrieved"}
        yield "submit_research_result", {"summary": "No usable public guidance found."}

    return script


def support_script(
    order_id: str | None = "ORD-1001",
    customer_id: str | None = None,
    customer_response: str | None = None,
    steps: list[str] | None = None,
    extra_tools: list[tuple[str, dict[str, Any]]] | None = None,
):
    """Standard support drafting: call relevant tools, then submit a grounded draft."""

    def script(ctx):
        evidence_ids: list[str] = []

        if order_id:
            observation = yield "get_order_status", {"order_id": order_id}
            payload = json.loads(observation)
            if payload.get("evidence_id"):
                evidence_ids.append(payload["evidence_id"])

            observation = yield "get_shipment_status", {"order_id": order_id}
            payload = json.loads(observation)
            if payload.get("evidence_id"):
                evidence_ids.append(payload["evidence_id"])

        if customer_id:
            observation = yield "get_checkout_diagnostics", {"customer_id": customer_id}
            payload = json.loads(observation)
            if payload.get("evidence_id"):
                evidence_ids.append(payload["evidence_id"])

        for tool_name, kwargs in extra_tools or []:
            observation = yield tool_name, kwargs
            payload = json.loads(observation)
            if payload.get("evidence_id"):
                evidence_ids.append(payload["evidence_id"])

        observation = yield "list_available_evidence", {"reason": "confirm citable evidence"}
        available = json.loads(observation)
        evidence_ids.extend(item["evidence_id"] for item in available.get("public_evidence", []))
        evidence_ids = list(dict.fromkeys(evidence_ids))

        draft = {
            "issue_summary": "The customer's parcel is late and tracking has not updated.",
            "customer_response": customer_response
            or (
                "Thanks for flagging this, and sorry for the wait. Your order is in "
                "transit and the most recent carrier scan shows it at a regional "
                "facility. Tracking sometimes pauses for a day or two between scans. "
                "If it has not moved by the expected delivery date, reply here and we "
                "will raise it with the carrier."
            ),
            "troubleshooting_steps": steps
            or [
                "Check the tracking reference on the carrier's own website.",
                "Confirm the delivery address on the order is correct.",
                "Allow one extra business day before reporting the parcel as lost.",
            ],
            "evidence_ids": evidence_ids,
            "unresolved_questions": [],
            "limitations": ["Carrier scan timing is outside our control."],
        }
        yield "submit_support_draft", {"draft_json": json.dumps(draft)}

    return script


def support_script_with_draft(draft: dict[str, Any], order_id: str | None = "ORD-1001"):
    """Support drafting that submits a specific draft, used by adversarial tests."""

    def script(ctx):
        evidence_ids: list[str] = []
        if order_id:
            observation = yield "get_order_status", {"order_id": order_id}
            payload = json.loads(observation)
            if payload.get("evidence_id"):
                evidence_ids.append(payload["evidence_id"])

        observation = yield "list_available_evidence", {"reason": "confirm citable evidence"}
        available = json.loads(observation)
        evidence_ids.extend(item["evidence_id"] for item in available.get("public_evidence", []))

        payload = dict(draft)
        payload.setdefault("evidence_ids", list(dict.fromkeys(evidence_ids)))
        yield "submit_support_draft", {"draft_json": json.dumps(payload)}

    return script


def qa_script(decision: str = "approve", issues: list[str] | None = None):
    """Standard QA: run every required check, then submit a decision."""

    def script(ctx):
        yield "check_evidence_grounding", {"reason": "verify citations"}
        yield "check_restricted_claims", {"reason": "verify authority limits"}
        yield "check_sensitive_data", {"reason": "verify no secrets"}
        yield "check_operational_claims", {"reason": "verify customer-specific claims"}

        if decision == "revise":
            yield "request_support_revision", {
                "instructions_json": json.dumps(issues or ["Cite the evidence used."])
            }

        yield "submit_qa_decision", {
            "decision": decision,
            "issues_json": json.dumps(issues or []),
        }

    return script


def qa_script_skipping_checks(decision: str = "approve"):
    """QA that tries to submit without running the required checks."""

    def script(ctx):
        yield "submit_qa_decision", {"decision": decision, "issues_json": "[]"}
        # The tool rejects this, so run the checks and try again honestly.
        yield "check_evidence_grounding", {"reason": "retry"}
        yield "check_restricted_claims", {"reason": "retry"}
        yield "check_sensitive_data", {"reason": "retry"}
        yield "check_operational_claims", {"reason": "retry"}
        yield "submit_qa_decision", {"decision": decision, "issues_json": "[]"}

    return script


def documentation_script(title: str = "Why parcel tracking stops updating", body: str | None = None):
    """Standard documentation: select evidence, check privacy, submit."""

    def script(ctx):
        observation = yield "list_public_evidence", {"reason": "see available sources"}
        payload = json.loads(observation)
        evidence_ids = [item["evidence_id"] for item in payload.get("public_evidence", [])]

        yield "select_public_evidence", {"evidence_ids_json": json.dumps(evidence_ids)}

        article = {
            "title": title,
            "body_markdown": body
            or (
                "# Why parcel tracking stops updating\n\n"
                "Tracking information updates when a carrier scans a parcel. Between "
                "scans, which can be a day or more apart on standard shipping, the "
                "tracking page will look unchanged even though the parcel is moving.\n\n"
                "## What to do\n\n"
                "1. Check the tracking reference on the carrier's own website.\n"
                "2. Confirm the delivery address on the order is correct.\n"
                "3. Allow one extra business day before reporting the parcel as lost.\n"
                "4. If tracking has not moved after that, contact the carrier.\n"
            ),
            "source_evidence_ids": evidence_ids,
            "limitations": ["Carrier scan timing is outside the retailer's control."],
        }
        yield "check_article_privacy", {"article_json": json.dumps(article)}
        yield "submit_article", {"reason": "privacy check passed"}

    return script


def documentation_script_leaking_identifier():
    """Documentation that leaks a customer identifier into the body text."""

    def script(ctx):
        observation = yield "list_public_evidence", {"reason": "see available sources"}
        payload = json.loads(observation)
        evidence_ids = [item["evidence_id"] for item in payload.get("public_evidence", [])]
        yield "select_public_evidence", {"evidence_ids_json": json.dumps(evidence_ids)}

        leaking = {
            "title": "Tracking guidance",
            "body_markdown": "# Tracking guidance\n\nOrder ORD-1001 for CUS-001 was delayed.",
            "source_evidence_ids": evidence_ids,
            "limitations": [],
        }
        observation = yield "check_article_privacy", {"article_json": json.dumps(leaking)}

        # The privacy tool rejects it, so publish a properly generic article instead.
        clean = {
            "title": "Tracking guidance",
            "body_markdown": (
                "# Tracking guidance\n\nTracking can pause between carrier scans. "
                "Check the carrier site and confirm the delivery address before "
                "reporting a parcel as lost.\n"
            ),
            "source_evidence_ids": evidence_ids,
            "limitations": [],
        }
        yield "check_article_privacy", {"article_json": json.dumps(clean)}
        yield "submit_article", {"reason": "privacy check passed"}

    return script


def orchestrator_script(revision: bool = False):
    """Standard orchestration: inspect state, delegate in order, finalize."""

    def script(ctx):
        yield "inspect_workflow_state", {"reason": "start"}
        yield "delegate_to_triage", {"reason": "classify the ticket"}

        observation = json.loads(ctx.last())
        if not observation.get("delegated") or observation.get("current_state") == "escalated":
            yield "finalize_workflow", {"reason": "escalated during triage"}
            return

        yield "delegate_to_research", {"reason": "gather public guidance"}
        observation = json.loads(ctx.last())
        if observation.get("current_state") == "escalated":
            yield "finalize_workflow", {"reason": "escalated during research"}
            return

        yield "delegate_to_support", {"reason": "draft the response"}
        yield "delegate_to_qa", {"reason": "review the draft"}
        observation = json.loads(ctx.last())
        state = observation.get("current_state")

        if state == "qa_revision_requested":
            yield "delegate_to_support", {"reason": "apply QA revisions"}
            yield "delegate_to_qa", {"reason": "re-review the revised draft"}
            observation = json.loads(ctx.last())
            state = observation.get("current_state")

        if state == "escalated":
            yield "finalize_workflow", {"reason": "escalated during QA"}
            return

        yield "delegate_to_documentation", {"reason": "write the reusable article"}
        yield "finalize_workflow", {"reason": "workflow complete"}

    return script


def full_happy_path_model(
    scripted_model_cls,
    *,
    triage: Any = None,
    research: Any = None,
    support: Any = None,
    qa: Any = None,
    documentation: Any = None,
    orchestrator: Any = None,
):
    """Assemble a ScriptedModel covering every agent in one run."""
    return scripted_model_cls(
        triage_agent=triage or triage_script(),
        research_agent=research or research_script(),
        support_agent=support or support_script(),
        qa_agent=qa or qa_script(),
        documentation_agent=documentation or documentation_script(),
        orchestrator_agent=orchestrator or orchestrator_script(),
    )
