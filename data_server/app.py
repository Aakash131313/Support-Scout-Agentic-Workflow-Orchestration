"""FastAPI application exposing synthetic, read-only support data.

Read-only by construction: there is no POST, PUT, PATCH or DELETE route anywhere in
this service, so no agent can modify an order, account or refund even by accident.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from data_server.database import create_db_and_tables, get_session
from data_server.models import (
    AccountDiagnostic,
    CheckoutDiagnostic,
    Customer,
    Order,
    ReturnRecord,
    Shipment,
)
from data_server.schemas import (
    AccountDiagnosticResponse,
    CheckoutDiagnosticResponse,
    CustomerResponse,
    HealthResponse,
    OrderResponse,
    ReturnResponse,
    ShipmentResponse,
)
from data_server.seed import seed_database

SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    seed_database()
    yield


app = FastAPI(
    title="SupportScout Synthetic Operations API",
    version="1.0.0",
    description="Read-only synthetic operational data for SupportScout troubleshooting.",
    lifespan=lifespan,
)


def not_found(kind: str, record_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind} {record_id} not found")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="support-data")


@app.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, session: SessionDep):
    record = session.get(Customer, customer_id)
    if record is None:
        raise not_found("Customer", customer_id)
    return record


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, session: SessionDep):
    record = session.get(Order, order_id)
    if record is None:
        raise not_found("Order", order_id)
    return record


@app.get("/orders/{order_id}/shipment", response_model=ShipmentResponse)
def get_shipment(order_id: str, session: SessionDep):
    record = session.exec(select(Shipment).where(Shipment.order_id == order_id)).first()
    if record is None:
        raise not_found("Shipment for order", order_id)
    return record


@app.get("/orders/{order_id}/return", response_model=ReturnResponse)
def get_return(order_id: str, session: SessionDep):
    record = session.exec(select(ReturnRecord).where(ReturnRecord.order_id == order_id)).first()
    if record is None:
        raise not_found("Return for order", order_id)
    return record


@app.get("/customers/{customer_id}/checkout-diagnostics", response_model=CheckoutDiagnosticResponse)
def get_checkout_diagnostic(customer_id: str, session: SessionDep):
    record = session.exec(
        select(CheckoutDiagnostic)
        .where(CheckoutDiagnostic.customer_id == customer_id)
        .order_by(CheckoutDiagnostic.occurred_at.desc())
    ).first()
    if record is None:
        raise not_found("Checkout diagnostics for customer", customer_id)
    return record


@app.get("/customers/{customer_id}/account-diagnostics", response_model=AccountDiagnosticResponse)
def get_account_diagnostic(customer_id: str, session: SessionDep):
    record = session.exec(
        select(AccountDiagnostic)
        .where(AccountDiagnostic.customer_id == customer_id)
        .order_by(AccountDiagnostic.occurred_at.desc())
    ).first()
    if record is None:
        raise not_found("Account diagnostics for customer", customer_id)
    return record
