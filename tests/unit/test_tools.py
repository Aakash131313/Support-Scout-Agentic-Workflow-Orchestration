"""Tool-level tests.

These assert the guarantees that make the workflow safe regardless of what the model
decides to do: tools reject fabricated identifiers, refuse out-of-order calls, return
structured misses instead of raising, and refuse unsafe submissions.
"""
from __future__ import annotations

import json

import pytest

from support_scout.evidence_registry import EvidenceRegistry
from support_scout.schemas import SupportDraft
from support_scout.tools.documentation_tools import (
    DocumentationWorkspace,
    build_documentation_tools,
)
from support_scout.tools.qa_tools import QAWorkspace, build_qa_tools
from support_scout.tools.research_tools import ResearchWorkspace, build_research_tools
from support_scout.tools.support_tools import SupportWorkspace, build_support_tools
from support_scout.tools.triage_tools import (
    TriageWorkspace,
    assess_sentiment,
    build_triage_tools,
)
from tests.conftest import FakeDataClient, FakeScraper, FakeSearchAdapter, FakeURLPolicy


def tools_by_name(tools):
    return {tool.name: tool for tool in tools}


# --------------------------------------------------------------------------------------
# Every tool is a real, introspectable smolagents tool
# --------------------------------------------------------------------------------------
def test_tools_expose_name_description_and_schema(registry):
    tools = build_support_tools(SupportWorkspace(), registry=registry, data_client=FakeDataClient())
    for tool in tools:
        assert tool.name
        assert tool.description
        assert isinstance(tool.inputs, dict)
        for spec in tool.inputs.values():
            assert spec["description"], f"{tool.name} has an undocumented argument"


# --------------------------------------------------------------------------------------
# Triage tools
# --------------------------------------------------------------------------------------
def test_sentiment_detects_frustration():
    result = assess_sentiment("This is absolutely ridiculous and I am extremely frustrated.")
    assert result.label.value == "negative"
    assert result.intensity.value in {"moderate", "strong"}


def test_sentiment_neutral_for_plain_report():
    result = assess_sentiment("My parcel has not arrived yet.")
    assert result.label.value == "neutral"


def test_triage_submission_requires_sentiment_first():
    workspace = TriageWorkspace()
    workspace.reset("My parcel is late.")
    tools = tools_by_name(build_triage_tools(workspace))

    outcome = json.loads(
        tools["submit_triage"](
            domain="order_tracking_delivery",
            intent="locate parcel",
            urgency="medium",
            confidence=0.9,
            uncertainty_reason="",
        )
    )
    assert outcome["status"] == "rejected"


def test_triage_rejects_unknown_domain():
    workspace = TriageWorkspace()
    workspace.reset("My parcel is late.")
    tools = tools_by_name(build_triage_tools(workspace))
    tools["analyze_sentiment"](reason="tone")

    outcome = json.loads(
        tools["submit_triage"](
            domain="billing_disputes",
            intent="x",
            urgency="medium",
            confidence=0.9,
            uncertainty_reason="",
        )
    )
    assert outcome["status"] == "rejected"
    assert "allowed" in outcome


# --------------------------------------------------------------------------------------
# Research tools
# --------------------------------------------------------------------------------------
def test_search_query_identifiers_never_reach_the_provider(registry):
    """FR-006A enforced at the tool boundary, not merely requested in the prompt."""
    adapter = FakeSearchAdapter()
    tools = tools_by_name(
        build_research_tools(
            ResearchWorkspace(),
            registry=registry,
            search_adapter=adapter,
            url_policy=FakeURLPolicy(),
            scraper=FakeScraper(),
        )
    )

    tools["web_search"](query="ORD-1001 for CUS-003 delayed delivery")

    assert adapter.queries
    assert "ORD-1001" not in adapter.queries[0]
    assert "CUS-003" not in adapter.queries[0]


def test_fetch_requires_prior_validation(registry):
    tools = tools_by_name(
        build_research_tools(
            ResearchWorkspace(),
            registry=registry,
            search_adapter=FakeSearchAdapter(),
            url_policy=FakeURLPolicy(),
            scraper=FakeScraper(),
        )
    )
    outcome = json.loads(tools["fetch_web_page"](url="https://help.example.com/tracking-delays"))
    assert outcome["status"] == "rejected"


def test_unsafe_url_is_blocked_before_any_request(registry):
    """AT-005: the request is never made."""
    scraper = FakeScraper()
    tools = tools_by_name(
        build_research_tools(
            ResearchWorkspace(),
            registry=registry,
            search_adapter=FakeSearchAdapter(),
            url_policy=FakeURLPolicy(),
            scraper=scraper,
        )
    )

    outcome = json.loads(tools["validate_source_url"](url="http://localhost:8001/admin"))
    assert outcome["status"] == "blocked"
    assert scraper.fetched == []


