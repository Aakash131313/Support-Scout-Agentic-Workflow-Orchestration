"""Public response contracts for the synthetic operations API.

Note: `OperationalEvidence` deliberately does NOT live here. It is a SupportScout
contract, defined once in `support_scout.schemas`. The previous duplicate definition
in this module was unused and would have drifted.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class HealthResponse(APIModel):
    status: str
    service: str


class CustomerResponse(APIModel):
    customer_id: str
    name_alias: str
    email_masked: str
    account_status: str
    created_at: datetime


class OrderResponse(APIModel):
    order_id: str
    customer_id: str
    order_status: str
    created_at: datetime
    total: Decimal
    currency: str
    shipping_method: str


class ShipmentResponse(APIModel):
    shipment_id: str
    order_id: str
    carrier: str
    tracking_number_masked: str
    shipment_status: str
    last_tracking_event: str
    last_updated_at: datetime
    expected_delivery_date: date | None


class ReturnResponse(APIModel):
    return_id: str
    order_id: str
    return_status: str
    requested_at: datetime
    received_at: datetime | None
    refund_status: str


class CheckoutDiagnosticResponse(APIModel):
    attempt_id: str
    customer_id: str
    occurred_at: datetime
    result: str
    error_code: str | None
    safe_error_message: str | None


class AccountDiagnosticResponse(APIModel):
    diagnostic_id: str
    customer_id: str
    account_status: str
    latest_event: str
    latest_login_result: str
    occurred_at: datetime
