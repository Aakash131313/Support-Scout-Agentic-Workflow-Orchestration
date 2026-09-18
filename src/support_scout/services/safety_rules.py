"""Deterministic safety screening.

Authority model: these rules run *before* the model sees anything, and the model can
never clear them. If a rule fires, escalation is mandatory.

Implementation note (supersedes the Phase 13-14 alias approach): matching is
token/keyword co-occurrence rather than full-phrase aliases. The old approach missed
ordinary paraphrases -- "please refund me", "I want my money back", "can you authorize
a refund" all bypassed a list built around the literal string "approve refund". Rules
here require one term from an *intent* group and one from an *object* group, which
generalises across phrasing while staying fully deterministic and testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas import (
    EscalationDecision,
    EscalationReason,
    SupportDomain,
    SupportTicket,
    TicketClassification,
)

# --------------------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------------------
_PUNCTUATION = re.compile(r"[^a-z0-9\s'-]+")
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lower-case, strip punctuation and collapse whitespace for stable matching."""
    lowered = text.casefold().replace("'", "")
    stripped = _PUNCTUATION.sub(" ", lowered)
    return _WHITESPACE.sub(" ", stripped).strip()


def contains_term(normalized_text: str, term: str) -> bool:
    """Whole-word containment check that also supports multi-word terms."""
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized_text) is not None


def contains_any(normalized_text: str, terms: frozenset[str]) -> bool:
    return any(contains_term(normalized_text, term) for term in terms)


# --------------------------------------------------------------------------------------
# Term vocabulary
# --------------------------------------------------------------------------------------
FINANCIAL_OBJECTS = frozenset(
    {
        "refund", "refunds", "refunded", "reimbursement", "reimburse", "credit",
        "store credit", "chargeback", "charge back", "money back", "my money",
        "payment", "repayment", "compensation", "adjustment",
    }
)

AUTHORIZATION_INTENTS = frozenset(
    {
        "approve", "approved", "approval", "authorize", "authorise", "authorization",
        "issue", "issued", "grant", "granted", "process", "give me", "send me",
        "want", "need", "request", "requesting", "please", "demand", "owe", "owed",
        "return my", "get my",
    }
)

POLICY_OBJECTS = frozenset(
    {"policy", "policies", "rule", "rules", "terms", "deadline", "window", "cutoff", "cut off"}
)

EXCEPTION_INTENTS = frozenset(
    {
        "exception", "exemption", "waive", "waiver", "waived", "override", "bend",
        "bypass", "make an exception", "outside", "past the", "beyond the", "extend",
    }
)

COMPROMISE_TERMS = frozenset(
    {
        "hacked", "hack", "compromised", "compromise", "breached", "breach",
        "unauthorized", "unauthorised", "stolen", "someone else", "not me",
        "identity theft", "fraudulent", "fraud", "took over", "taken over",
    }
)

ACCOUNT_TERMS = frozenset(
    {"account", "login", "log in", "sign in", "profile", "password", "credentials"}
)

INJECTION_INTENTS = frozenset(
    {"ignore", "disregard", "forget", "override", "bypass", "reveal", "print", "repeat", "show me"}
)

INJECTION_OBJECTS = frozenset(
    {
        "previous instructions", "prior instructions", "all instructions", "instructions",
        "system prompt", "system message", "your prompt", "your rules", "your instructions",
        "initial prompt", "developer message",
    }
)

UNSUPPORTED_TERMS = frozenset(
    {
        "legal advice", "lawsuit", "sue", "medical advice", "tax advice",
        "investment advice", "employment", "job application", "press inquiry",
    }
)

# --------------------------------------------------------------------------------------
# Sensitive data
# --------------------------------------------------------------------------------------
_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|passcode|pin|api[_ -]?key|access[_ -]?token|auth(?:entication)?[_ -]?token|token|secret)\b\s*(?:is|:|=)\s*\S+"
)
_CVV_PATTERN = re.compile(r"(?i)\b(?:cvv|cvc|security code)\b\s*(?:is|:|=)?\s*\d{3,4}\b")


def contains_sensitive_data(text: str) -> bool:
    """True when raw credentials or full payment data appear in the text."""
    return bool(
        _CARD_PATTERN.search(text)
        or _SSN_PATTERN.search(text)
        or _SECRET_ASSIGNMENT.search(text)
        or _CVV_PATTERN.search(text)
    )


