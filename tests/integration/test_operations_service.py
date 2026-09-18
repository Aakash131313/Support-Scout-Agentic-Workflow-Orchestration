"""Operations service contract tests.

Skipped automatically when sqlmodel/httpx are not installed, so the core suite still
runs in a minimal environment. The client-side contract is verified separately in
`test_support_data_client.py`, which needs no database at all.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlmodel", reason="sqlmodel is required for the operations service")
pytest.importorskip("httpx", reason="httpx is required by the FastAPI test client")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel, create_engine  # noqa: E402

from data_server import database  # noqa: E402
from data_server.app import app  # noqa: E402
from data_server.seed import seed_database  # noqa: E402


@pytest.fixture
def client(tmp_path):
    """Point the app at an isolated database rather than the real file."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    original = database.get_engine()
    database.set_engine(engine)
    seed_database(engine, force=True)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        database.set_engine(original)


def test_health_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "support-data"}


def test_customer_lookup(client):
    payload = client.get("/customers/CUS-001").json()
    assert payload["customer_id"] == "CUS-001"
    assert "***" in payload["email_masked"]


def test_order_lookup_includes_customer(client):
    payload = client.get("/orders/ORD-1001").json()
    assert payload["order_status"] == "shipped"
    assert payload["customer_id"] == "CUS-001"


def test_shipment_lookup(client):
    payload = client.get("/orders/ORD-1001/shipment").json()
    assert payload["shipment_status"] == "in_transit"
    assert payload["tracking_number_masked"].startswith("TRK-")


def test_return_lookup_reports_pending_refund(client):
    """Status only. The service has no way to authorize a refund."""
    payload = client.get("/orders/ORD-2001/return").json()
    assert payload["return_status"] == "received"
    assert payload["refund_status"] == "pending_review"


def test_checkout_diagnostics(client):
    payload = client.get("/customers/CUS-003/checkout-diagnostics").json()
    assert payload["error_code"] == "ADDRESS_VALIDATION_FAILED"
    assert "password" not in str(payload).casefold()


def test_account_diagnostics_exclude_credentials(client):
    payload = client.get("/customers/CUS-004/account-diagnostics").json()
    assert payload["latest_login_result"] == "failed"
    for token in ("password", "token", "secret"):
        assert token not in str(payload).casefold()


@pytest.mark.parametrize(
    "path",
    [
        "/orders/ORD-9999",
        "/customers/CUS-999",
        "/orders/ORD-9999/shipment",
        "/orders/ORD-1001/return",
        "/customers/CUS-001/account-diagnostics",
    ],
)
def test_missing_records_return_404(client, path):
    assert client.get(path).status_code == 404


def test_order_without_shipment_returns_404(client):
    """ORD-1003 is accepted but not yet shipped."""
    assert client.get("/orders/ORD-1003").status_code == 200
    assert client.get("/orders/ORD-1003/shipment").status_code == 404


def test_carrier_exception_is_available(client):
    payload = client.get("/orders/ORD-3001/shipment").json()
    assert payload["shipment_status"] == "exception"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_service_is_read_only(client, method):
    """No write route exists anywhere in the service."""
    response = getattr(client, method)("/orders/ORD-1001")
    assert response.status_code in {404, 405}


def test_reseed_is_idempotent(client, tmp_path):
    before = client.get("/customers/CUS-001").json()
    seed_database(database.get_engine(), force=True)
    assert client.get("/customers/CUS-001").json() == before
