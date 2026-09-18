"""Evidence sufficiency and conflict assessment.

Deduplication and identifier assignment live in `EvidenceRegistry`. This module only
answers two questions about the evidence a run has gathered:

1. Is there enough of it to ground a confident answer?
2. Do the sources materially disagree?

Conflict detection is deliberately conservative. It looks for explicit
affirmative/negative pairs on the same concept. It will miss subtle disagreements --
that limitation is documented in the README rather than overstated here.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas import ScrapedEvidence

#: Affirmative/negative pairs whose co-occurrence signals a material conflict.
CONFLICT_PAIRS: tuple[tuple[str, str], ...] = (
    ("eligible", "not eligible"),
    ("eligible", "ineligible"),
    ("allowed", "not allowed"),
    ("permitted", "not permitted"),
    ("will refund", "will not refund"),
    ("can be returned", "cannot be returned"),
    ("is refundable", "is not refundable"),
    ("refundable", "non-refundable"),
    ("free returns", "return fee"),
    ("no restocking fee", "restocking fee"),
)

MINIMUM_SUFFICIENT_SOURCES = 1
MINIMUM_SUFFICIENT_CHARACTERS = 200


@dataclass(frozen=True)
class EvidenceAssessment:
    """Whether gathered evidence can support a confident, grounded answer."""

    items: list[ScrapedEvidence]
    insufficient: bool
    potential_conflict: bool
    reasons: list[str]


class EvidenceAssessor:
    """Assesses sufficiency and conflict across prepared public evidence."""

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

        conflict = self.detect_conflict(items)
        if conflict:
            reasons.append("Sources materially disagree about eligibility or policy.")

        return EvidenceAssessment(
            items=list(items),
            insufficient=insufficient,
            potential_conflict=conflict,
            reasons=reasons,
        )

    @staticmethod
    def detect_conflict(items: list[ScrapedEvidence]) -> bool:
        """Detect explicit affirmative/negative disagreement across sources."""
        combined = " ".join(item.content.casefold() for item in items)
        for affirmative, negative in CONFLICT_PAIRS:
            if negative in combined and affirmative in combined.replace(negative, " "):
                return True
        return False
