"""Deterministic validation of generated content.

Two distinct checks live here:

* `ContentValidator`  - validates a customer-facing SupportDraft (grounding, authority,
  secret leakage).
* `ArticlePrivacyValidator` - validates a reusable TroubleshootingArticle, which has a
  much stricter rule: no customer-specific identifier of any kind may appear anywhere
  in the body text, not merely in the citation list.

Restricted-claim detection: why this is sentence-scoped
-------------------------------------------------------
The original implementation matched a flat set of regexes against the whole draft.
That produced three separate false positives in live runs, each appearing only after
the previous one was patched and the model rephrased:

  1. "I checked your order ... could not find any records"
     -> an honest report of a lookup that returned nothing, read as a fabricated claim.
  2. "the order was not successfully placed or has been canceled"
     -> a speculation about why a record is missing, read as "we canceled it",
        because the substring "has been canceled" appears in both.
  3. "I checked your order ... could not LOCATE any records"
     -> the same honest report as (1), but phrased with "locate" instead of
        "find". The fix for (1) consulted an enumerated list of not-found
        phrasings, and the model simply stepped outside it.

Patching one regex at a time did not converge, because the underlying question was
wrong. The check is not "does a completion verb appear near a restricted noun". It is:

    Does this sentence assert that WE performed a restricted action,
    without negation or hedging?

So the text is split into sentences and each is classified:

* First-person agency ("I approved your refund") is a claim of having acted. Only an
  explicit negation excuses it -- hedging does not, because "I may have approved your
  refund" is still an unacceptable thing to tell a customer.
* Passive or bare completions ("your refund has been approved") describe an outcome.
  These are excused by negation OR hedging, because in that form they are observations
  about system state rather than claims of agency.
* Inspection claims ("I checked your order") are excused by negation, hedging, or a
  not-found marker, since reporting an empty lookup is true and grounded. Negation is
  the primary signal; the marker list only covers absences stated without one.

Documented residual risk: "Your refund may have been approved" passes, as a hedged
passive. That is the deliberate tradeoff that allows "the order may have been canceled"
as a legitimate observation. It asserts nothing and promises nothing, and QA's evidence
grounding and operational-claims checks still apply to the same draft.

Operational-claim detection
---------------------------
`find_operational_claims` answers a different question, used by QA's
`check_operational_claims`: does this reply state the customer's *concrete operational
status* -- that their parcel is in transit, was delivered, left a facility, arrives
Thursday? Such statements can only come from the operations system, so QA requires an
`OP-` citation whenever one is present.

The same sentence-scoped discipline applies. A sentence is skipped when it reports an
absence ("could not find any records"), hedges ("may have been canceled", "should
arrive shortly"), or speaks generally about how orders behave rather than about this
customer's order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas import OperationalEvidence, ScrapedEvidence, SupportDraft, TroubleshootingArticle
from .safety_rules import contains_sensitive_data

EvidenceRecord = ScrapedEvidence | OperationalEvidence

# --------------------------------------------------------------------------------------
# Shared sentence scoping
# --------------------------------------------------------------------------------------
#: Sentences are the unit of analysis: negation and hedging apply within a sentence,
#: not across a whole multi-paragraph reply.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

#: Phrases showing a sentence is reporting an absence rather than asserting a status.
NOT_FOUND_MARKERS: tuple[str, ...] = (
    "could not find",
    "cannot find",
    "can't find",
    "couldn't find",
    "did not find",
    "didn't find",
    "unable to find",
    "unable to locate",
    "could not locate",
    "cannot locate",
    "couldn't locate",
    "no record",
    "no records",
    "does not exist",
    "doesn't exist",
    "no such order",
    "no such account",
    "not located",
    "was not found",
    "were not found",
    "no matching",
    "no results",
    "not available in",
    "does not appear",
    "no information",
)

# --------------------------------------------------------------------------------------
# Restricted claim detection
# --------------------------------------------------------------------------------------
_RESTRICTED_OBJECT = r"(?:refund|credit|payment|charge|exception|order|account|subscription|address)"
_COMPLETION_VERB = (
    r"(?:approved|issued|authorized|authorised|processed|granted|refunded|credited"
    r"|updated|modified|changed|cancelled|canceled|reset|restored)"
)
#: Auxiliaries and modals that may sit between the pronoun and the verb, so that
#: "I may have approved", "I had already approved" and "I've approved" all match.
_AUXILIARY = r"(?:may|might|could|must|will|shall|have|has|had|been|already|just|now)"

_NEGATION = re.compile(
    r"(?i)\b(?:not|never|cannot|can't|isn't|aren't|wasn't|weren't|haven't|hasn't|"
    r"didn't|doesn't|don't|no|unable|failed to|without)\b"
)
_HEDGE = re.compile(
    r"(?i)\b(?:may|might|could|perhaps|possibly|appears?|seems?|suggests?|indicates?|"
    r"likely|unlikely|if|whether|would|should)\b"
)

#: "I approved your refund", "we have already issued the credit".
_FIRST_PERSON_ACTION = re.compile(
    rf"(?i)\b(?:i|we)\s*(?:'ve|'ll|'d)?(?:\s+{_AUXILIARY})*\s+{_COMPLETION_VERB}\b"
    rf"[^.!?]{{0,60}}\b{_RESTRICTED_OBJECT}\b"
)
#: "I will approve your refund today".
_FIRST_PERSON_PROMISE = re.compile(
    rf"(?i)\b(?:i|we)\s+(?:will|shall|am going to|are going to)\s+"
    rf"(?:approve|issue|authorize|authorise|process|grant|refund|credit)\b"
    rf"[^.!?]{{0,60}}\b{_RESTRICTED_OBJECT}\b"
)
#: "your refund has been approved", "the payment was processed".
_PASSIVE_COMPLETION = re.compile(
    rf"(?i)\b(?:your|the|this)\s+{_RESTRICTED_OBJECT}\b[^.!?]{{0,40}}"
    rf"\b(?:has|have|had|was|were|is|are)\s+(?:been\s+)?{_COMPLETION_VERB}\b"
)
#: "refund approved", "payment processed" as a standalone statement.
_BARE_COMPLETION = re.compile(
    rf"(?i)\b{_RESTRICTED_OBJECT}\s+(?:successfully\s+)?{_COMPLETION_VERB}\b"
)
#: "I checked your order", "we verified your account".
_INSPECTION_CLAIM_PATTERN = re.compile(
    r"(?i)\b(?:i|we)\s*(?:'ve|\s+have)?\s*(?:verified|confirmed|checked|looked up|accessed)\b"
    r"[^.!?]{0,40}\b(?:your\s+)?(?:order|account|payment|shipment)\b"
)

_SECRET_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(?:send|share|provide|give|tell|reply with|confirm)\b[^.!?]{0,40}\b(?:password|passcode|pin|full card number|card number|cvv|security code|one[- ]time code|otp)\b"
    ),
)


def contains_restricted_claim(text: str) -> bool:
    """True when the text asserts that a restricted action was, or will be, performed.

    Evaluated sentence by sentence so that negation and hedging are scoped correctly.
    See the module docstring for the rules and the one documented residual risk.
    """
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue

        negated = bool(_NEGATION.search(sentence))
        hedged = bool(_HEDGE.search(sentence))

        # Claiming we acted. Only an explicit negation excuses this; a hedge does not.
        if _FIRST_PERSON_ACTION.search(sentence) or _FIRST_PERSON_PROMISE.search(sentence):
            if not negated:
                return True
            continue

        # Describing an outcome. Negated or hedged, this is an observation about
        # system state rather than a claim that we performed the action.
        if _PASSIVE_COMPLETION.search(sentence) or _BARE_COMPLETION.search(sentence):
            if not (negated or hedged):
                return True
            continue

        # Claiming to have inspected private data. An honest "checked, found
        # nothing" is grounded and allowed.
        #
        # Negation and hedging excuse this the same way they excuse a passive
        # completion, because "I checked X but <negation>" is structurally a report
        # of a miss. Relying on the NOT_FOUND_MARKERS list alone was the fourth
        # enumerated-phrase failure in this module: every earlier run said "could
        # not find", one run said "could not locate", and the list did not cover it,
        # so an honest report was escalated as a restricted claim. The negation
        # signal is already computed for every sentence; the marker list is kept as
        # an additional path for phrasings that report an absence without an
        # explicit negation ("I checked your order; no records exist").
        if _INSPECTION_CLAIM_PATTERN.search(sentence):
            if negated or hedged:
                continue
            lowered = sentence.casefold()
            if not any(marker in lowered for marker in NOT_FOUND_MARKERS):
                return True

    return False


def requests_secret(text: str) -> bool:
    """True when the text asks the customer to disclose a credential."""
    return any(pattern.search(text) for pattern in _SECRET_REQUEST_PATTERNS)


# --------------------------------------------------------------------------------------
# Operational claim detection
# --------------------------------------------------------------------------------------
#: A reference to this customer's own record, not a generic noun.
_CUSTOMER_RECORD = (
    r"(?:your|the|this)\s+(?:\w+\s+){0,2}"
    r"(?:order|package|parcel|shipment|delivery|return|refund|tracking|account)"
)
#: A named handling location, allowing an adjective ("the regional facility").
_FACILITY = r"(?:our|the|a)\s+(?:\w+\s+){0,2}(?:warehouse|facility|depot|hub|centre|center)"
#: A concrete operational state only the operations system can establish.
_OPERATIONAL_STATE = (
    rf"(?:shipped|delivered|dispatched|in\s+transit|out\s+for\s+delivery|"
    rf"on\s+its\s+way|on\s+the\s+way|en\s+route|arriving|arrive|arrived|"
    rf"received|processing|processed|pending|scanned|being\s+prepared|awaiting|"
    rf"on\s+(?:our|the)\s+(?:\w+\s+){{0,2}}(?:vehicle|truck|van)|"
    rf"at\s+{_FACILITY}|left\s+{_FACILITY})"
)
#: Past-tense movement verbs that assert status without a linking verb
#: ("your package left our warehouse").
_DIRECT_ACTION = r"(?:left|departed|shipped|arrived|cleared|passed\s+through)"

_OPERATIONAL_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "your order is in transit", "your package has been delivered"
    re.compile(
        rf"(?i)\b{_CUSTOMER_RECORD}\b[^.!?]{{0,50}}?"
        rf"\b(?:is|are|was|were|has\s+been|have\s+been|will\s+be|shows?|indicates?)\b"
        rf"[^.!?]{{0,30}}?\b{_OPERATIONAL_STATE}\b"
    ),
    # "your package left our warehouse" -- the verb itself is the assertion
    re.compile(rf"(?i)\b{_CUSTOMER_RECORD}\b[^.!?]{{0,30}}?\b{_DIRECT_ACTION}\b"),
    # "tracking shows your parcel is at the regional facility"
    re.compile(
        rf"(?i)\b(?:tracking|the\s+carrier|our\s+system|our\s+records)\b[^.!?]{{0,40}}?"
        rf"\b(?:shows?|indicates?|confirms?|says?|reports?)\b[^.!?]{{0,70}}?"
        rf"\b(?:{_OPERATIONAL_STATE}|{_DIRECT_ACTION})\b"
    ),
    # "it will arrive Thursday", "expected delivery is the 14th"
    re.compile(
        r"(?i)\b(?:expected\s+delivery|estimated\s+(?:delivery|arrival)|will\s+arrive|"
        r"should\s+arrive|arriving)\b[^.!?]{0,40}?"
        r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"\d{1,2}(?:st|nd|rd|th)?|january|february|march|april|may|june|july|august|"
        r"september|october|november|december|\d{4}-\d{2}-\d{2})\b"
    ),
)

#: Hedges specific to operational statements. Broader than the restricted-claim hedge
#: list because general support guidance frequently uses "typically" and "usually".
_OPERATIONAL_HEDGE = re.compile(
    r"(?i)\b(?:may|might|could|perhaps|possibly|appears?|seems?|suggests?|"
    r"indicate[sd]?\s+that|likely|unlikely|if|whether|would|should|typically|"
    r"usually|generally|often|normally|can\s+take|in\s+most\s+cases)\b"
)
#: Framing that describes how orders behave in general rather than this customer's.
_GENERAL_FRAMING = re.compile(
    r"(?i)\b(?:orders\s+are|packages\s+are|shipments\s+are|deliveries\s+are|"
    r"returns\s+are|refunds\s+are|items\s+are|standard\s+shipping|"
    r"most\s+orders|some\s+orders|carriers?\s+(?:typically|usually|generally))\b"
)


def find_operational_claims(text: str) -> list[str]:
    """Return sentences asserting this customer's concrete operational status.

    Used by QA to require an `OP-` citation whenever the reply states something only
    the operations system could know. Sentences reporting an absence, hedging, or
    describing general behaviour are not claims and are skipped.
    """
    claims: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue

        lowered = sentence.casefold()
        if any(marker in lowered for marker in NOT_FOUND_MARKERS):
            continue
        if _OPERATIONAL_HEDGE.search(sentence):
            continue
        if _GENERAL_FRAMING.search(sentence):
            continue

        if any(pattern.search(sentence) for pattern in _OPERATIONAL_CLAIM_PATTERNS):
            claims.append(sentence)

    return claims


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
