"""Content validation tests.

The restricted-claim paraphrases here are the cases the previous literal-phrase list
missed. Each one would have been approved and sent to a customer.
"""
from __future__ import annotations

import pytest

from support_scout.schemas import ScrapedEvidence, SupportDraft, TroubleshootingArticle
from support_scout.services.content_validation import (
    ArticlePrivacyValidator,
    ContentValidator,
    contains_restricted_claim,
    requests_secret,
)


def _evidence(evidence_id: str = "EV-001") -> ScrapedEvidence:
    return ScrapedEvidence(
        evidence_id=evidence_id,
        source_url="https://help.example.com/guide",
        title="Guide",
        retrieved_at="2026-09-17T12:00:00Z",
        content="General guidance about tracking.",
        content_hash="abcdef1234",
    )


def _draft(**overrides) -> SupportDraft:
    payload = {
        "issue_summary": "Parcel is late.",
        "customer_response": "Thanks for reaching out. Your parcel is still in transit.",
        "troubleshooting_steps": ["Check the carrier site."],
        "evidence_ids": ["EV-001"],
        "unresolved_questions": [],
        "limitations": [],
    }
    payload.update(overrides)
    return SupportDraft.model_validate(payload)


# --------------------------------------------------------------------------------------
# Restricted claims
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "I approved your refund.",
        "I've approved your refund.",
        "We have already issued your refund.",
        "Your refund has been approved.",
        "Your refund is approved.",
        "The refund was issued this morning.",
        "Your payment has been processed.",
        "Refund approved, you will see it shortly.",
        "I will approve your refund today.",
        "I have updated your order for you.",
        "Your account has been changed as requested.",
        "I verified your order in our system.",
    ],
)
def test_restricted_claims_detected_across_phrasings(text):
    assert contains_restricted_claim(text)


@pytest.mark.parametrize(
    "text",
    [
        "A refund can be requested through the returns centre.",
        "Refunds are usually processed within five business days.",
        "Our team will review whether a refund applies.",
        "You can check your order status in your account.",
    ],
)
def test_general_refund_guidance_is_not_a_restricted_claim(text):
    assert not contains_restricted_claim(text)


def test_validator_flags_restricted_draft():
    validator = ContentValidator()
    draft = _draft(customer_response="Good news, I've approved your refund.")
    result = validator.validate(draft, [_evidence()])
    assert not result.valid
    assert result.contains_restricted_claim


# --------------------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Please reply with your password so we can check.",
        "Send us your full card number to verify.",
        "Confirm the one-time code you received.",
    ],
)
def test_requests_for_secrets_are_detected(text):
    assert requests_secret(text)


def test_validator_flags_secret_request():
    validator = ContentValidator()
    draft = _draft(customer_response="Please reply with your password so we can check.")
    result = validator.validate(draft, [_evidence()])
    assert not result.valid
    assert result.contains_sensitive_data


# --------------------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------------------
def test_unknown_evidence_identifier_is_rejected():
    validator = ContentValidator()
    draft = _draft(evidence_ids=["EV-999"])
    result = validator.validate(draft, [_evidence()])
    assert not result.valid
    assert result.unknown_evidence_ids == ["EV-999"]


def test_steps_without_citation_are_rejected():
    validator = ContentValidator()
    draft = _draft(evidence_ids=[], troubleshooting_steps=["Do a thing."])
    result = validator.validate(draft, [_evidence()])
    assert not result.valid


def test_valid_draft_passes():
    validator = ContentValidator()
    assert validator.validate(_draft(), [_evidence()]).valid


# --------------------------------------------------------------------------------------
# Article privacy
# --------------------------------------------------------------------------------------
def _article(**overrides) -> TroubleshootingArticle:
    payload = {
        "title": "Why tracking stops updating",
        "body_markdown": "# Why tracking stops updating\n\nTracking pauses between scans.",
        "source_evidence_ids": ["EV-001"],
        "limitations": [],
    }
    payload.update(overrides)
    return TroubleshootingArticle.model_validate(payload)


@pytest.mark.parametrize(
    "identifier",
    ["ORD-1001", "CUS-003", "SHP-1001", "RET-2001", "CHK-3001", "ACC-4001", "TKT-DEMO-001", "OP-001"],
)
def test_article_body_identifiers_are_rejected(identifier):
    """Every identifier family is blocked, including the three the old list missed."""
    validator = ArticlePrivacyValidator()
    article = _article(body_markdown=f"# Guide\n\nThis happened to {identifier} last week.")
    result = validator.validate(article, allowed_evidence_ids={"EV-001"})
    assert not result.privacy_safe
    assert identifier in result.matched_identifiers


def test_article_email_is_rejected():
    validator = ArticlePrivacyValidator()
    article = _article(body_markdown="# Guide\n\nContact shopper@example.com for details.")
    assert not validator.validate(article, allowed_evidence_ids={"EV-001"}).privacy_safe


def test_article_citing_operational_evidence_is_rejected():
    validator = ArticlePrivacyValidator()
    article = _article(source_evidence_ids=["OP-001"])
    assert not validator.validate(article, allowed_evidence_ids={"EV-001"}).privacy_safe


def test_article_citing_unselected_evidence_is_rejected():
    validator = ArticlePrivacyValidator()
    article = _article(source_evidence_ids=["EV-002"])
    assert not validator.validate(article, allowed_evidence_ids={"EV-001"}).privacy_safe


def test_clean_article_passes():
    validator = ArticlePrivacyValidator()
    assert validator.validate(_article(), allowed_evidence_ids={"EV-001"}).privacy_safe