def test_page_budget_is_enforced(registry):
    policy = FakeURLPolicy()
    tools = tools_by_name(
        build_research_tools(
            ResearchWorkspace(),
            registry=registry,
            search_adapter=FakeSearchAdapter(),
            url_policy=policy,
            scraper=FakeScraper(),
            max_pages=1,
        )
    )
    for url in ("https://a.example.com/x", "https://b.example.com/y"):
        tools["validate_source_url"](url=url)

    first = json.loads(tools["fetch_web_page"](url="https://a.example.com/x"))
    second = json.loads(tools["fetch_web_page"](url="https://b.example.com/y"))
    assert first["status"] == "ok"
    assert second["status"] == "rejected"


def test_scrape_failure_returns_structured_error(registry):
    """AT-009: a failed page does not kill the run."""
    from support_scout.exceptions import ScrapeTimeoutError

    tools = tools_by_name(
        build_research_tools(
            ResearchWorkspace(),
            registry=registry,
            search_adapter=FakeSearchAdapter(),
            url_policy=FakeURLPolicy(),
            scraper=FakeScraper(error=ScrapeTimeoutError("Page request timed out")),
        )
    )
    tools["validate_source_url"](url="https://a.example.com/x")
    outcome = json.loads(tools["fetch_web_page"](url="https://a.example.com/x"))
    assert outcome["status"] == "error"


def test_search_failure_returns_structured_error(registry):
    """AT-008: a provider failure is controlled and leaks no secret."""
    from support_scout.exceptions import SearchTimeoutError

    tools = tools_by_name(
        build_research_tools(
            ResearchWorkspace(),
            registry=registry,
            search_adapter=FakeSearchAdapter(error=SearchTimeoutError("Search timed out")),
            url_policy=FakeURLPolicy(),
            scraper=FakeScraper(),
        )
    )
    outcome = json.loads(tools["web_search"](query="tracking guidance"))
    assert outcome["status"] == "error"
    assert "key" not in outcome["reason"].casefold()


# --------------------------------------------------------------------------------------
# Support tools
# --------------------------------------------------------------------------------------
def test_missing_order_returns_structured_miss(registry):
    """The unknown-order case must be reasoned about, not raised."""
    tools = tools_by_name(
        build_support_tools(SupportWorkspace(), registry=registry, data_client=FakeDataClient())
    )
    outcome = json.loads(tools["get_order_status"](order_id="ORD-9999"))
    assert outcome["available"] is False
    assert "no such record" in outcome["reason"].casefold()


def test_operations_outage_returns_structured_miss(registry):
    """AT-007-style dependency failure: controlled, not fatal."""
    tools = tools_by_name(
        build_support_tools(
            SupportWorkspace(),
            registry=registry,
            data_client=FakeDataClient(unavailable=True),
        )
    )
    outcome = json.loads(tools["get_order_status"](order_id="ORD-1001"))
    assert outcome["available"] is False


def test_successful_lookup_mints_operational_evidence(registry):
    tools = tools_by_name(
        build_support_tools(SupportWorkspace(), registry=registry, data_client=FakeDataClient())
    )
    outcome = json.loads(tools["get_order_status"](order_id="ORD-1001"))
    assert outcome["available"] is True
    assert outcome["evidence_id"] == "OP-001"


def test_draft_citing_fabricated_evidence_is_rejected(registry):
    workspace = SupportWorkspace()
    tools = tools_by_name(
        build_support_tools(workspace, registry=registry, data_client=FakeDataClient())
    )
    draft = {
        "issue_summary": "Late parcel.",
        "customer_response": "Your parcel is in transit.",
        "troubleshooting_steps": ["Check the carrier site."],
        "evidence_ids": ["EV-999"],
        "unresolved_questions": [],
        "limitations": [],
    }
    outcome = json.loads(tools["submit_support_draft"](draft_json=json.dumps(draft)))
    assert outcome["status"] == "rejected"
    assert workspace.submitted is False


def test_draft_with_wrong_schema_is_rejected_with_guidance(registry):
    tools = tools_by_name(
        build_support_tools(SupportWorkspace(), registry=registry, data_client=FakeDataClient())
    )
    outcome = json.loads(tools["submit_support_draft"](draft_json=json.dumps({"order_id": "ORD-1"})))
    assert outcome["status"] == "rejected"
    assert "allowed_keys" in outcome


# --------------------------------------------------------------------------------------
# QA tools
# --------------------------------------------------------------------------------------
def _qa_setup(registry, draft: SupportDraft):
    workspace = QAWorkspace()
    workspace.reset(draft)
    return workspace, tools_by_name(build_qa_tools(workspace, registry=registry))


