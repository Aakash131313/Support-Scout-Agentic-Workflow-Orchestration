"""Every committed sample input must validate and stay synthetic."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from support_scout.schemas import SupportTicket
from support_scout.services.safety_rules import SafetyScreener

SAMPLES = sorted(Path("sample_inputs").glob("*.json"))


def test_sample_inputs_exist():
    assert len(SAMPLES) >= 15


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_sample_input_validates(path):
    SupportTicket.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_sample_ticket_ids_are_unique_and_safe(path):
    ticket = SupportTicket.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert ticket.ticket_id.startswith("TKT-")


def test_ticket_ids_do_not_collide():
    identifiers = [
        SupportTicket.model_validate(json.loads(path.read_text(encoding="utf-8"))).ticket_id
        for path in SAMPLES
    ]
    assert len(identifiers) == len(set(identifiers))


def test_sample_set_covers_escalation_and_completion():
    """The curated set must exercise both outcomes, not just the happy path."""
    screener = SafetyScreener()
    outcomes = set()
    for path in SAMPLES:
        ticket = SupportTicket.model_validate(json.loads(path.read_text(encoding="utf-8")))
        outcomes.add(screener.screen_ticket(ticket).required)
    assert outcomes == {True, False}


def test_sample_set_covers_the_restricted_action_gate():
    from support_scout.hitl import requires_human_approval

    screener = SafetyScreener()
    gated = [
        path.stem
        for path in SAMPLES
        if requires_human_approval(
            screener.screen_ticket(
                SupportTicket.model_validate(json.loads(path.read_text(encoding="utf-8")))
            ).escalation.reason_code
        )
    ]
    assert len(gated) >= 3


def test_operational_references_match_the_seeded_data():
    """Order and customer references must be real, except the deliberate miss."""
    known_orders = {"ORD-1001", "ORD-1002", "ORD-2001", "ORD-1003", "ORD-3001"}
    known_customers = {"CUS-001", "CUS-002", "CUS-003", "CUS-004"}
    intentional_misses = {"ORD-9999"}

    for path in SAMPLES:
        ticket = SupportTicket.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if ticket.order_reference:
            assert ticket.order_reference in known_orders | intentional_misses, path.stem
        if ticket.customer_reference:
            assert ticket.customer_reference in known_customers, path.stem