# --------------------------------------------------------------------------------------
# Screening result
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ScreeningResult:
    """Outcome of deterministic pre-model screening."""

    escalation: EscalationDecision
    rule_ids: list[str] = field(default_factory=list)

    @property
    def required(self) -> bool:
        return self.escalation.required


def _escalate(rule_id: str, reason: EscalationReason, action: str) -> ScreeningResult:
    return ScreeningResult(
        escalation=EscalationDecision(
            required=True,
            reason_code=reason,
            summary="A deterministic safety rule requires human review.",
            recommended_human_action=action,
        ),
        rule_ids=[rule_id],
    )


_CLEAR = ScreeningResult(escalation=EscalationDecision(required=False))


class SafetyScreener:
    """Applies deterministic rules that outrank any model output."""

    def screen_ticket(self, ticket: SupportTicket) -> ScreeningResult:
        """Screen inbound ticket text before any model or network call happens."""
        raw = ticket.customer_message
        if contains_sensitive_data(raw):
            return _escalate(
                "sensitive_data",
                EscalationReason.SENSITIVE_DATA,
                "Purge the sensitive value and contact the customer through a secure channel.",
            )

        text = normalize(raw)

        if contains_any(text, INJECTION_INTENTS) and contains_any(text, INJECTION_OBJECTS):
            return _escalate(
                "prompt_injection",
                EscalationReason.OUTSIDE_AUTHORITY,
                "Review the request manually; it attempts to override system instructions.",
            )

        if contains_any(text, COMPROMISE_TERMS) and contains_any(text, ACCOUNT_TERMS):
            return _escalate(
                "account_compromise",
                EscalationReason.ACCOUNT_COMPROMISE,
                "Route to the account security team for immediate verification.",
            )

        if contains_any(text, EXCEPTION_INTENTS) and contains_any(text, POLICY_OBJECTS):
            return _escalate(
                "policy_exception",
                EscalationReason.POLICY_EXCEPTION,
                "A policy owner must decide whether an exception is permitted.",
            )

        if contains_any(text, FINANCIAL_OBJECTS) and contains_any(text, AUTHORIZATION_INTENTS):
            return _escalate(
                "financial_authorization",
                EscalationReason.FINANCIAL_AUTHORIZATION,
                "An authorized agent must decide the refund or adjustment.",
            )

        if contains_any(text, UNSUPPORTED_TERMS):
            return _escalate(
                "unsupported_domain",
                EscalationReason.UNSUPPORTED_DOMAIN,
                "Route to the appropriate specialist team; this is outside support scope.",
            )

        return _CLEAR

    def screen_classification(
        self,
        classification: TicketClassification,
        *,
        confidence_threshold: float,
    ) -> ScreeningResult:
        """Screen the model's classification after triage."""
        if classification.domain == SupportDomain.UNSUPPORTED:
            return _escalate(
                "unsupported_domain",
                EscalationReason.UNSUPPORTED_DOMAIN,
                "Route the request to the correct team.",
            )
        if (
            classification.domain == SupportDomain.UNCERTAIN
            or classification.confidence < confidence_threshold
        ):
            return _escalate(
                "low_confidence",
                EscalationReason.LOW_CONFIDENCE,
                "Classify the ticket manually before automated handling.",
            )
        return _CLEAR


# --------------------------------------------------------------------------------------
# Research query sanitisation (FR-006A)
# --------------------------------------------------------------------------------------
_IDENTIFIER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(?:ORD|CUS|SHP|RET|CHK|ACC|TKT|OP|EV)-[A-Za-z0-9_-]+\b"),
    re.compile(r"(?i)\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    re.compile(r"(?<!\d)(?:\d[ -]?){9,}(?!\d)"),
)


def sanitize_search_query(query: str) -> str:
    """Strip customer, order, account and refund identifiers from a web search query.

    Research may only ever look up *general public guidance*. This is enforced
    deterministically so a model cannot leak an identifier to a third-party search API.
    """
    cleaned = query
    for pattern in _IDENTIFIER_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    return cleaned


def query_contains_identifier(query: str) -> bool:
    """True when the query still carries an identifier that must not be searched."""
    return any(pattern.search(query) for pattern in _IDENTIFIER_PATTERNS)