def _clean_draft() -> SupportDraft:
    return SupportDraft(
        issue_summary="Late parcel.",
        customer_response="Your parcel is in transit and should arrive shortly.",
        troubleshooting_steps=["Check the carrier site."],
        evidence_ids=["EV-001"],
    )


def test_qa_cannot_submit_before_running_checks(registry):
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    _, tools = _qa_setup(registry, _clean_draft())
    outcome = json.loads(tools["submit_qa_decision"](decision="approve", issues_json="[]"))
    assert outcome["status"] == "rejected"


def test_qa_cannot_approve_while_a_check_fails(registry):
    """AT-019: an unsupported claim cannot be approved, whatever the model prefers."""
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    draft = SupportDraft(
        issue_summary="Refund.",
        customer_response="Good news, I have approved your refund.",
        troubleshooting_steps=["Wait for the credit."],
        evidence_ids=["EV-001"],
    )
    _, tools = _qa_setup(registry, draft)

    for name in (
        "check_evidence_grounding",
        "check_restricted_claims",
        "check_sensitive_data",
        "check_operational_claims",
    ):
        tools[name](reason="check")

    outcome = json.loads(tools["submit_qa_decision"](decision="approve", issues_json="[]"))
    assert outcome["status"] == "rejected"
    assert outcome["blocking_issues"]


def test_qa_escalation_reason_is_specific(registry):
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    draft = SupportDraft(
        issue_summary="Account.",
        customer_response="Your password is hunter2 as you asked.",
        troubleshooting_steps=["Sign in again."],
        evidence_ids=["EV-001"],
    )
    workspace, tools = _qa_setup(registry, draft)

    for name in (
        "check_evidence_grounding",
        "check_restricted_claims",
        "check_sensitive_data",
        "check_operational_claims",
    ):
        tools[name](reason="check")

    outcome = json.loads(tools["submit_qa_decision"](decision="escalate", issues_json="[]"))
    assert outcome["escalation_reason"] == "sensitive_data"


def test_qa_revision_requires_instructions(registry):
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    _, tools = _qa_setup(registry, _clean_draft())
    for name in (
        "check_evidence_grounding",
        "check_restricted_claims",
        "check_sensitive_data",
        "check_operational_claims",
    ):
        tools[name](reason="check")

    outcome = json.loads(tools["submit_qa_decision"](decision="revise", issues_json="[]"))
    assert outcome["status"] == "rejected"


def test_qa_approves_a_clean_draft(registry):
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    workspace, tools = _qa_setup(registry, _clean_draft())
    for name in (
        "check_evidence_grounding",
        "check_restricted_claims",
        "check_sensitive_data",
        "check_operational_claims",
    ):
        tools[name](reason="check")

    outcome = json.loads(tools["submit_qa_decision"](decision="approve", issues_json="[]"))
    assert outcome["status"] == "submitted"
    assert workspace.result.decision.value == "approve"


# --------------------------------------------------------------------------------------
# Documentation tools
# --------------------------------------------------------------------------------------
def _doc_setup(registry):
    workspace = DocumentationWorkspace()
    return workspace, tools_by_name(build_documentation_tools(workspace, registry=registry))


def test_documentation_rejects_operational_evidence_selection(registry):
    registry.register_operational(record_type="order", record_id="ORD-1001", facts={})
    _, tools = _doc_setup(registry)
    outcome = json.loads(tools["select_public_evidence"](evidence_ids_json=json.dumps(["OP-001"])))
    assert outcome["status"] == "rejected"


def test_documentation_blocks_identifier_in_body(registry):
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    _, tools = _doc_setup(registry)
    tools["select_public_evidence"](evidence_ids_json=json.dumps(["EV-001"]))

    article = {
        "title": "Guide",
        "body_markdown": "# Guide\n\nOrder ORD-1001 was delayed.",
        "source_evidence_ids": ["EV-001"],
        "limitations": [],
    }
    outcome = json.loads(tools["check_article_privacy"](article_json=json.dumps(article)))
    assert outcome["status"] == "rejected"
    assert "ORD-1001" in outcome["matched_identifiers"]


def test_documentation_cannot_submit_without_privacy_check(registry):
    _, tools = _doc_setup(registry)
    outcome = json.loads(tools["submit_article"](reason="ready"))
    assert outcome["status"] == "rejected"


def test_documentation_accepts_a_generic_article(registry):
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    workspace, tools = _doc_setup(registry)
    tools["select_public_evidence"](evidence_ids_json=json.dumps(["EV-001"]))

    article = {
        "title": "Why tracking stops updating",
        "body_markdown": "# Why tracking stops updating\n\nTracking pauses between scans.",
        "source_evidence_ids": ["EV-001"],
        "limitations": [],
    }
    tools["check_article_privacy"](article_json=json.dumps(article))
    outcome = json.loads(tools["submit_article"](reason="clean"))
    assert outcome["status"] == "submitted"
    assert workspace.submitted is True
