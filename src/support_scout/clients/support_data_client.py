"""HTTP client for the synthetic operational support data service.

SupportScout never touches the operations database directly. Every operational fact
arrives through this read-only client, which is also the seam the offline test suite
replaces with a fake.
"""
from __future__ import annotations

from typing import Any

import requests

from ..exceptions import SupportDataClientError, SupportDataNotFound


class SupportDataClient:
    """Read-only HTTP client for the operations service."""

    def __init__(self, base_url: str, timeout_seconds: int = 5, session: Any = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    # -- transport ---------------------------------------------------------------
    def _get(self, path: str) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}{path}", timeout=self.timeout_seconds
            )
        except requests.Timeout as exc:
            raise SupportDataClientError("Operations service request timed out") from exc
        except requests.RequestException as exc:
            raise SupportDataClientError("Operations service request failed") from exc

        if response.status_code == 404:
            raise SupportDataNotFound("Operational record was not found")
        if response.status_code >= 400:
            raise SupportDataClientError(
                f"Operations service returned HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SupportDataClientError("Operations service returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise SupportDataClientError("Operations service response must be an object")

        return payload

    # -- health ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        """Return the service health payload, raising if the service is unreachable."""
        return self._get("/health")

    def is_healthy(self) -> bool:
        """Boolean health probe used by the CLI start-up check."""
        try:
            return self.health().get("status") == "ok"
        except SupportDataClientError:
            return False

    # -- records -----------------------------------------------------------------
    def get_customer(self, customer_id: str) -> dict[str, Any]:
        return self._get(f"/customers/{customer_id}")

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._get(f"/orders/{order_id}")

    def get_shipment(self, order_id: str) -> dict[str, Any]:
        return self._get(f"/orders/{order_id}/shipment")

    def get_return(self, order_id: str) -> dict[str, Any]:
        return self._get(f"/orders/{order_id}/return")

    def get_checkout_diagnostic(self, customer_id: str) -> dict[str, Any]:
        return self._get(f"/customers/{customer_id}/checkout-diagnostics")

    def get_account_diagnostic(self, customer_id: str) -> dict[str, Any]:
        return self._get(f"/customers/{customer_id}/account-diagnostics")
