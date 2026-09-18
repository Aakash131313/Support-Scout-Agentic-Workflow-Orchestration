"""SQLModel table definitions for synthetic operational support data.

Everything here is synthetic. Emails are masked and tracking numbers are partially
redacted at rest, so even the seed data cannot leak a realistic personal identifier.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


class Customer(SQLModel, table=True):
    customer_id: str = Field(primary_key=True, max_length=64)
    name_alias: str = Field(max_length=120)
    email_masked: str = Field(max_length=254)
    account_status: str = Field(index=True, max_length=40)
    created_at: datetime


class Order(SQLModel, table=True):
    order_id: str = Field(primary_key=True, max_length=64)
    customer_id: str = Field(foreign_key="customer.customer_id", index=True)
    order_status: str = Field(index=True, max_length=40)
    created_at: datetime
    total: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    currency: str = Field(default="USD", max_length=3)
    shipping_method: str = Field(max_length=40)


class Shipment(SQLModel, table=True):
    shipment_id: str = Field(primary_key=True, max_length=64)
    order_id: str = Field(foreign_key="order.order_id", unique=True, index=True)
    carrier: str = Field(max_length=80)
    tracking_number_masked: str = Field(max_length=80)
    shipment_status: str = Field(index=True, max_length=40)
    last_tracking_event: str = Field(max_length=500)
    last_updated_at: datetime
    expected_delivery_date: date | None = None


class ReturnRecord(SQLModel, table=True):
    return_id: str = Field(primary_key=True, max_length=64)
    order_id: str = Field(foreign_key="order.order_id", unique=True, index=True)
    return_status: str = Field(index=True, max_length=40)
    requested_at: datetime
    received_at: datetime | None = None
    refund_status: str = Field(index=True, max_length=40)


class CheckoutDiagnostic(SQLModel, table=True):
    attempt_id: str = Field(primary_key=True, max_length=64)
    customer_id: str = Field(foreign_key="customer.customer_id", index=True)
    occurred_at: datetime
    result: str = Field(index=True, max_length=40)
    error_code: str | None = Field(default=None, index=True, max_length=80)
    safe_error_message: str | None = Field(default=None, max_length=500)


class AccountDiagnostic(SQLModel, table=True):
    diagnostic_id: str = Field(primary_key=True, max_length=64)
    customer_id: str = Field(foreign_key="customer.customer_id", index=True)
    account_status: str = Field(index=True, max_length=40)
    latest_event: str = Field(max_length=120)
    latest_login_result: str = Field(max_length=40)
    occurred_at: datetime
