"""Support data client tests using a stubbed HTTP session (no server required)."""
from __future__ import annotations

import pytest
import requests

from support_scout.clients.support_data_client import SupportDataClient
from support_scout.exceptions import SupportDataClientError, SupportDataNotFound


class StubResponse:
    def __init__(self, status_code=200, payload=None, invalid_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("not json")
        return self._payload


class StubSession:
    def __init__(self, response=None, error=None):
        self.response = response or StubResponse()
        self.error = error
        self.requested: list[str] = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        if self.error:
            raise self.error
        return self.response


def build_client(response=None, error=None):
    session = StubSession(response, error)
    return SupportDataClient("http://ops.test", session=session), session


def test_order_lookup_builds_the_expected_path():
    client, session = build_client(StubResponse(payload={"order_id": "ORD-1001"}))
    assert client.get_order("ORD-1001")["order_id"] == "ORD-1001"
    assert session.requested == ["http://ops.test/orders/ORD-1001"]


@pytest.mark.parametrize(
    "method,argument,expected",
    [
        ("get_customer", "CUS-001", "/customers/CUS-001"),
        ("get_shipment", "ORD-1001", "/orders/ORD-1001/shipment"),
        ("get_return", "ORD-2001", "/orders/ORD-2001/return"),
        ("get_checkout_diagnostic", "CUS-003", "/customers/CUS-003/checkout-diagnostics"),
        ("get_account_diagnostic", "CUS-004", "/customers/CUS-004/account-diagnostics"),
    ],
)
def test_every_endpoint_is_addressed_correctly(method, argument, expected):
    client, session = build_client(StubResponse(payload={"ok": True}))
    getattr(client, method)(argument)
    assert session.requested == [f"http://ops.test{expected}"]


def test_missing_record_raises_not_found():
    client, _ = build_client(StubResponse(status_code=404))
    with pytest.raises(SupportDataNotFound):
        client.get_order("ORD-9999")


def test_server_error_raises_client_error():
    client, _ = build_client(StubResponse(status_code=500))
    with pytest.raises(SupportDataClientError):
        client.get_order("ORD-1001")


def test_timeout_is_sanitized():
    client, _ = build_client(error=requests.Timeout())
    with pytest.raises(SupportDataClientError) as exc_info:
        client.get_order("ORD-1001")
    assert "timed out" in str(exc_info.value).casefold()


def test_invalid_json_is_rejected():
    client, _ = build_client(StubResponse(invalid_json=True))
    with pytest.raises(SupportDataClientError):
        client.get_order("ORD-1001")


def test_non_object_payload_is_rejected():
    client, _ = build_client(StubResponse(payload=["unexpected"]))
    with pytest.raises(SupportDataClientError):
        client.get_order("ORD-1001")


def test_health_probe_reports_healthy():
    client, _ = build_client(StubResponse(payload={"status": "ok", "service": "support-data"}))
    assert client.is_healthy() is True


def test_health_probe_reports_unreachable():
    client, _ = build_client(error=requests.ConnectionError())
    assert client.is_healthy() is False


def test_base_url_trailing_slash_is_normalized():
    client = SupportDataClient("http://ops.test/", session=StubSession())
    assert client.base_url == "http://ops.test"
