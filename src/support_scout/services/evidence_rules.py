"""Evidence relevance, sufficiency and conflict assessment.

Deduplication and identifier assignment live in `EvidenceRegistry`. This module answers
three questions about the evidence a run has gathered:

1. Is each source actually about the customer's problem?
2. Is there enough usable evidence to ground a confident answer?
3. Do the sources genuinely disagree with each other?

Design note on conflict detection
---------------------------------
The original implementation concatenated every source and looked for an
affirmative/negative pair anywhere in the combined text. That produced false positives
constantly, because a *single* policy page legitimately contains both sides of a
conditional rule: "eligible for return within 30 days ... not eligible if damaged by
misuse". Any one real-world help page trips a naive pair match on its own.

Detection now works at the level of individual *occurrences*. For each topic keyword
found in a source, the words immediately preceding it are inspected for a negation
marker, which classifies that occurrence as affirmative or negative. This avoids the
substring trap where "not eligible for return" also matches "eligible for return".

A conflict requires genuine disagreement *between* sources: one source must hold the
affirmative position on a topic while a different source holds the negative position.
A source containing both positions is stating a conditional rule and holds no position
at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas import ScrapedEvidence

# --------------------------------------------------------------------------------------
# Relevance
# --------------------------------------------------------------------------------------
#: Topic vocabulary per support domain. A source must overlap with the ticket's domain.
DOMAIN_TERMS: dict[str, frozenset[str]] = {
    "order_tracking_delivery": frozenset(
        {
            "tracking", "track", "delivery", "delivered", "shipment", "shipping",
            "parcel", "package", "courier", "carrier", "dispatch", "in transit",
            "late", "delayed", "lost package", "missing package", "order status",
        }
    ),
    "returns_refunds": frozenset(
        {
            "return", "returns", "refund", "refunds", "exchange", "replacement",
            "damaged", "defective", "faulty", "restocking", "return label",
            "money back", "credit", "warranty", "returned",
        }
    ),
    "account_checkout": frozenset(
        {
            "checkout", "payment", "card declined", "billing", "sign in", "signin",
            "log in", "login", "password", "account", "authentication", "address",
            "verification", "two-factor", "declined",
        }
    ),
}

#: Sources about a different industry or service entirely. Strong exclusion signal.
OFF_DOMAIN_TERMS = frozenset(
    {
        "postage", "stamps", "mailing service", "usps retail", "freight",
        "airline", "flight", "hotel booking", "insurance premium", "tax return",
        "mortgage", "student loan", "utility bill",
    }
)

MINIMUM_RELEVANCE_MATCHES = 2


@dataclass(frozen=True)
class RelevanceResult:
    """Whether one source is genuinely about the customer's problem."""

    relevant: bool
    matched_terms: list[str]
    off_domain_terms: list[str]
    reason: str


def assess_relevance(
    *,
    title: str,
    content: str,
    domain: str,
    minimum_matches: int = MINIMUM_RELEVANCE_MATCHES,
) -> RelevanceResult:
    """Decide whether a fetched page addresses the ticket's domain.

    Volume is not relevance. A long, authoritative page about the wrong subject is
    worse than no page at all, because it lends false confidence and pollutes conflict
    detection with unrelated positions.
    """
    text = f"{title}\n{content}".casefold()

    domain_terms = DOMAIN_TERMS.get(domain, frozenset())
    matched = sorted({term for term in domain_terms if term in text})
    off_domain = sorted({term for term in OFF_DOMAIN_TERMS if term in text})

    if not domain_terms:
        return RelevanceResult(
            relevant=True,
            matched_terms=[],
            off_domain_terms=off_domain,
            reason=f"No topic vocabulary defined for domain '{domain}'; accepted by default.",
        )

    if off_domain and len(matched) < minimum_matches + 1:
        return RelevanceResult(
            relevant=False,
            matched_terms=matched,
            off_domain_terms=off_domain,
            reason=(
                f"Source appears to be about a different service ({', '.join(off_domain[:3])}) "
                f"rather than {domain.replace('_', ' ')}."
            ),
        )

    if len(matched) < minimum_matches:
        return RelevanceResult(
            relevant=False,
            matched_terms=matched,
            off_domain_terms=off_domain,
            reason=(
                f"Source does not discuss {domain.replace('_', ' ')}; "
                f"found {len(matched)} topic term(s), need {minimum_matches}."
            ),
        )

    return RelevanceResult(
        relevant=True,
        matched_terms=matched,
        off_domain_terms=off_domain,
        reason=f"Source discusses {', '.join(matched[:5])}.",
    )


# --------------------------------------------------------------------------------------
# Conflict detection
# --------------------------------------------------------------------------------------
#: Words that flip the meaning of a following topic keyword.
NEGATION_MARKERS = frozenset(
    {
        "not", "never", "cannot", "can't", "isn't", "aren't", "won't", "wont",
        "no", "non", "ineligible", "unable", "refuse", "denied", "except",
    }
)

#: Phrases indicating a conditional rule rather than a universal position. A hedged
#: statement cannot be one side of a genuine conflict.
HEDGE_MARKERS = frozenset(
    {
        "may", "might", "some", "certain", "depending", "depends", "varies",
        "generally", "typically", "usually", "unless", "most", "often", "sometimes",
    }
)

_NEGATION_LOOKBACK_CHARACTERS = 45
_NEGATION_LOOKBACK_TOKENS = 8
_HEDGE_LOOKBACK_CHARACTERS = 90
_WORD = re.compile(r"[a-z']+")


@dataclass(frozen=True)
class ConflictTopic:
    """One topic on which two sources could genuinely disagree."""

    name: str
    label: str
    keywords: tuple[str, ...]


