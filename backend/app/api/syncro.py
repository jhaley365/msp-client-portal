"""Syncro ticket endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

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

    # Actual Syncro status strings grouped into logical buckets.
    OPEN_STATUSES = ["New", "In Progress", "Customer Reply", "Waiting On Customer", "Scheduled"]
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
    in_progress_count = _count_status("In Progress") + _count_status("Customer Reply") + _count_status("Waiting On Customer")
    total = _count_all()

    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "in_progress": in_progress_count,
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

    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-created_at-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }

    if status:
        # Use the status index when filtering; fall back to created_at index
        # for ordering within the filtered results by querying only that status.
        kwargs["IndexName"] = "customer_id-status-index"
        kwargs["KeyConditionExpression"] = Key("customer_id").eq(
            customer_id
        ) & Key("status").eq(status)
        # Remove ScanIndexForward since the sort key is status (string) not
        # a timestamp — ordering is lexicographic.  Keep for consistency.

    if last_key:
        if status:
            kwargs["ExclusiveStartKey"] = {
                "customer_id": customer_id,
                "status": status,
                # ticket_id is the table PK and must be included in the ESK
                # when querying a GSI; pass the value supplied by the client.
                "ticket_id": last_key,
            }
        else:
            kwargs["ExclusiveStartKey"] = {
                "customer_id": customer_id,
                "created_at": last_key,
                "ticket_id": last_key,
            }

    resp = tbl.query(**kwargs)

    # Determine the appropriate next_key field based on the index used.
    last_evaluated = resp.get("LastEvaluatedKey", {})
    if status:
        next_key = last_evaluated.get("ticket_id")
    else:
        next_key = last_evaluated.get("created_at")

    return {
        "items": resp.get("Items", []),
        "next_key": next_key,
        "count": resp.get("Count", 0),
    }
