"""Relevance filtering and cross-source conflict detection.

These tests are pinned to a real false positive observed on ticket TKT-DEMO-013, where
a USPS postage-refund page was stored as evidence for a damaged-product refund query
and then triggered a spurious conflict escalation.
"""
from __future__ import annotations

import json

import pytest

from support_scout.schemas import ScrapedEvidence
from support_scout.services.evidence_rules import (
    EvidenceAssessor,
    assess_relevance,
    detect_conflict,
)
from support_scout.tools.research_tools import ResearchWorkspace, build_research_tools
from tests.conftest import FakeScraper, FakeSearchAdapter, FakeURLPolicy


def _evidence(evidence_id: str, content: str, title: str = "Source") -> ScrapedEvidence:
    return ScrapedEvidence(
        evidence_id=evidence_id,
        source_url=f"https://example.com/{evidence_id}",
        title=title,
        retrieved_at="2026-09-17T12:00:00Z",
        content=content,
        content_hash=f"hash-{evidence_id}-0001",
    )


def tools_by_name(tools):
    return {tool.name: tool for tool in tools}


# --------------------------------------------------------------------------------------
# Relevance: the TKT-DEMO-013 regression
# --------------------------------------------------------------------------------------
def test_usps_postage_page_is_rejected_for_a_product_refund():
    """Regression: this exact source polluted TKT-DEMO-013 and caused a false conflict."""
    result = assess_relevance(
        title="Request a Domestic Refund | USPS",
        content=(
            "Postage is refundable only for certain services. Metered postage and "
            "stamps are non-refundable after 30 days. Retail mailing service refunds "
            "require a receipt."
        ),
        domain="returns_refunds",
    )
    assert result.relevant is False
    assert "postage" in result.off_domain_terms


@pytest.mark.parametrize(
    "title,content",
    [
        (
            "How can I get a refund on a product I purchased with my credit card?",
            "You may be eligible for a chargeback if the merchant will not refund you. "
            "Damaged or defective goods purchased with a credit card can be disputed.",
        ),
        (
            "Defective Products: Strategies to Get a Refund or Replacement",
            "Defective products are usually eligible for return or replacement. "
            "Contact the retailer for a return label before shipping the item back.",
        ),
    ],
)
def test_genuinely_relevant_refund_sources_are_kept(title, content):
    assert assess_relevance(title=title, content=content, domain="returns_refunds").relevant


def test_tracking_guidance_is_relevant_to_delivery_domain():
    result = assess_relevance(
        title="Why tracking stops updating",
        content="Tracking can pause between carrier scans while a parcel is in transit. "
        "Check the delivery estimate before reporting a package as lost.",
        domain="order_tracking_delivery",
    )
    assert result.relevant


def test_tracking_guidance_is_not_relevant_to_checkout_domain():
    """A good page about the wrong problem is still the wrong page."""
    result = assess_relevance(
        title="Why parcel scans pause",
        content="Scans can pause between carrier facilities while a parcel moves.",
        domain="account_checkout",
    )
    assert result.relevant is False


def test_unknown_domain_accepts_by_default():
    """An undefined domain must not silently reject everything."""
    result = assess_relevance(
        title="Anything", content="Any content at all.", domain="not_a_real_domain"
    )
    assert result.relevant


def test_relevance_reason_is_actionable():
    result = assess_relevance(
        title="Request a Domestic Refund | USPS",
        content="Postage and stamps are non-refundable. Mailing service refunds.",
        domain="returns_refunds",
    )
    assert "different service" in result.reason


# --------------------------------------------------------------------------------------
# Conflict: no longer fires on conditional guidance
# --------------------------------------------------------------------------------------
def test_single_source_stating_a_conditional_rule_is_not_a_conflict():
    """A help page saying 'can be returned ... cannot be returned if' is normal guidance."""
    items = [
        _evidence(
            "EV-001",
            "Items can be returned within 30 days of delivery. Opened software cannot "
            "be returned once the seal is broken.",
        )
    ]
    assert detect_conflict(items).conflicted is False


