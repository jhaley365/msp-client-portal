"""Syncro ticket endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/syncro", tags=["syncro"])

_PAGE_SIZE = 50

TABLE_SYNCRO_TICKETS = "SyncroTickets"


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    """Return ticket status counts for the Syncro dashboard card."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_SYNCRO_TICKETS)

    # All non-resolved statuses are considered "open".
    OPEN_STATUSES = [
        "New", "In Progress", "Waiting on Customer", "Waiting for Parts",
        "Scheduled", "Customer Reply", "Escalated to MSP", "Abandoned",
    ]
    RESOLVED_STATUSES = ["Resolved", "Closed", "Cancelled"]

    def _count_status(status_value: str) -> int:
        resp = tbl.query(
            IndexName="customer_id-status-index",
            KeyConditionExpression=(
                Key("customer_id").eq(customer_id) & Key("status").eq(status_value)
            ),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    def _count_all() -> int:
        resp = tbl.query(
            IndexName="customer_id-created_at-index",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    open_count = sum(_count_status(s) for s in OPEN_STATUSES)
    closed_count = sum(_count_status(s) for s in RESOLVED_STATUSES)
    total = _count_all()

    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "in_progress": _count_status("In Progress"),
    }


# ── Tickets ───────────────────────────────────────────────────────────────────


@router.get("/tickets")
def list_tickets(
    status: str | None = Query(default=None),
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return a paginated list of Syncro tickets for the authenticated customer.

    Parameters
    ----------
    status:
        Optional status filter (e.g. ``open``, ``closed``, ``in_progress``).
        When omitted all tickets are returned, sorted by ``created_at`` desc.
    last_key:
        Pagination cursor returned as ``next_key`` from a previous call.
    """
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_SYNCRO_TICKETS)

    # "open" is a virtual filter meaning all non-Resolved statuses.
    open_filter = status == "open"
    actual_status = None if (not status or open_filter) else status

    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-created_at-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }

    if actual_status:
        kwargs["IndexName"] = "customer_id-status-index"
        kwargs["KeyConditionExpression"] = (
            Key("customer_id").eq(customer_id) & Key("status").eq(actual_status)
        )

    if open_filter:
        kwargs["FilterExpression"] = Attr("status").ne("Resolved")

    if last_key:
        if actual_status:
            kwargs["ExclusiveStartKey"] = {
                "customer_id": customer_id,
                "status": actual_status,
                "ticket_id": last_key,
            }
        else:
            kwargs["ExclusiveStartKey"] = {
                "customer_id": customer_id,
                "created_at": last_key,
                "ticket_id": last_key,
            }

    resp = tbl.query(**kwargs)

    last_evaluated = resp.get("LastEvaluatedKey", {})
    if actual_status:
        next_key = last_evaluated.get("ticket_id")
    else:
        next_key = last_evaluated.get("created_at")

    return {
        "items": resp.get("Items", []),
        "next_key": next_key,
        "count": resp.get("Count", 0),
    }


# ── Admin: all-customer summary ───────────────────────────────────────────────

OPEN_STATUSES = {
    "New", "In Progress", "Waiting on Customer", "Waiting for Parts",
    "Scheduled", "Customer Reply", "Escalated to MSP", "Abandoned",
}
RESOLVED_STATUSES = {"Resolved", "Closed", "Cancelled"}


def _require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.get("/admin/summary")
def admin_summary(user: dict = Depends(_require_admin)) -> dict:
    """Return ticket counts across all customers for admin users."""
    tbl = _table(TABLE_SYNCRO_TICKETS)
    items: list[dict] = []
    kwargs: dict[str, Any] = {"ProjectionExpression": "#s", "ExpressionAttributeNames": {"#s": "status"}}
    while True:
        resp = tbl.scan(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek

    open_count = sum(1 for i in items if i.get("status") in OPEN_STATUSES)
    closed_count = sum(1 for i in items if i.get("status") in RESOLVED_STATUSES)
    in_progress = sum(1 for i in items if i.get("status") == "In Progress")

    return {
        "total": len(items),
        "open": open_count,
        "closed": closed_count,
        "in_progress": in_progress,
    }
