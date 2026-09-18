"""Deterministic synthetic data seeding.

All original records are preserved exactly, so artifacts produced before this refactor
remain reproducible. A small number of records were added to cover scenarios the
curated sample inputs exercise: an order that has not shipped yet, a carrier delivery
exception, and a declined-payment checkout failure.

Deliberately absent: ORD-9999 and CUS-999. Their absence is what makes the
unknown-record scenarios a genuine test of missing-data handling.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from data_server.database import create_db_and_tables, get_engine
from data_server.models import (
    AccountDiagnostic,
    CheckoutDiagnostic,
    Customer,
    Order,
    ReturnRecord,
    Shipment,
)


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def build_records() -> list:
    """Return every synthetic record, in dependency order."""
    customers = [
        Customer(customer_id="CUS-001", name_alias="Demo Customer One", email_masked="d***1@example.test", account_status="active", created_at=_utc(2026, 1, 10)),
        Customer(customer_id="CUS-002", name_alias="Demo Customer Two", email_masked="d***2@example.test", account_status="active", created_at=_utc(2026, 2, 2)),
        Customer(customer_id="CUS-003", name_alias="Demo Customer Three", email_masked="d***3@example.test", account_status="active", created_at=_utc(2026, 3, 3)),
        Customer(customer_id="CUS-004", name_alias="Demo Customer Four", email_masked="d***4@example.test", account_status="active", created_at=_utc(2026, 4, 4)),
    ]

    orders = [
        Order(order_id="ORD-1001", customer_id="CUS-001", order_status="shipped", created_at=_utc(2026, 9, 8, 12, 0), total=Decimal("89.99"), currency="USD", shipping_method="standard"),
        Order(order_id="ORD-1002", customer_id="CUS-002", order_status="delivered", created_at=_utc(2026, 9, 2, 9, 30), total=Decimal("42.50"), currency="USD", shipping_method="express"),
        Order(order_id="ORD-2001", customer_id="CUS-002", order_status="returned", created_at=_utc(2026, 8, 15, 16, 0), total=Decimal("120.00"), currency="USD", shipping_method="standard"),
        # Added: an order accepted but not yet shipped (no shipment record exists).
        Order(order_id="ORD-1003", customer_id="CUS-001", order_status="processing", created_at=_utc(2026, 9, 16, 10, 15), total=Decimal("31.25"), currency="USD", shipping_method="standard"),
        # Added: an order held by a carrier delivery exception.
        Order(order_id="ORD-3001", customer_id="CUS-003", order_status="shipped", created_at=_utc(2026, 9, 5, 8, 45), total=Decimal("64.00"), currency="USD", shipping_method="standard"),
    ]

    shipments = [
        Shipment(shipment_id="SHP-1001", order_id="ORD-1001", carrier="Demo Carrier", tracking_number_masked="TRK-****1001", shipment_status="in_transit", last_tracking_event="Arrived at regional facility", last_updated_at=_utc(2026, 9, 11, 8, 30), expected_delivery_date=date(2026, 9, 14)),
        Shipment(shipment_id="SHP-1002", order_id="ORD-1002", carrier="Demo Carrier", tracking_number_masked="TRK-****1002", shipment_status="delivered", last_tracking_event="Delivered at front door", last_updated_at=_utc(2026, 9, 10, 14, 10), expected_delivery_date=date(2026, 9, 10)),
        Shipment(shipment_id="SHP-3001", order_id="ORD-3001", carrier="Demo Carrier", tracking_number_masked="TRK-****3001", shipment_status="exception", last_tracking_event="Delivery exception: address could not be accessed", last_updated_at=_utc(2026, 9, 12, 17, 5), expected_delivery_date=date(2026, 9, 9)),
    ]

    returns = [
        ReturnRecord(return_id="RET-2001", order_id="ORD-2001", return_status="received", requested_at=_utc(2026, 9, 1, 10, 0), received_at=_utc(2026, 9, 8, 15, 0), refund_status="pending_review"),
    ]

    checkout = [
        CheckoutDiagnostic(attempt_id="CHK-3001", customer_id="CUS-003", occurred_at=_utc(2026, 9, 11, 9, 15), result="failed", error_code="ADDRESS_VALIDATION_FAILED", safe_error_message="The billing address could not be validated."),
        # Added: a declined payment, which needs different guidance from an address failure.
        CheckoutDiagnostic(attempt_id="CHK-3002", customer_id="CUS-001", occurred_at=_utc(2026, 9, 15, 19, 40), result="failed", error_code="PAYMENT_DECLINED", safe_error_message="The payment method was declined by the issuing bank."),
    ]

    accounts = [
        AccountDiagnostic(diagnostic_id="ACC-4001", customer_id="CUS-004", account_status="active", latest_event="account_recovery_completed", latest_login_result="failed", occurred_at=_utc(2026, 9, 11, 9, 45)),
    ]

    return customers + orders + shipments + returns + checkout + accounts


def seed_database(db_engine=None, *, force: bool = False) -> None:
    """Create tables and insert synthetic records.

    Args:
        db_engine: Optional engine override, used by tests.
        force: Rebuild from scratch. Without this, an existing database is left alone,
            which means schema or data changes will not appear until you reseed.
    """
    active = db_engine or get_engine()
    create_db_and_tables(active)

    with Session(active) as session:
        existing = session.exec(select(Customer)).first()
        if existing is not None:
            if not force:
                return
            for model in (
                AccountDiagnostic,
                CheckoutDiagnostic,
                ReturnRecord,
                Shipment,
                Order,
                Customer,
            ):
                for row in session.exec(select(model)).all():
                    session.delete(row)
            session.commit()

        session.add_all(build_records())
        session.commit()


if __name__ == "__main__":
    seed_database(force=True)
    print("Synthetic SupportScout operational data seeded.")