CONFLICT_TOPICS: tuple[ConflictTopic, ...] = (
    ConflictTopic(
        name="return_eligibility",
        label="return eligibility",
        keywords=("eligible for return", "be returned", "returnable"),
    ),
    ConflictTopic(
        name="refundability",
        label="refundability",
        keywords=("refundable", "be refunded", "issue a refund"),
    ),
    ConflictTopic(
        name="restocking_fee",
        label="restocking fees",
        keywords=("restocking fee",),
    ),
    ConflictTopic(
        name="return_shipping_cost",
        label="return shipping cost",
        keywords=("free return shipping", "return shipping is free"),
    ),
)


def _classify_occurrences(text: str, keyword: str) -> list[str]:
    """Classify every occurrence of `keyword` as affirmative, negative or hedged.

    Looking backwards from each occurrence avoids the substring trap: the phrase
    "not eligible for return" contains "eligible for return", so a plain membership
    test would count it as both positions at once.
    """
    lowered = text.casefold()
    positions: list[str] = []

    for match in re.finditer(re.escape(keyword), lowered):
        start = match.start()

        hedge_window = lowered[max(0, start - _HEDGE_LOOKBACK_CHARACTERS) : start]
        if any(token in HEDGE_MARKERS for token in _WORD.findall(hedge_window)):
            positions.append("hedged")
            continue

        negation_window = lowered[max(0, start - _NEGATION_LOOKBACK_CHARACTERS) : start]
        tokens = _WORD.findall(negation_window)[-_NEGATION_LOOKBACK_TOKENS:]

        # "non-refundable" and "cannot" collapse into the preceding token.
        prefixed = keyword in {"refundable"} and lowered[max(0, start - 4) : start].endswith(
            ("non-", "non", "un")
        )

        negated = prefixed or any(token in NEGATION_MARKERS for token in tokens)
        positions.append("negative" if negated else "affirmative")

    return positions


def _position_on(text: str, topic: ConflictTopic) -> str | None:
    """Return 'affirmative', 'negative', or None for a source's stance on one topic.

    A source asserting both sides is describing a conditional rule, which is normal
    guidance rather than a contradiction. It holds no position.
    """
    positions: list[str] = []
    for keyword in topic.keywords:
        positions.extend(_classify_occurrences(text, keyword))

    affirms = "affirmative" in positions
    negates = "negative" in positions

    if affirms == negates:
        return None
    return "affirmative" if affirms else "negative"


@dataclass(frozen=True)
class ConflictResult:
    """Whether two or more sources take genuinely opposed positions."""

    conflicted: bool
    topic: str | None = None
    label: str | None = None
    affirmative_ids: list[str] = field(default_factory=list)
    negative_ids: list[str] = field(default_factory=list)

    def describe(self) -> str:
        if not self.conflicted:
            return "No material disagreement between sources."
        return (
            f"Sources disagree about {self.label or self.topic}: "
            f"{', '.join(self.affirmative_ids)} say yes while "
            f"{', '.join(self.negative_ids)} say no."
        )


def detect_conflict(items: list[ScrapedEvidence]) -> ConflictResult:
    """Detect genuine disagreement *between* distinct sources.

    Requires at least two sources. A single source cannot conflict with itself, and a
    document stating both sides of its own conditional rule is not a conflict.
    """
    if len(items) < 2:
        return ConflictResult(conflicted=False)

    for topic in CONFLICT_TOPICS:
        affirmative: list[str] = []
        negative: list[str] = []

        for item in items:
            position = _position_on(item.content, topic)
            if position == "affirmative":
                affirmative.append(item.evidence_id)
            elif position == "negative":
                negative.append(item.evidence_id)

        if affirmative and negative:
            return ConflictResult(
                conflicted=True,
                topic=topic.name,
                label=topic.label,
                affirmative_ids=affirmative,
                negative_ids=negative,
            )

    return ConflictResult(conflicted=False)


# --------------------------------------------------------------------------------------
# Sufficiency
# --------------------------------------------------------------------------------------
MINIMUM_SUFFICIENT_SOURCES = 1
MINIMUM_SUFFICIENT_CHARACTERS = 200


@dataclass(frozen=True)
class EvidenceAssessment:
    """Whether gathered evidence can support a confident, grounded answer."""

    items: list[ScrapedEvidence]
    insufficient: bool
    potential_conflict: bool
    reasons: list[str]
    conflict: ConflictResult = field(default_factory=lambda: ConflictResult(conflicted=False))


class EvidenceAssessor:
    """Assesses sufficiency and cross-source conflict over prepared public evidence."""

    def __init__(
        self,
        *,
        minimum_sources: int = MINIMUM_SUFFICIENT_SOURCES,
        minimum_characters: int = MINIMUM_SUFFICIENT_CHARACTERS,
    ) -> None:
        self.minimum_sources = minimum_sources
        self.minimum_characters = minimum_characters

    def assess(self, items: list[ScrapedEvidence]) -> EvidenceAssessment:
        reasons: list[str] = []

        insufficient = len(items) < self.minimum_sources
        if insufficient:
            reasons.append("No usable public source was retrieved.")
        else:
            total_characters = sum(len(item.content.strip()) for item in items)
            if total_characters < self.minimum_characters:
                insufficient = True
                reasons.append("Retrieved sources contain too little usable guidance.")

        conflict = detect_conflict(items)
        if conflict.conflicted:
            reasons.append(conflict.describe())

        return EvidenceAssessment(
            items=list(items),
            insufficient=insufficient,
            potential_conflict=conflict.conflicted,
            reasons=reasons,
            conflict=conflict,
        )

    @staticmethod
    def detect_conflict(items: list[ScrapedEvidence]) -> bool:
        """Backwards-compatible boolean form."""
        return detect_conflict(items).conflicted