def test_two_sources_each_stating_their_own_conditions_is_not_a_conflict():
    """Regression: this shape escalated TKT-DEMO-013 as conflicting_evidence."""
    items = [
        _evidence(
            "EV-001",
            "You may be eligible for a chargeback if the merchant will not refund you. "
            "Some purchases are not eligible for dispute.",
        ),
        _evidence(
            "EV-002",
            "Defective products are eligible for replacement. Items damaged by misuse "
            "are not eligible.",
        ),
    ]
    assert detect_conflict(items).conflicted is False


def test_a_single_source_can_never_conflict():
    items = [_evidence("EV-001", "Opened electronics cannot be returned.")]
    assert detect_conflict(items).conflicted is False


def test_genuine_cross_source_disagreement_still_escalates():
    """The control must keep working: opposed positions on the same topic."""
    items = [
        _evidence("EV-001", "Opened electronics can be returned within 30 days for a full refund."),
        _evidence("EV-002", "Opened electronics cannot be returned once the seal is broken."),
    ]
    result = detect_conflict(items)
    assert result.conflicted is True
    assert result.topic == "return_eligibility"
    assert result.affirmative_ids == ["EV-001"]
    assert result.negative_ids == ["EV-002"]


def test_plural_eligibility_phrasing_is_detected():
    """'ARE eligible' must work as well as 'IS eligible'."""
    items = [
        _evidence("EV-001", "Opened items are eligible for return. " * 10),
        _evidence("EV-002", "Opened items are not eligible for return. " * 10),
    ]
    assert detect_conflict(items).conflicted is True


def test_restocking_fee_disagreement_is_detected():
    items = [
        _evidence("EV-001", "Returns are accepted and no restocking fee applies to any item."),
        _evidence("EV-002", "We charge a restocking fee on all opened merchandise."),
    ]
    assert detect_conflict(items).conflicted is True


def test_hedged_statements_do_not_create_a_conflict():
    """'May not be returnable in some cases' is not an assertion."""
    items = [
        _evidence("EV-001", "Most items can be returned within 30 days."),
        _evidence(
            "EV-002",
            "Depending on the retailer, some opened items cannot be returned.",
        ),
    ]
    assert detect_conflict(items).conflicted is False


def test_conflict_description_names_the_disagreeing_sources():
    items = [
        _evidence("EV-001", "Opened electronics can be returned within 30 days."),
        _evidence("EV-002", "Opened electronics cannot be returned under any circumstance."),
    ]
    description = detect_conflict(items).describe()
    assert "EV-001" in description
    assert "EV-002" in description
    assert "return eligibility" in description


# --------------------------------------------------------------------------------------
# Assessor integration
# --------------------------------------------------------------------------------------
def test_assessor_reports_no_conflict_for_the_regression_case():
    items = [
        _evidence("EV-001", "You may be eligible for a chargeback. " * 20),
        _evidence("EV-002", "Defective products are eligible for replacement. " * 20),
    ]
    assessment = EvidenceAssessor().assess(items)
    assert assessment.potential_conflict is False
    assert assessment.insufficient is False


def test_assessor_surfaces_a_genuine_conflict_with_detail():
    items = [
        _evidence("EV-001", "Opened electronics can be returned within 30 days. " * 10),
        _evidence("EV-002", "Opened electronics cannot be returned, ever. " * 10),
    ]
    assessment = EvidenceAssessor().assess(items)
    assert assessment.potential_conflict is True
    assert assessment.conflict.topic == "return_eligibility"
    assert any("disagree" in reason for reason in assessment.reasons)


# --------------------------------------------------------------------------------------
# Tool-level behaviour
# --------------------------------------------------------------------------------------
def _research_tools(registry, workspace, pages=None, enforce=True):
    return tools_by_name(
        build_research_tools(
            workspace,
            registry=registry,
            search_adapter=FakeSearchAdapter(),
            url_policy=FakeURLPolicy(),
            scraper=FakeScraper(pages=pages or {}),
            enforce_relevance=enforce,
        )
    )


