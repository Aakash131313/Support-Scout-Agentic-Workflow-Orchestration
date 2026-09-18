"""Deterministic validation of generated content.

Two distinct checks live here:

* `ContentValidator`  - validates a customer-facing SupportDraft (grounding, authority,
  secret leakage).
* `ArticlePrivacyValidator` - validates a reusable TroubleshootingArticle, which has a
  much stricter rule: no customer-specific identifier of any kind may appear anywhere
  in the body text, not merely in the citation list.

Restricted-claim detection is pattern-based rather than literal-phrase based. The
previous alias list only caught exact strings such as "i approved your refund", so
"I've approved your refund", "your refund is approved" and "refund has been authorized"
all passed. The patterns below match subject/verb/object shapes instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas import OperationalEvidence, ScrapedEvidence, SupportDraft, TroubleshootingArticle
from .safety_rules import contains_sensitive_data

EvidenceRecord = ScrapedEvidence | OperationalEvidence

# --------------------------------------------------------------------------------------
# Restricted claim detection
# --------------------------------------------------------------------------------------
_RESTRICTED_OBJECT = r"(?:refund|credit|payment|charge|exception|order|account|subscription|address)"
_COMPLETION_VERB = (
    r"(?:approved|issued|authorized|authorised|processed|granted|refunded|credited"
    r"|updated|modified|changed|cancelled|canceled|reset|restored)"
)

_RESTRICTED_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "I approved", "we've issued", "I have already processed"
    re.compile(
        rf"(?i)\b(?:i|we)\s*(?:'ve|'ll|\s+have|\s+has|\s+had)?\s*(?:already\s+)?{_COMPLETION_VERB}\b[^.!?]{{0,60}}\b{_RESTRICTED_OBJECT}\b"
    ),
    # "your refund has been approved", "the refund was issued"
    re.compile(
        rf"(?i)\b(?:your|the|this)\s+{_RESTRICTED_OBJECT}\b[^.!?]{{0,40}}\b(?:has|have|had|was|were|is|are)\s+(?:been\s+)?{_COMPLETION_VERB}\b"
    ),
    # "refund approved", "payment processed" used as a completed statement
    re.compile(rf"(?i)\b{_RESTRICTED_OBJECT}\s+(?:successfully\s+)?{_COMPLETION_VERB}\b"),
    # Explicit promises of future authorisation
    re.compile(
        rf"(?i)\b(?:i|we)\s+(?:will|shall|am going to|are going to)\s+(?:approve|issue|authorize|authorise|process|grant|refund|credit)\b[^.!?]{{0,60}}\b{_RESTRICTED_OBJECT}\b"
    ),
    # Claims of having inspected private systems without operational evidence
    re.compile(
        r"(?i)\b(?:i|we)\s*(?:'ve|\s+have)?\s*(?:verified|confirmed|checked|looked up|accessed)\b[^.!?]{0,40}\b(?:your\s+)?(?:order|account|payment|shipment)\b"
    ),
)

_SECRET_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(?:send|share|provide|give|tell|reply with|confirm)\b[^.!?]{0,40}\b(?:password|passcode|pin|full card number|card number|cvv|security code|one[- ]time code|otp)\b"
    ),
)


def contains_restricted_claim(text: str) -> bool:
    """True when the text claims a restricted action was, or will be, performed."""
    return any(pattern.search(text) for pattern in _RESTRICTED_CLAIM_PATTERNS)


def requests_secret(text: str) -> bool:
    """True when the text asks the customer to disclose a credential."""
    return any(pattern.search(text) for pattern in _SECRET_REQUEST_PATTERNS)


# --------------------------------------------------------------------------------------
# Draft validation
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ContentValidationResult:
    valid: bool
    issues: list[str] = field(default_factory=list)
    unknown_evidence_ids: list[str] = field(default_factory=list)
    contains_sensitive_data: bool = False
    contains_restricted_claim: bool = False


class ContentValidator:
    """Validates grounding, authority limits and secret leakage in a support draft."""

    def validate(
        self,
        draft: SupportDraft,
        evidence: list[EvidenceRecord],
    ) -> ContentValidationResult:
        issues: list[str] = []
        known_ids = {item.evidence_id for item in evidence}
        unknown = sorted(set(draft.evidence_ids) - known_ids)
        if unknown:
            issues.append(f"Draft references unknown evidence identifiers: {unknown}")

        has_steps = any(step.strip() for step in draft.troubleshooting_steps)
        if has_steps and not draft.evidence_ids:
            issues.append("Troubleshooting steps must cite at least one evidence identifier.")

        combined = "\n".join(
            [
                draft.issue_summary,
                draft.customer_response,
                *draft.troubleshooting_steps,
                *draft.unresolved_questions,
                *draft.limitations,
            ]
        )

        sensitive = contains_sensitive_data(combined)
        if sensitive:
            issues.append("Draft contains sensitive or credential-like data.")

        if requests_secret(combined):
            sensitive = True
            issues.append("Draft asks the customer to disclose a credential.")

        restricted = contains_restricted_claim(combined)
        if restricted:
            issues.append("Draft claims a restricted action was completed or promised.")

        return ContentValidationResult(
            valid=not issues,
            issues=issues,
            unknown_evidence_ids=unknown,
            contains_sensitive_data=sensitive,
            contains_restricted_claim=restricted,
        )


# --------------------------------------------------------------------------------------
# Article privacy validation
# --------------------------------------------------------------------------------------
#: Every customer-specific identifier family that must never reach reusable documentation.
FORBIDDEN_ARTICLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bOP-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bORD-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bCUS-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bSHP-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bRET-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bCHK-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bACC-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\bTKT-[0-9A-Z_-]+\b"),
    re.compile(r"(?i)\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    re.compile(r"(?i)\bTRK-[0-9A-Z*_-]+\b"),
)


@dataclass(frozen=True)
class ArticlePrivacyResult:
    privacy_safe: bool
    issues: list[str] = field(default_factory=list)
    matched_identifiers: list[str] = field(default_factory=list)


class ArticlePrivacyValidator:
    """Deterministically enforces the customer-agnostic rule for reusable articles."""

    def validate(
        self,
        article: TroubleshootingArticle,
        *,
        allowed_evidence_ids: set[str] | None = None,
    ) -> ArticlePrivacyResult:
        issues: list[str] = []
        matched: list[str] = []

        text = "\n".join(
            [article.title, article.body_markdown, *article.source_evidence_ids, *article.limitations]
        )
        for pattern in FORBIDDEN_ARTICLE_PATTERNS:
            for match in pattern.findall(text):
                matched.append(str(match))
        if matched:
            issues.append("Article contains customer-specific or operational identifiers.")

        if contains_sensitive_data(text):
            issues.append("Article contains sensitive or credential-like data.")

        non_public = [item for item in article.source_evidence_ids if not item.startswith("EV-")]
        if non_public:
            issues.append(f"Article may cite only EV-prefixed public evidence: {sorted(non_public)}")

        if allowed_evidence_ids is not None:
            unknown = sorted(set(article.source_evidence_ids) - allowed_evidence_ids)
            if unknown:
                issues.append(f"Article cites evidence that was never selected: {unknown}")

        return ArticlePrivacyResult(
            privacy_safe=not issues,
            issues=issues,
            matched_identifiers=sorted(set(matched)),
        )
