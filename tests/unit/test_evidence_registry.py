"""Evidence registry tests: deterministic identifiers, deduplication, lookup."""
from __future__ import annotations

from support_scout.evidence_registry import EvidenceRegistry


def test_public_identifiers_are_sequential_and_deterministic():
    registry = EvidenceRegistry()
    first = registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    second = registry.register_public(source_url="https://b.example.com", title="B", content="beta")
    assert first.evidence_id == "EV-001"
    assert second.evidence_id == "EV-002"


def test_duplicate_url_is_not_registered_twice():
    registry = EvidenceRegistry()
    registry.register_public(source_url="https://a.example.com/", title="A", content="alpha")
    duplicate = registry.register_public(source_url="https://a.example.com", title="A", content="other")
    assert duplicate is None
    assert len(registry.public_evidence) == 1


def test_duplicate_content_is_not_registered_twice():
    registry = EvidenceRegistry()
    registry.register_public(source_url="https://a.example.com", title="A", content="same text")
    duplicate = registry.register_public(source_url="https://b.example.com", title="B", content="same text")
    assert duplicate is None


def test_content_is_bounded():
    registry = EvidenceRegistry(max_content_characters=10)
    record = registry.register_public(source_url="https://a.example.com", title="A", content="x" * 500)
    assert len(record.content) == 10


def test_operational_identifiers_are_sequential():
    registry = EvidenceRegistry()
    first = registry.register_operational(record_type="order", record_id="ORD-1001", facts={})
    second = registry.register_operational(record_type="shipment", record_id="SHP-1001", facts={})
    assert first.evidence_id == "OP-001"
    assert second.evidence_id == "OP-002"


def test_duplicate_operational_record_is_not_registered_twice():
    registry = EvidenceRegistry()
    registry.register_operational(record_type="order", record_id="ORD-1001", facts={})
    duplicate = registry.register_operational(record_type="order", record_id="ORD-1001", facts={})
    assert duplicate is None


def test_unknown_ids_reports_fabricated_identifiers():
    registry = EvidenceRegistry()
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    assert registry.unknown_ids(["EV-001", "EV-404", "OP-001"]) == ["EV-404", "OP-001"]


def test_public_and_operational_ids_are_separable():
    registry = EvidenceRegistry()
    registry.register_public(source_url="https://a.example.com", title="A", content="alpha")
    registry.register_operational(record_type="order", record_id="ORD-1001", facts={})
    assert registry.public_ids() == {"EV-001"}
    assert registry.operational_ids() == {"OP-001"}
    assert registry.known_ids == {"EV-001", "OP-001"}