def test_fetch_rejects_an_irrelevant_page_without_storing_it(registry):
    workspace = ResearchWorkspace()
    workspace.reset(domain="returns_refunds")
    url = "https://www.usps.com/help/refunds.htm"
    pages = {
        url: {
            "title": "Request a Domestic Refund | USPS",
            "content": "Postage and stamps are non-refundable. Mailing service refunds.",
            "hash": "usps-hash-0001",
            "final_url": url,
        }
    }
    tools = _research_tools(registry, workspace, pages)

    tools["validate_source_url"](url=url)
    outcome = json.loads(tools["fetch_web_page"](url=url))

    assert outcome["status"] == "not_relevant"
    assert registry.public_evidence == []
    assert len(workspace.rejected_sources) == 1


def test_rejection_tells_the_agent_what_to_do_next(registry):
    workspace = ResearchWorkspace()
    workspace.reset(domain="returns_refunds")
    url = "https://www.usps.com/help/refunds.htm"
    pages = {
        url: {
            "title": "USPS postage refunds",
            "content": "Postage and stamps are non-refundable after 30 days.",
            "hash": "usps-hash-0002",
            "final_url": url,
        }
    }
    tools = _research_tools(registry, workspace, pages)

    tools["validate_source_url"](url=url)
    outcome = json.loads(tools["fetch_web_page"](url=url))

    assert "different search result" in outcome["guidance"]


def test_fetch_stores_a_relevant_page(registry):
    workspace = ResearchWorkspace()
    workspace.reset(domain="returns_refunds")
    url = "https://help.example.com/returns"
    pages = {
        url: {
            "title": "How to return a damaged item",
            "content": "Damaged or defective items are eligible for return. Request a "
            "return label from the retailer and ship the item back for a refund.",
            "hash": "relevant-hash-0001",
            "final_url": url,
        }
    }
    tools = _research_tools(registry, workspace, pages)

    tools["validate_source_url"](url=url)
    outcome = json.loads(tools["fetch_web_page"](url=url))

    assert outcome["status"] == "ok"
    assert outcome["evidence_id"] == "EV-001"


def test_relevance_can_be_disabled_for_tests(registry):
    workspace = ResearchWorkspace()
    workspace.reset(domain="returns_refunds")
    url = "https://www.usps.com/help/refunds.htm"
    pages = {
        url: {
            "title": "USPS postage refunds",
            "content": "Postage and stamps are non-refundable.",
            "hash": "usps-hash-0003",
            "final_url": url,
        }
    }
    tools = _research_tools(registry, workspace, pages, enforce=False)

    tools["validate_source_url"](url=url)
    outcome = json.loads(tools["fetch_web_page"](url=url))

    assert outcome["status"] == "ok"


def test_relevance_is_skipped_when_no_domain_is_set(registry):
    """Defensive: an unset domain must not reject every source."""
    workspace = ResearchWorkspace()
    workspace.reset()
    url = "https://help.example.com/anything"
    tools = _research_tools(registry, workspace)

    tools["validate_source_url"](url=url)
    outcome = json.loads(tools["fetch_web_page"](url=url))

    assert outcome["status"] == "ok"


def test_assess_evidence_reports_rejected_source_count(registry):
    workspace = ResearchWorkspace()
    workspace.reset(domain="returns_refunds")
    url = "https://www.usps.com/help/refunds.htm"
    pages = {
        url: {
            "title": "USPS postage refunds",
            "content": "Postage and stamps are non-refundable.",
            "hash": "usps-hash-0004",
            "final_url": url,
        }
    }
    tools = _research_tools(registry, workspace, pages)

    tools["validate_source_url"](url=url)
    tools["fetch_web_page"](url=url)
    outcome = json.loads(tools["assess_evidence"](reason="done"))

    assert outcome["sources_rejected_as_irrelevant"] == 1
    assert outcome["insufficient"] is True


def test_default_fake_content_is_relevant_to_every_domain():
    """The shared test fake must not be rejected by the relevance gate."""
    for domain in ("order_tracking_delivery", "returns_refunds", "account_checkout"):
        result = assess_relevance(
            title="Help centre guidance",
            content=FakeScraper.DEFAULT_CONTENT,
            domain=domain,
        )
        assert result.relevant, f"default fixture content rejected for {domain}"
