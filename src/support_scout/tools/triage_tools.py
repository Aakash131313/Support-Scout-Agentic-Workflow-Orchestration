"""Triage tools: sentiment analysis, domain reference, and triage submission.

Sentiment is exposed as a deterministic tool rather than being folded into a single
model call. That makes it independently testable and makes the separation the mission
requires explicit: sentiment influences *tone and priority*, never authority. A furious
customer asking a routine question still gets routine handling; a calm customer
reporting account compromise still escalates.

`submit_triage` is idempotent. Every submit tool in this project carries the same
"call this exactly once" instruction, and a live run showed the QA equivalent being
called eleven times because nothing enforced it. The same guard is applied here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from smolagents import tool

from ..schemas import (
    SentimentAssessment,
    SentimentIntensity,
    SentimentLabel,
    SupportDomain,
    TicketClassification,
    Urgency,
)
from ..services.safety_rules import contains_term, normalize

# --------------------------------------------------------------------------------------
# Sentiment lexicon
# --------------------------------------------------------------------------------------
NEGATIVE_TERMS = frozenset(
    {
        "angry", "furious", "frustrated", "frustrating", "annoyed", "upset", "unhappy",
        "disappointed", "terrible", "awful", "horrible", "worst", "useless", "ridiculous",
        "unacceptable", "disgusted", "fed up", "sick of", "never again", "waste",
    }
)

POSITIVE_TERMS = frozenset(
    {
        "thanks", "thank you", "great", "excellent", "appreciate", "appreciated",
        "helpful", "pleased", "happy", "wonderful", "love", "perfect",
    }
)

INTENSIFIERS = frozenset(
    {"very", "extremely", "incredibly", "absolutely", "completely", "totally", "really", "so"}
)

URGENCY_TERMS = frozenset(
    {"urgent", "urgently", "asap", "immediately", "emergency", "critical", "right now", "today"}
)


def assess_sentiment(message: str) -> SentimentAssessment:
    """Deterministic lexicon sentiment assessment. Advisory only, never authoritative."""
    text = normalize(message)

    negative_hits = [term for term in NEGATIVE_TERMS if contains_term(text, term)]
    positive_hits = [term for term in POSITIVE_TERMS if contains_term(text, term)]
    intensifier_hits = [term for term in INTENSIFIERS if contains_term(text, term)]

    if len(negative_hits) > len(positive_hits):
        label = SentimentLabel.NEGATIVE
        strength = len(negative_hits) + len(intensifier_hits)
    elif positive_hits and not negative_hits:
        label = SentimentLabel.POSITIVE
        strength = len(positive_hits)
    else:
        label = SentimentLabel.NEUTRAL
        strength = 0

    if strength >= 3:
        intensity = SentimentIntensity.STRONG
    elif strength == 2:
        intensity = SentimentIntensity.MODERATE
    else:
        intensity = SentimentIntensity.MILD

    if label == SentimentLabel.NEUTRAL:
        rationale = "No strong sentiment markers were present."
    else:
        markers = negative_hits if label == SentimentLabel.NEGATIVE else positive_hits
        rationale = f"Detected {label.value} markers: {', '.join(sorted(markers)[:5])}."

    return SentimentAssessment(label=label, intensity=intensity, rationale_summary=rationale)


def suggests_urgency(message: str) -> bool:
    """True when the message contains an explicit time-pressure marker."""
    text = normalize(message)
    return any(contains_term(text, term) for term in URGENCY_TERMS)


# --------------------------------------------------------------------------------------
# Workspace and tools
# --------------------------------------------------------------------------------------
@dataclass
class TriageWorkspace:
    """Mutable state shared by the triage tools during a single agent run."""

    customer_message: str = ""
    sentiment: SentimentAssessment | None = None
    classification: TicketClassification | None = None
    submitted: bool = False
    notes: list[str] = field(default_factory=list)

    def reset(self, customer_message: str) -> None:
        self.customer_message = customer_message
        self.sentiment = None
        self.classification = None
        self.submitted = False
        self.notes.clear()


def build_triage_tools(workspace: TriageWorkspace) -> list[Any]:
    """Create the triage tool set bound to one run's workspace."""

    @tool
    def analyze_sentiment(reason: str) -> str:
        """Measure the customer's sentiment and any explicit urgency markers.

        Sentiment affects tone and priority only. It never authorizes an action and
        never, on its own, requires escalation.

        Args:
            reason: A short note on why sentiment is being measured.
        """
        del reason
        sentiment = assess_sentiment(workspace.customer_message)
        workspace.sentiment = sentiment
        return json.dumps(
            {
                "label": sentiment.label.value,
                "intensity": sentiment.intensity.value,
                "rationale": sentiment.rationale_summary,
                "explicit_urgency_markers": suggests_urgency(workspace.customer_message),
                "note": "Sentiment informs tone and priority only; it never authorizes an action.",
            }
        )

    @tool
    def list_supported_domains(reason: str) -> str:
        """List the support domains this system is allowed to handle.

        Args:
            reason: A short note on why the domain list is needed.
        """
        del reason
        return json.dumps(
            {
                "domains": {
                    SupportDomain.ORDER_TRACKING_DELIVERY.value: (
                        "Where an order is, delivery delays, tracking that has not updated, "
                        "packages marked delivered but not received."
                    ),
                    SupportDomain.RETURNS_REFUNDS.value: (
                        "How to return an item, return eligibility, the status of a return "
                        "or refund already in progress."
                    ),
                    SupportDomain.ACCOUNT_CHECKOUT.value: (
                        "Sign-in problems, account settings, checkout and payment failures "
                        "at the point of purchase."
                    ),
                    SupportDomain.UNSUPPORTED.value: "Anything outside the three domains above.",
                    SupportDomain.UNCERTAIN.value: "Use when the request cannot be classified reliably.",
                }
            }
        )

    @tool
    def submit_triage(
        domain: str, intent: str, urgency: str, confidence: float, uncertainty_reason: str
    ) -> str:
        """Submit the triage decision. Call this exactly once, at the end.

        analyze_sentiment must be called first, because sentiment is part of the
        triage record. The first submission is final: calling this again returns
        "already_submitted" and does not change the recorded classification.

        Args:
            domain: One of the values returned by list_supported_domains.
            intent: A short phrase describing what the customer actually wants.
            urgency: One of "low", "medium", "high" or "critical".
            confidence: Classification confidence between 0.0 and 1.0.
            uncertainty_reason: Why the domain is uncertain, or "" when it is not.
        """
        # The first submission wins. A repeat call means the agent has not noticed it
        # is finished; say so plainly instead of silently overwriting the result.
        if workspace.submitted and workspace.classification is not None:
            return json.dumps(
                {
                    "status": "already_submitted",
                    "reason": (
                        "Triage was already submitted for this ticket and cannot be "
                        "changed. Your work here is complete; stop calling this tool."
                    ),
                    "domain": workspace.classification.domain.value,
                    "urgency": workspace.classification.urgency.value,
                    "confidence": workspace.classification.confidence,
                }
            )

        if workspace.sentiment is None:
            return json.dumps(
                {"status": "rejected", "reason": "Call analyze_sentiment before submitting triage."}
            )

        try:
            domain_value = SupportDomain(domain.strip().casefold())
        except ValueError:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": f"Unknown domain '{domain}'.",
                    "allowed": [item.value for item in SupportDomain],
                }
            )

        try:
            urgency_value = Urgency(urgency.strip().casefold())
        except ValueError:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": f"Unknown urgency '{urgency}'.",
                    "allowed": [item.value for item in Urgency],
                }
            )

        try:
            classification = TicketClassification(
                domain=domain_value,
                intent=intent.strip() or "unspecified",
                urgency=urgency_value,
                confidence=float(confidence),
                uncertainty_reason=uncertainty_reason.strip() or None,
            )
        except Exception as exc:  # noqa: BLE001 - returned to the agent to correct
            return json.dumps({"status": "rejected", "reason": str(exc)[:400]})

        workspace.classification = classification
        workspace.submitted = True
        return json.dumps(
            {
                "status": "submitted",
                "domain": classification.domain.value,
                "urgency": classification.urgency.value,
                "confidence": classification.confidence,
            }
        )

    return [analyze_sentiment, list_supported_domains, submit_triage]
